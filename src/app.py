"""
Application File
"""
import flask
from flask import Flask, Response, request, render_template
import configparser
import tempfile
import anymarkup
import os
import re
import subprocess
import sys
import time
from typing import Dict, Set
import urllib.parse

from webapp import contacts_reader, project_reader, rg_reader, vo_reader
from webapp.common import to_xml_bytes, Filters
from webapp.contacts_reader import ContactsData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2, Topology
from webapp.vos_data import VOsData

import sys
print(sys.path)

class InvalidArgumentsError(Exception): pass

class DataError(Exception): pass


class CachedData:
    MAX_DATA_AGE = 60 * 15

    def __init__(self, data=None, timestamp=0, force_update=True):
        self.data = data
        self.timestamp = timestamp
        self.force_update = force_update

    def should_update(self):
        return self.force_update or (not self.data or time.time() - self.timestamp > self.MAX_DATA_AGE)

    def update(self, data):
        self.data = data
        self.timestamp = time.time()
        self.force_update = False


class GlobalData:
    contacts_data = CachedData()
    dn_set = CachedData()
    projects = CachedData()
    topology = CachedData()
    vos_data = CachedData()

    @classmethod
    def get_contacts_data(cls) -> ContactsData:
        """
        Get the contact information.  For now this is from a private github repo, but in the future
        it could be much more complicated to get the contact details
        """
        if cls.contacts_data.should_update():
            # use local copy if it exists
            if os.path.exists("../contacts.yaml"):
                filename = "../contacts.yaml"
            elif os.path.exists("/etc/opt/topology/config.ini") or os.path.exists("../config.ini"):
                # Get the contacts from bitbucket
                # Read in the config file with the SSH key location
                config = configparser.ConfigParser()
                config.read(["/etc/opt/topology/config.ini", "../config.ini"])
                ssh_key = config['git']['ssh_key']
                # Create a temporary directory to store the contact information
                with tempfile.TemporaryDirectory() as tmp_dir:
                    # From SO: https://stackoverflow.com/questions/4565700/specify-private-ssh-key-to-use-when-executing-shell-command
                    cmd = "ssh-agent bash -c 'ssh-add {0}; git clone git@bitbucket.org:opensciencegrid/contact.git {1}'".format(
                        ssh_key, tmp_dir)

                    # I know this should be Popen or similar.  But.. I am unable to make that work.
                    # I suspect it has something to do with the subshell that is being executed
                    git_result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                encoding="utf-8")
                    if git_result.returncode != 0:
                        # Git command exited with nonzero!
                        print("Git failed:\n" + git_result.stdout, file=sys.stderr)
                    filename = os.path.join(tmp_dir, 'contacts.yaml')
                    if not os.path.exists(filename):
                        raise DataError("contacts.yaml not found from git checkout")
            else:
                raise DataError("contacts.yaml or config.ini not found -- don't know where to get"
                                   " contacts data from")

            cls.contacts_data.update(contacts_reader.get_contacts_data(filename))

        return cls.contacts_data.data

    @classmethod
    def get_dns(cls) -> Set:
        """
        Get the set of DNs allowed to access "special" data (such as contact info)
        """
        if cls.dn_set.should_update():
            contacts_data = cls.get_contacts_data()
            cls.dn_set.update(set(contacts_data.get_dns()))
        return cls.dn_set.data

    @classmethod
    def get_topology(cls) -> Topology:
        if cls.topology.should_update():
            cls.topology.update(rg_reader.get_topology("../topology", cls.get_contacts_data()))
        return cls.topology.data

    @classmethod
    def get_vos_data(cls) -> VOsData:
        if cls.vos_data.should_update():
            cls.vos_data.update(vo_reader.get_vos_data("../virtual-organizations", cls.get_contacts_data()))
        return cls.vos_data.data

    @classmethod
    def get_projects(cls) -> Dict:
        if cls.projects.should_update():
            cls.projects.update(project_reader.get_projects("../projects"))
        return cls.projects.data


default_authorized = False

app = Flask(__name__)

@app.route('/')
def homepage():

    return """
    <h1>OSG Topology Interface</h1>
    <a href="https://github.com/opensciencegrid/topology">Source Repo</a><br/>
    <p>XML data:
        <ul>
            <li><a href="miscproject/xml?">Projects data</a></li>
            <li><a href="miscuser/xml?">User data (authorized users only)</a></li>
            <li><a href="rgsummary/xml?">Resource topology data</a></li>
            <li><a href="rgdowntime/xml?">Resource downtime data</a>
                (<a href="rgdowntime/xml?downtime_attrs_showpast=all">with past downtimes</a>)</li>
            <li><a href="vosummary/xml?">Virtual Organization data</a></li>
        </ul>
    </p>
    """

