import copy


import flask
from flask import Flask, Response, request
import configparser
import tempfile
import anymarkup
import os
import re
import subprocess
from converters.convertlib import to_xml, ensure_list, is_null
from converters.project_yaml_to_xml import get_projects
from converters.vo_yaml_to_xml import get_vos
from converters.resourcegroup_yaml_to_xml import get_topology
from converters.topology import Filters, GRIDTYPE_1, GRIDTYPE_2


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
_vos = None
_contacts = None
_topology = None

@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


@app.route('/miscproject/xml')
def projects():
    global _projects
    if not _projects:
        _projects = get_projects()
    projects_xml = to_xml(_projects)
    return Response(projects_xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    global _vos
    if not _vos:
        _vos = get_vos()
    args = flask.request.args
    if "active" in args:
        vos = copy.deepcopy(_vos)
        active_value = args.get("active_value", "")
        if active_value == "0":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if not vo["Active"]]
        elif active_value == "1":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if vo["Active"]]
        else:
            return Response("Invalid arguments: active_value must be 0 or 1", status=400)
    else:
        vos = _vos
    vos_xml = to_xml(vos)
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

    # 2 ways to filter by service: either pass service_1=on, service_2=on, etc.
    # or pass service_sel[]=1, service_sel[]=2, etc. (multiple service_sel[] args).
    # Same for facility, sc, and site
    for filter_name, filter_list, description in [
        ("facility", filters.facility_id, "facility ID"),
        ("service", filters.service_id, "service ID"),
        ("sc", filters.support_center_id, "support center ID"),
        ("site", filters.site_id, "site ID"),
    ]:
        if filter_name in args:
            pat = re.compile(r"{0}_(\d+)".format(filter_name))
            arg_sel = "{0}_sel[]".format(filter_name)
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
def resources():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = False
    if 'GRST_CRED_AURI_0' in request.environ:
        # Ok, there is a cert presented.  GRST_CRED_AURI_0 is the DN.  Match that to something.
        # Gridsite already made sure it matches something in the CA distribution
        authorized = True

    rgsummary = _getTopology().get_resource_summary(authorized=authorized, filters=filters)
    rgsummary_xml = to_xml(rgsummary)
    return Response(rgsummary_xml, mimetype='text/xml')


@app.route('/rgdowntime/xml')
def downtime():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = False
    if 'GRST_CRED_AURI_0' in request.environ:
        # Ok, there is a cert presented.  GRST_CRED_AURI_0 is the DN.  Match that to something.
        # Gridsite already made sure it matches something in the CA distribution
        authorized = True

    rgdowntime = _getTopology().get_downtimes(authorized=authorized, filters=filters)
    rgdowntime_xml = to_xml(rgdowntime)
    return Response(rgdowntime_xml, mimetype='text/xml')


def _getContacts():
    """
    Get the contact information.  For now this is from a private github repo, but in the future
    it could be much more complicated to get the contact details
    """
    
    global _contacts
    if not _contacts:
        # use local copy if it exists
        if os.path.exists("contacts.yaml"):
            _contacts = anymarkup.parse_file("contacts.yaml")
        else:
            # Get the contacts from bitbucket
            # Read in the config file with the SSH key location
            config = configparser.ConfigParser()
            config.read("config.ini")
            ssh_key = config['git']['ssh_key']
            # Create a temporary directory to store the contact information
            with tempfile.TemporaryDirectory() as tmp_dir:
                # From SO: https://stackoverflow.com/questions/4565700/specify-private-ssh-key-to-use-when-executing-shell-command
                cmd = "ssh-agent bash -c 'ssh-add {0}; git clone git@bitbucket.org:opensciencegrid/contact.git {1}'".format(ssh_key, tmp_dir)

                # I know this should be Popen or similar.  But.. I am unable to make that work.
                # I suspect it has something to do with the subshell that is being executed
                git_cmd = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if git_cmd != 0:
                    # Git command exited with nonzero!
                    pass
                _contacts = anymarkup.parse_file(os.path.join(tmp_dir, 'contacts.yaml'))

    return _contacts


def _getTopology():
    contacts = _getContacts()
    global _topology
    if not _topology:
        _topology = get_topology("topology", contacts)

    return _topology


if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

