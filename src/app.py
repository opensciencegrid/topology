"""
Application File
"""
import csv
import flask
import flask.logging
from flask import Flask, Response, make_response, request, render_template
from io import StringIO
import logging
import os
import re
import sys
import traceback
import urllib.parse

from webapp import default_config
from webapp.common import readfile, to_xml_bytes, Filters
from webapp.forms import GenerateDowntimeForm
from webapp.models import GlobalData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2

try:
    import stashcache
except ImportError as e:
    stashcache = None
    print("*** Couldn't import stashcache", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("*** Continuing without authfile support", file=sys.stderr)


class InvalidArgumentsError(Exception): pass

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


default_authorized = False

app = Flask(__name__)
app.config.from_object(default_config)
app.config.from_pyfile("config.py", silent=True)
if "TOPOLOGY_CONFIG" in os.environ:
    app.config.from_envvar("TOPOLOGY_CONFIG", silent=False)
_verify_config(app.config)
if "AUTH" in app.config:
    if app.debug:
        default_authorized = app.config["AUTH"]
    else:
        print("ignoring AUTH option when FLASK_ENV != development", file=sys.stderr)
if not app.config.get("SECRET_KEY"):
    app.config["SECRET_KEY"] = "this is not very secret"
### Replace previous with this when we want to add CSRF protection
#     if app.debug:
#         app.config["SECRET_KEY"] = "this is not very secret"
#     else:
#         raise Exception("SECRET_KEY required when FLASK_ENV != development")
if "LOGLEVEL" in app.config:
    app.logger.setLevel(app.config["LOGLEVEL"])

global_data = GlobalData(app.config, strict=app.config.get("STRICT", app.debug))


cilogon_pass = readfile(global_data.cilogon_ldap_passfile, app.logger)
if not cilogon_pass:
    app.logger.warning("Note, no CILOGON_LDAP_PASSFILE configured; "
                       "OASIS Manager ssh key lookups will be unavailable.")


def _fix_unicode(text):
    """Convert a partial unicode string to full unicode"""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8')


@app.route('/')
def homepage():
    return render_template('homepage.html.j2')

@app.route('/map/iframe')
def map():
    rgsummary = global_data.get_topology().get_resource_summary()

    return _fix_unicode(render_template('iframe.html.j2', resourcegroups=rgsummary["ResourceSummary"]["ResourceGroup"]))


@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd", "miscproject.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


@app.route('/miscuser/xml')
def miscuser_xml():
    return Response(to_xml_bytes(global_data.get_contacts_data().get_tree(_get_authorized())),
                    mimetype='text/xml')


@app.route('/nsfscience/csv')
def nsfscience_csv():
    nsfscience = global_data.get_mappings().nsfscience
    if not nsfscience:
        return Response("Error getting Field of Science mappings", status=503)

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=",")
    writer.writerow(["Topology Field of Science", "NSF Field of Science"])
    writer.writerows(nsfscience.items())
    response = make_response(buffer.getvalue())
    response.headers.set("Content-Type", "text/csv")
    response.headers.set("Content-Disposition", "attachment", filename="nsfscience.csv")
    return response


@app.route('/contacts')
def contacts():
    try:
        authorized = _get_authorized()
        users_list = global_data.get_contacts_data().get_tree(_get_authorized())["Users"]["User"]
        return _fix_unicode(render_template('contacts.html.j2', users=users_list, authorized=authorized))
    except (KeyError, AttributeError):
        app.log_exception(sys.exc_info())
        return Response("Error getting users", status=503)  # well, it's better than crashing


@app.route('/miscproject/xml')
def miscproject_xml():
    return Response(to_xml_bytes(global_data.get_projects()), mimetype='text/xml')


@app.route('/vosummary/xml')
def vosummary_xml():
    return _get_xml_or_fail(global_data.get_vos_data().get_tree, request.args)


@app.route('/rgsummary/xml')
def rgsummary_xml():
    return _get_xml_or_fail(global_data.get_topology().get_resource_summary, request.args)


@app.route('/rgdowntime/xml')
def rgdowntime_xml():
    return _get_xml_or_fail(global_data.get_topology().get_downtimes, request.args)


