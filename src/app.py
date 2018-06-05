"""
Application File
"""
import flask
import flask.logging
from flask import Flask, Response, request, render_template
import logging
import os
import re
import sys
import time
from typing import Dict, Set
import urllib.parse

from webapp import contacts_reader, project_reader, rg_reader, vo_reader, default_config
from webapp.common import git_clone_or_pull, to_xml_bytes, Filters
from webapp.contacts_reader import ContactsData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2, Topology
from webapp.vos_data import VOsData


class InvalidArgumentsError(Exception): pass

class DataError(Exception): pass


class CachedData:
    def __init__(self, data=None, timestamp=0, force_update=True, cache_lifetime=60*15):
        self.data = data
        self.timestamp = timestamp
        self.force_update = force_update
        self.cache_lifetime = cache_lifetime

    def should_update(self):
        return self.force_update or (not self.data or time.time() - self.timestamp > self.cache_lifetime)

    def update(self, data):
        self.data = data
        self.timestamp = time.time()
        self.force_update = False


def _verify_config(cfg):
    if not cfg["NO_GIT"]:
        ssh_key = cfg["GIT_SSH_KEY"]
        if not ssh_key:
            raise ValueError("GIT_SSH_KEY must be specified if using Git")
        elif not os.path.exists(ssh_key):
            raise FileNotFoundError(ssh_key)
        else:
            st = os.stat(ssh_key)
            if st.st_uid != os.getuid() or (st.st_mode & 0o7777) not in (0o700, 0o600, 0o400):
                raise PermissionError(ssh_key)


class GlobalData:
    def __init__(self, config):
        self.contacts_data = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.dn_set = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.projects = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.topology = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.vos_data = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.contacts_file = os.path.join(config["CONTACT_DATA_DIR"], "contacts.yaml")
        self.projects_dir = os.path.join(config["TOPOLOGY_DATA_DIR"], "projects")
        self.topology_dir = os.path.join(config["TOPOLOGY_DATA_DIR"], "topology")
        self.vos_dir = os.path.join(config["TOPOLOGY_DATA_DIR"], "virtual-organizations")
        self.config = config

    def _update_topology_repo(self):
        if not self.config["NO_GIT"]:
            parent = os.path.dirname(self.config["TOPOLOGY_DATA_DIR"])
            os.makedirs(parent, mode=0o755, exist_ok=True)
            ok = git_clone_or_pull(self.config["TOPOLOGY_DATA_REPO"], self.config["TOPOLOGY_DATA_DIR"],
                                   self.config["TOPOLOGY_DATA_BRANCH"])
            if ok:
                app.logger.debug("topology repo update ok")
            else:
                app.logger.warning("topology repo update failed")
        for d in [self.projects_dir, self.topology_dir, self.vos_dir]:
            if not os.path.exists(d):
                app.logger.error("%s not in topology repo", d)
                raise FileNotFoundError(d)

    def _update_contacts_repo(self):
        if not self.config["NO_GIT"]:
            parent = os.path.dirname(self.config["CONTACT_DATA_DIR"])
            os.makedirs(parent, mode=0o700, exist_ok=True)
            ok = git_clone_or_pull(self.config["CONTACT_DATA_REPO"], self.config["CONTACT_DATA_DIR"],
                                   self.config["CONTACT_DATA_BRANCH"], self.config["GIT_SSH_KEY"])
            if ok:
                app.logger.debug("contact repo update ok")
            else:
                app.logger.warning("contact repo update failed")
        if not os.path.exists(self.contacts_file):
            app.logger.error("%s not in contact repo", self.contacts_file)

    def get_contacts_data(self) -> ContactsData:
        """
        Get the contact information from a private git repo
        """
        if self.contacts_data.should_update():
            self._update_contacts_repo()
            self.contacts_data.update(contacts_reader.get_contacts_data(self.contacts_file))

        return self.contacts_data.data

    def get_dns(self) -> Set:
        """
        Get the set of DNs allowed to access "special" data (such as contact info)
        """
        if self.dn_set.should_update():
            contacts_data = self.get_contacts_data()
            self.dn_set.update(set(contacts_data.get_dns()))
        return self.dn_set.data

    def get_topology(self) -> Topology:
        if self.topology.should_update():
            self._update_topology_repo()
            self.topology.update(rg_reader.get_topology(self.topology_dir, self.get_contacts_data()))
        return self.topology.data

    def get_vos_data(self) -> VOsData:
        if self.vos_data.should_update():
            self._update_topology_repo()
            self.vos_data.update(vo_reader.get_vos_data(self.vos_dir, self.get_contacts_data()))
        return self.vos_data.data

    def get_projects(self) -> Dict:
        if self.projects.should_update():
            self._update_topology_repo()
            self.projects.update(project_reader.get_projects(self.projects_dir))
        return self.projects.data


default_authorized = False

app = Flask(__name__)
app.config.from_object(default_config)
app.config.from_pyfile("config.py", silent=True)
if "TOPOLOGY_CONFIG" in os.environ:
    app.config.from_envvar("TOPOLOGY_CONFIG", silent=False)
_verify_config(app.config)

global_data = GlobalData(app.config)


@app.route('/')
def homepage():

    return render_template('homepage.tmpl')

@app.route('/map/iframe')
def map():
    @app.template_filter()
    def encode(text):
        """Convert a partial unicode string to full unicode"""
        return text.encode('utf-8', 'surrogateescape').decode('utf-8')
    rgsummary = global_data.get_topology().get_resource_summary()

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
    return Response(to_xml_bytes(global_data.get_contacts_data().get_tree(authorized)), mimetype='text/xml')


@app.route('/miscproject/xml')
def miscproject_xml():
    projects_xml = to_xml_bytes(global_data.get_projects())
    return Response(projects_xml, mimetype='text/xml')


@app.route('/vosummary/xml')
def vosummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()
    vos_xml = to_xml_bytes(global_data.get_vos_data().get_tree(authorized, filters))
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
        filters.populate_voown_name(global_data.get_vos_data().get_vo_id_to_name())

    return filters


@app.route('/rgsummary/xml')
def rgsummary_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()
    rgsummary = global_data.get_topology().get_resource_summary(authorized=authorized, filters=filters)
    return Response(to_xml_bytes(rgsummary), mimetype='text/xml')


@app.route('/rgdowntime/xml')
def rgdowntime_xml():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)

    authorized = _get_authorized()

    rgdowntime = global_data.get_topology().get_downtimes(authorized=authorized, filters=filters)
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
            authorized_dns = global_data.get_dns()

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
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, use_reloader=True)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
