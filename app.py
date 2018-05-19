import flask
from flask import Flask, Response, request
import configparser
import tempfile
import anymarkup
import os
import re
import subprocess
import sys
from app.common import to_xml, Filters
from app.project_reader import get_projects
from app.vo_reader import get_vo_data
from app.rg_reader import get_topology
from app.topology import GRIDTYPE_1, GRIDTYPE_2


class InvalidArgumentsError(Exception): pass


app = Flask(__name__)

@app.route('/')
def homepage():

    return """
    <h1>OSG Topology Interface</h1>
    <a href="https://github.com/opensciencegrid/topology">Source Repo</a><br/>
    <p>XML data:
        <ul>
            <li><a href="miscproject/xml">Projects data</a></li>
            <li><a href="rgsummary/xml">Resource topology data</a></li>
            <li><a href="rgdowntime/xml">Resource downtime data</a></li>
            <li><a href="vosummary/xml">Virtual Organization data</a></li>
        </ul>
    </p>
    """

_projects = None
_vo_data = None
_contacts_data = None
_topology = None

@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


@app.route('/miscproject/xml')
def miscproject_xml():
    global _projects
    if not _projects:
        _projects = get_projects()
    projects_xml = to_xml(_projects)
    return Response(projects_xml, mimetype='text/xml')


@app.route('/vosummary/xml')
def vosummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = False
    if 'GRST_CRED_AURI_0' in request.environ:
        # Ok, there is a cert presented.  GRST_CRED_AURI_0 is the DN.  Match that to something.
        # Gridsite already made sure it matches something in the CA distribution
        authorized = True
    vos_xml = to_xml(_get_vo_data().get_tree(authorized, filters))
    return Response(vos_xml, mimetype='text/xml')


def get_filters_from_args(args) -> Filters:
    filters = Filters()
    if "active" in args:
        active_value = args.get("active_value", "")
        if active_value == "0":
            filters.active = False
        elif active_value == "1":
            filters.active = True
        else:
            raise InvalidArgumentsError("active_value must be 0 or 1")
    if "disable" in args:
        disable_value = args.get("disable_value", "")
        if disable_value == "0":
            filters.disable = False
        elif disable_value == "1":
            filters.disable = True
        else:
            raise InvalidArgumentsError("disable_value must be 0 or 1")
    if "gridtype" in args:
        gridtype_1, gridtype_2 = args.get("gridtype_1", ""), args.get("gridtype_2", "")
        if gridtype_1 == "on" and gridtype_2 == "on":
            pass
        elif gridtype_1 == "on":
            filters.grid_type = GRIDTYPE_1
        elif gridtype_2 == "on":
            filters.grid_type = GRIDTYPE_2
        else:
            raise InvalidArgumentsError("gridtype_1 or gridtype_2 or both must be \"on\"")
    if "downtime_attrs_showpast" in args:
        # doesn't make sense for rgsummary but will be ignored anyway
        try:
            v = args["downtime_attrs_showpast"]
            if v == "all":
                filters.past_days = -1
            elif not v:
                filters.past_days = 0
            else:
                filters.past_days = int(args["downtime_attrs_showpast"])
        except ValueError:
            raise InvalidArgumentsError("downtime_attrs_showpast must be an integer, \"\", or \"all\"")

    # 2 ways to filter by a key like "facility", "service", "sc", "site", etc.:
    # - either pass KEY_1=on, KEY_2=on, etc.
    # - pass KEY_sel[]=1, KEY_sel[]=2, etc. (multiple KEY_sel[] args).
    for filter_key, filter_list, description in [
        ("facility", filters.facility_id, "facility ID"),
        ("service", filters.service_id, "service ID"),
        ("sc", filters.support_center_id, "support center ID"),
        ("site", filters.site_id, "site ID"),
    ]:
        if filter_key in args:
            pat = re.compile(r"{0}_(\d+)".format(filter_key))
            arg_sel = "{0}_sel[]".format(filter_key)
            for k, v in args.items():
                if k == arg_sel:
                    try:
                        filter_list.append(int(v))
                    except ValueError:
                        raise InvalidArgumentsError("{0}={1}: must be int".format(k,v))
                elif pat.match(k):
                    m = pat.match(k)
                    filter_list.append(int(m.group(1)))
            if not filter_list:
                raise InvalidArgumentsError("at least one {0} must be specified".format(description))

    return filters


@app.route('/rgsummary/xml')
def rgsummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = False
    if 'GRST_CRED_AURI_0' in request.environ:
        # Ok, there is a cert presented.  GRST_CRED_AURI_0 is the DN.  Match that to something.
        # Gridsite already made sure it matches something in the CA distribution
        authorized = True

    rgsummary = _get_topology().get_resource_summary(authorized=authorized, filters=filters)
    rgsummary_xml = to_xml(rgsummary)
    return Response(rgsummary_xml, mimetype='text/xml')


@app.route('/rgdowntime/xml')
def rgdowntime_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = False
    if 'GRST_CRED_AURI_0' in request.environ:
        # Ok, there is a cert presented.  GRST_CRED_AURI_0 is the DN.  Match that to something.
        # Gridsite already made sure it matches something in the CA distribution
        authorized = True

    rgdowntime = _get_topology().get_downtimes(authorized=authorized, filters=filters)
    rgdowntime_xml = to_xml(rgdowntime)
    return Response(rgdowntime_xml, mimetype='text/xml')


def _get_contacts_data():
    """
    Get the contact information.  For now this is from a private github repo, but in the future
    it could be much more complicated to get the contact details
    """
    
    global _contacts_data
    # TODO: periodically update contacts info
    if not _contacts_data:
        # use local copy if it exists
        if os.path.exists("contacts.yaml"):
            _contacts_data = anymarkup.parse_file("contacts.yaml")
        else:
            # Get the contacts from bitbucket
            # Read in the config file with the SSH key location
            config = configparser.ConfigParser()
            config.read(["/etc/opt/topology/config.ini", "config.ini"])
            ssh_key = config['git']['ssh_key']
            # Create a temporary directory to store the contact information
            with tempfile.TemporaryDirectory() as tmp_dir:
                # From SO: https://stackoverflow.com/questions/4565700/specify-private-ssh-key-to-use-when-executing-shell-command
                cmd = "ssh-agent bash -c 'ssh-add {0}; git clone git@bitbucket.org:opensciencegrid/contact.git {1}'".format(ssh_key, tmp_dir)

                # I know this should be Popen or similar.  But.. I am unable to make that work.
                # I suspect it has something to do with the subshell that is being executed
                git_result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
                if git_result.returncode != 0:
                    # Git command exited with nonzero!
                    print("Git failed:\n" + git_result.stdout, file=sys.stderr)
                _contacts_data = anymarkup.parse_file(os.path.join(tmp_dir, 'contacts.yaml'))

    return _contacts_data


def _get_topology():
    global _topology
    if not _topology:
        _topology = get_topology("topology", _get_contacts_data())
    return _topology


def _get_vo_data():
    global _vo_data
    if not _vo_data:
        _vo_data = get_vo_data("virtual-organizations", _get_contacts_data())
    return _vo_data


if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