@app.route('/rgdowntime/ical')
def rgdowntime_ical():
    try:
        filters = get_filters_from_args(request.args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)
    response = make_response(global_data.get_topology().get_downtimes_ical(False, filters).to_ical())
    response.headers.set("Content-Type", "text/calendar")
    response.headers.set("Content-Disposition", "attachment", filename="downtime.ics")
    return response


@app.route("/stashcache/authfile")
def authfile():
    return _get_cache_authfile(public_only=False)


@app.route("/stashcache/authfile-public")
def authfile_public():
    return _get_cache_authfile(public_only=True)


@app.route("/stashcache/origin-authfile-public")
def origin_authfile_public():
    return _get_origin_authfile(public_only=True)


@app.route("/stashcache/origin-authfile")
def origin_authfile():
    return _get_origin_authfile(public_only=False)


@app.route("/stashcache/scitokens")
def scitokens():
    if not stashcache:
        return Response("Can't get scitokens config: stashcache module unavailable", status=503)
    cache_fqdn = request.args.get("cache_fqdn")
    origin_fqdn = request.args.get("origin_fqdn")
    if not cache_fqdn and not origin_fqdn:
        return Response("FQDN of cache or origin server required in the 'cache_fqdn' or 'origin_fqdn' argument", status=400)

    try:
        if cache_fqdn:
            cache_scitokens = stashcache.generate_cache_scitokens(global_data.get_vos_data(),
                                                                global_data.get_topology().get_resource_group_list(),
                                                                fqdn=cache_fqdn,
                                                                suppress_errors=False)
            return Response(cache_scitokens, mimetype="text/plain")
        elif origin_fqdn:
            origin_scitokens = stashcache.generate_origin_scitokens(global_data.get_vos_data(),
                                                                global_data.get_topology().get_resource_group_list(),
                                                                fqdn=origin_fqdn,
                                                                suppress_errors=False)
            return Response(origin_scitokens, mimetype="text/plain")
    except stashcache.NotRegistered as e:
        return Response("# No resource registered for {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except stashcache.DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating scitokens config for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting scitokens config, please contact help@opensciencegrid.org", status=503)


def _get_cache_authfile(public_only):
    if not stashcache:
        return Response("Can't get authfile: stashcache module unavailable", status=503)
    cache_fqdn = request.args.get("cache_fqdn")
    try:
        if public_only:
            generate_function = stashcache.generate_public_cache_authfile
        else:
            generate_function = stashcache.generate_cache_authfile
        auth = generate_function(global_data.get_vos_data(),
                                 global_data.get_topology().get_resource_group_list(),
                                 fqdn=cache_fqdn,
                                 legacy=app.config["STASHCACHE_LEGACY_AUTH"],
                                 suppress_errors=False)
    except stashcache.NotRegistered as e:
        return Response("# No resource registered for {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except stashcache.DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating authfile for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting authfile, please contact help@opensciencegrid.org", status=503)
    return Response(auth, mimetype="text/plain")


def _get_origin_authfile(public_only):
    if not stashcache:
        return Response("Can't get authfile: stashcache module unavailable", status=503)
    if 'fqdn' not in request.args:
        return Response("FQDN of origin server required in the 'fqdn' argument", status=400)
    try:
        auth = stashcache.generate_origin_authfile(request.args['fqdn'],
                                                   global_data.get_vos_data(),
                                                   global_data.get_topology().get_resource_group_list(),
                                                   suppress_errors=False,
                                                   public_only=public_only)
    except stashcache.NotRegistered as e:
        return Response("# No resource registered for {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except stashcache.DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating authfile for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting authfile, please contact help@opensciencegrid.org", status=503)
    if not auth.strip():
        auth = """\
# No authorizations generated for this origin; please check configuration in OSG topology or contact help@opensciencegrid.org
"""
    return Response(auth, mimetype="text/plain")