@app.route('/map/iframe')
def map():
    @app.template_filter()
    def encode(text):
        """Convert a partial unicode string to full unicode"""
        return text.encode('utf-8', 'surrogateescape').decode('utf-8')
    rgsummary = GlobalData.get_topology().get_resource_summary()

    return render_template('iframe.tmpl', resourcegroups=rgsummary["ResourceSummary"]["ResourceGroup"])


@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd", "miscproject.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


@app.route('/miscuser/xml')
def miscuser_xml():
    authorized = _get_authorized()

    if not authorized:
        return Response("Access denied: user cert not found or not accepted", status=403)
    return Response(to_xml_bytes(GlobalData.get_contacts_data().get_tree(authorized)), mimetype='text/xml')


@app.route('/miscproject/xml')
def miscproject_xml():
    projects_xml = to_xml_bytes(GlobalData.get_projects())
    return Response(projects_xml, mimetype='text/xml')


@app.route('/vosummary/xml')
def vosummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()
    vos_xml = to_xml_bytes(GlobalData.get_vos_data().get_tree(authorized, filters))
    return Response(vos_xml, mimetype='text/xml')


def get_filters_from_args(args) -> Filters:
    filters = Filters()
    def filter_value(filter_key):
        filter_value_key = filter_key + "_value"
        if filter_key in args:
            filter_value_str = args.get(filter_value_key, "")
            if filter_value_str == "0":
                return False
            elif filter_value_str == "1":
                return True
            else:
                raise InvalidArgumentsError("{0} must be 0 or 1".format(filter_value_key))
    filters.active = filter_value("active")
    filters.disable = filter_value("disable")
    filters.oasis = filter_value("oasis")

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
    if "service_hidden_value" in args:  # note no "service_hidden" args
        if args["service_hidden_value"] == "0":
            filters.service_hidden = False
        elif args["service_hidden_value"] == "1":
            filters.service_hidden = True
        else:
            raise InvalidArgumentsError("service_hidden_value must be 0 or 1")
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
    if "has_wlcg" in args:
        filters.has_wlcg = True

    # 2 ways to filter by a key like "facility", "service", "sc", "site", etc.:
    # - either pass KEY_1=on, KEY_2=on, etc.
    # - pass KEY_sel[]=1, KEY_sel[]=2, etc. (multiple KEY_sel[] args).
    for filter_key, filter_list, description in [
        ("facility", filters.facility_id, "facility ID"),
        ("rg", filters.rg_id, "resource group ID"),
        ("service", filters.service_id, "service ID"),
        ("sc", filters.support_center_id, "support center ID"),
        ("site", filters.site_id, "site ID"),
        ("vo", filters.vo_id, "VO ID"),
        ("voown", filters.voown_id, "VO owner ID"),
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

    if filters.voown_id:
        filters.populate_voown_name(GlobalData.get_vos_data().get_vo_id_to_name())

    return filters


@app.route('/rgsummary/xml')
def rgsummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()
    rgsummary = GlobalData.get_topology().get_resource_summary(authorized=authorized, filters=filters)
    return Response(to_xml_bytes(rgsummary), mimetype='text/xml')


@app.route('/rgdowntime/xml')
def rgdowntime_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()

    rgdowntime = GlobalData.get_topology().get_downtimes(authorized=authorized, filters=filters)
    return Response(to_xml_bytes(rgdowntime), mimetype='text/xml')


def _get_authorized():
    """
    Determine if the client is authorized

    returns: True if authorized, False otherwise
    """
    # Loop through looking for all of the creds
    for key, value in request.environ.items():
        if key.startswith('GRST_CRED_AURI_') and value.startswith("dn:"):

            # HTTP unquote the DN:
            client_dn = urllib.parse.unquote_plus(value)

            # Get list of authorized DNs
            authorized_dns = GlobalData.get_dns()

            # Authorized dns should be a set, or dict, that supports the "in"
            if client_dn[3:] in authorized_dns: # "dn:" is at the beginning of the DN
                return True     

    # If it gets here, then it is not authorized
    return default_authorized


if __name__ == '__main__':
    try:
        if sys.argv[1] == "--auth":
            default_authorized = True
    except IndexError: pass
    app.run(debug=True, use_reloader=True)