@app.route("/generate_downtime", methods=["GET", "POST"])
def generate_downtime():
    form = GenerateDowntimeForm(request.form)

    def github_url(action, path):
        assert action in ("tree", "edit", "new"), "invalid action"
        base = global_data.topology_data_repo
        branch_q = urllib.parse.quote(global_data.topology_data_branch)
        path_q = urllib.parse.quote(path)
        param = f"?filename={path_q}" if action == "new" else f"/{path_q}"
        return f"{base}/{action}/{branch_q}{param}"

    github = False
    github_topology_root = ""
    if re.match("http(s?)://github.com", global_data.topology_data_repo):
        github = True
        github_topology_root = github_url("tree", "topology")

    def render_form(**kwargs):
        return render_template("generate_downtime_form.html.j2", form=form, infos=form.infos, github=github,
                               github_topology_root=github_topology_root, **kwargs)

    topo = global_data.get_topology()

    form.facility.choices = _make_choices(topo.resources_by_facility.keys(), select_one=True)
    facility = form.facility.data
    if facility not in topo.resources_by_facility:
        form.facility.data = ""
        form.resource.choices = [("", "-- Select a facility first --")]
        form.resource.data = ""
        form.services.choices = [("", "-- Select a facility and a resource first --")]
        return render_form()

    resource_choices = [("", "-- Select one --")]
    for r in topo.resources_by_facility[facility]:
        resource_choices.append((_fix_unicode(r.name),
                                 f"{_fix_unicode(r.name)} ({_fix_unicode(r.fqdn)})"))
    form.resource.choices = resource_choices

    if form.change_facility.data:  # "Change Facility" clicked
        form.resource.data = ""
        form.services.choices = [("", "-- Select a resource first --")]
        return render_form()

    resource = form.resource.data
    if resource not in topo.service_names_by_resource:
        return render_form()

    form.services.choices = _make_choices(topo.service_names_by_resource[resource])

    if form.change_resource.data:  # "Change Resource" clicked
        return render_form()

    if not form.validate_on_submit():
        return render_form()

    filepath = "topology/" + topo.downtime_path_by_resource[resource]
    # ^ filepath relative to the root of the topology repo checkout
    filename = os.path.basename(filepath)

    # Add github edit URLs or directory URLs for the repo, if we can.
    new_url = edit_url = site_dir_url = ""
    if github:
        site_dir_url = github_url("tree", os.path.dirname(filepath))
        if os.path.exists(os.path.join(global_data.topology_dir, topo.downtime_path_by_resource[resource])):
            edit_url = github_url("edit", filepath)
        else:
            new_url = github_url("new", filepath)

    form.yamloutput.data = form.get_yaml()

    return render_form(filepath=filepath, filename=filename,
                       edit_url=edit_url, site_dir_url=site_dir_url,
                       new_url=new_url)


def _make_choices(iterable, select_one=False):
    c = [(_fix_unicode(x), _fix_unicode(x)) for x in sorted(iterable)]
    if select_one:
        c.insert(0, ("", "-- Select one --"))
    return c


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
                raise InvalidArgumentsError("at least one {0} must be specified"
                                            " via the syntax <code>{1}_<b>ID</b>=on</code>"
                                            " or <code>{1}_sel[]=<b>ID</b></code>."
                                            " (These may be specified multiple times for multiple IDs.)"\
                                            .format(description, filter_key))

    if filters.voown_id:
        filters.populate_voown_name(global_data.get_vos_data().get_vo_id_to_name())

    return filters


def _get_xml_or_fail(getter_function, args):
    try:
        filters = get_filters_from_args(args)
    except InvalidArgumentsError as e:
        return Response("Invalid arguments: " + str(e), status=400)
    return Response(
        to_xml_bytes(getter_function(_get_authorized(), filters)),
        mimetype="text/xml"
    )


def _get_authorized():
    """
    Determine if the client is authorized

    returns: True if authorized, False otherwise
    """
    global app

    # Loop through looking for all of the creds
    for key, value in request.environ.items():
        if key.startswith('GRST_CRED_AURI_') and value.startswith("dn:"):

            # HTTP unquote the DN:
            client_dn = urllib.parse.unquote_plus(value)

            # Get list of authorized DNs
            authorized_dns = global_data.get_dns()

            # Authorized dns should be a set, or dict, that supports the "in"
            if client_dn[3:] in authorized_dns: # "dn:" is at the beginning of the DN
                if app and app.logger:
                    app.logger.info("Authorized %s", client_dn)
                return True
            else:
                if app and app.logger:
                    app.logger.debug("Rejected %s", client_dn)

    # If it gets here, then it is not authorized
    return default_authorized


if __name__ == '__main__':
    if "--auth" in sys.argv[1:]:
        default_authorized = True
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, use_reloader=True)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
