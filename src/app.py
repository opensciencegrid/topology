"""
Application File
"""
import csv
import flask
import flask.logging
from flask import Flask, Response, make_response, request, render_template, redirect, url_for, session
from io import StringIO
import logging
import os
import re
import sys
import traceback
import urllib.parse
import requests
from wtforms import ValidationError
from flask_wtf.csrf import CSRFProtect

from webapp import default_config
from webapp.common import readfile, to_xml_bytes, to_json_bytes, Filters, support_cors, simplify_attr_list, is_null, escape, cache_control_private
from webapp.exceptions import DataError, ResourceNotRegistered, ResourceMissingService
from webapp.forms import GenerateDowntimeForm, GenerateResourceGroupDowntimeForm, GenerateProjectForm
from webapp.models import GlobalData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2
from webapp.oasis_managers import get_oasis_manager_endpoint_info
from webapp.github import create_file_pr, update_file_pr, GithubUser, GitHubAuth, GitHubRepoAPI, GithubRequestException, GithubReferenceExistsException, GithubNotFoundException

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
                if cfg["IGNORE_SECRET_PERMS"]:
                    app.logger.info("Ignoring permissions/ownership issues on " + ssh_key)
                else:
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

if "LOGLEVEL" in app.config:
    app.logger.setLevel(app.config["LOGLEVEL"])

global_data = GlobalData(app.config, strict=app.config.get("STRICT", app.debug))

cilogon_pass = readfile(global_data.cilogon_ldap_passfile, app.logger)
if not cilogon_pass:
    app.logger.warning("Note, no CILOGON_LDAP_PASSFILE configured; "
                       "OASIS Manager ssh key lookups will be unavailable.")

ligo_pass = readfile(global_data.ligo_ldap_passfile, app.logger)
if not ligo_pass:
    app.logger.warning("Note, no LIGO_LDAP_PASSFILE configured; "
                       "LIGO DNs will be unavailable in authfiles.")

github_oauth_client_secret = readfile(global_data.github_oauth_client_secret, app.logger)
if not github_oauth_client_secret:
    app.logger.warning("Note, no GITHUB_OAUTH_CLIENT_SECRET configured; "
                       "Auto PRs will be unavailable.")
else:
    app.config['GITHUB_OAUTH_CLIENT_SECRET'] = github_oauth_client_secret.decode()

auto_pr_gh_api_user = readfile(global_data.auto_pr_gh_api_user, app.logger)
if not auto_pr_gh_api_user:
    app.logger.warning("Note, no AUTO_PR_GH_API_USER configured; "
                       "Auto PRs will be unavailable.")
else:
    app.config['AUTO_PR_GH_API_USER'] = auto_pr_gh_api_user.decode()

auto_pr_gh_api_token = readfile(global_data.auto_pr_gh_api_token, app.logger)
if not auto_pr_gh_api_token:
    app.logger.warning("Note, no AUTO_PR_GH_API_TOKEN configured; "
                       "Auto PRs will be unavailable.")
else:
    app.config['AUTO_PR_GH_API_TOKEN'] = auto_pr_gh_api_token.decode()

csrf_secret_key = readfile(global_data.csrf_secret_key, app.logger)
if (os.environ.get('TESTING', False) or app.debug) and not csrf_secret_key:
    app.config["SECRET_KEY"] = "this is not very secret"
elif not app.debug and not csrf_secret_key:
    raise Exception("SECRET_KEY required when FLASK_ENV != development")
else:
    app.config["SECRET_KEY"] = csrf_secret_key.decode()

csrf = CSRFProtect()
csrf.init_app(app)


def _fix_unicode(text):
    """Convert a partial unicode string to full unicode"""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8')

@app.after_request
def set_cache_control(response):
    if response.status_code == 200:
        # Cache results for 300s
        response.cache_control.max_age = 300
        # Serve an expired entry for up to 100s while refreshing in the background
        response.headers['Cache-Control'] += ', stale-while-revalidate=100'
    return response

@app.route('/')
def homepage():
    return render_template('homepage.html.j2')

@app.route('/map/iframe')
def map():
    rgsummary = global_data.get_topology().get_resource_summary()

    return _fix_unicode(render_template('iframe.html.j2', resourcegroups=rgsummary["ResourceSummary"]["ResourceGroup"]))

@app.route('/api/resource_group_summary')
def resource_summary():
    data = global_data.get_topology().get_resource_summary()["ResourceSummary"]["ResourceGroup"]

    return Response(
        to_json_bytes(simplify_attr_list(data, namekey='GroupName', del_name=False)),
        mimetype="application/json"
    )

@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd", "miscproject.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


@app.route('/miscuser/xml')
@cache_control_private
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


@app.route('/organizations')
def organizations():
    project_institution = global_data.get_mappings().project_institution
    if not project_institution:
        return Response("Error getting Project/Institution mappings", status=503)

    organizations = set()
    for project in global_data.get_projects()["Projects"]["Project"]:
        if "Organization" in project:
            organizations.add(project["Organization"])

    # Invert the Project/Institution mapping. Note that "institution" == "organization"
    # and "project" is actually the prefix for the project in our standard naming
    # convention.
    prefix_by_org = {pi[1]: pi[0] for pi in project_institution.items()}

    org_table = []
    for org in sorted(organizations):
        prefix = prefix_by_org.get(org, "")
        org_table.append((org, prefix))

    return _fix_unicode(render_template('organizations.html.j2', org_table=org_table))


@app.route('/resources')
def resources():

    return render_template("resources.html.j2")


@app.route('/collaborations')
def collaboration_list():

    return render_template("collaborations.html.j2")


@app.route("/collaborations/osg-scitokens-mapfile.conf")
def collaborations_scitoken_text():
    """Dumps output of /bin/get-scitokens-mapfile --regex at a text endpoint"""

    mapfile = ""
    all_vos_data = global_data.get_vos_data()

    for vo_name, vo_data in all_vos_data.vos.items():
        if is_null(vo_data, "Credentials", "TokenIssuers"):
            continue
        mapfile += f"## {vo_name} ##\n"
        for token_issuer in vo_data["Credentials"]["TokenIssuers"]:
            url = token_issuer.get("URL")
            subject = token_issuer.get("Subject", "")
            description = token_issuer.get("Description", "")
            pattern = ""
            if url:
                if subject:
                    pattern = f'/^{escape(url)},{escape(subject)}$/'
                else:
                    pattern = f'/^{escape(url)},/'
            unix_user = token_issuer.get("DefaultUnixUser")
            if description:
                mapfile += f"# {description}:\n"
            if pattern and unix_user:
                mapfile += f"SCITOKENS {pattern} {unix_user}\n"
            else:
                mapfile += f"# invalid SCITOKENS: {pattern or '<NO URL>'} {unix_user or '<NO UNIX USER>'}\n"

    if not mapfile:
        mapfile += "# No TokenIssuers found\n"

    return Response(mapfile, mimetype="text/plain")



@app.route('/contacts')
@cache_control_private
def contacts():
    try:
        authorized = _get_authorized()
        contacts_data = global_data.get_contacts_data().without_duplicates()
        users_list = contacts_data.get_tree(_get_authorized())["Users"]["User"]
        return Response(_fix_unicode(render_template('contacts.html.j2', users=users_list, authorized=authorized)))
    except (KeyError, AttributeError):
        app.log_exception(sys.exc_info())
        return Response("Error getting users", status=503)  # well, it's better than crashing


@app.route('/miscproject/xml')
def miscproject_xml():
    return Response(to_xml_bytes(global_data.get_projects()), mimetype='text/xml')


@app.route('/miscproject/json')
@support_cors
def miscproject_json():
    projects = simplify_attr_list(global_data.get_projects()["Projects"]["Project"], namekey="Name", del_name=False)
    return Response(to_json_bytes(projects), mimetype='application/json')


@app.route('/miscsite/json')
@support_cors
def miscsite_json():
    sites = {name: site.get_tree() for name, site in global_data.get_topology().sites.items()}
    return Response(to_json_bytes(sites), mimetype='application/json')


@app.route('/miscfacility/json')
@support_cors
def miscfacility_json():
    facilities = {name: facility.get_tree() for name, facility in global_data.get_topology().facilities.items()}
    return Response(to_json_bytes(facilities), mimetype='application/json')

@app.route('/miscresource/json')
@support_cors
def miscresource_json():
    resources = {}
    topology = global_data.get_topology()
    for rg in topology.rgs.values():
        for resource in rg.resources_by_name.values():
            resources[resource.name] = {
                "Name": resource.name,
                "Site": rg.site.name,
                "Facility": rg.site.facility.name,
                "ResourceGroup": rg.name,
                **resource.get_tree()
            }

    return Response(to_json_bytes(resources), mimetype='application/json')

@app.route('/vosummary/xml')
def vosummary_xml():
    return _get_xml_or_fail(global_data.get_vos_data().get_tree, request.args)

@app.route('/vosummary/json')
def vosummary_json():
    return Response(to_json_bytes(
        simplify_attr_list(global_data.get_vos_data().get_expansion(), namekey='Name')
    ), mimetype="application/json")


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

@app.route('/resources/stashcache-files')
@support_cors
def resources_stashcache_files():
    resource_files = {}
    topology = global_data.get_topology()
    for rg in topology.rgs.values():
        for resource in rg.resources_by_name.values():
            stashcache_files = resource.get_stashcache_files(global_data, app.config["STASHCACHE_LEGACY_AUTH"])

            if not stashcache_files:
                continue

            resource_files[resource.name] = {
                **stashcache_files
            }

    return Response(to_json_bytes(resource_files), mimetype='application/json')

@app.route("/resource-files")
def resource_files():

    return render_template("resource_files.html.j2")


@app.route("/cache/scitokens.conf")
def cache_scitokens():
    return _get_cache_scitoken_file()


@app.route("/origin/scitokens.conf")
def origin_scitokens():
    return _get_origin_scitoken_file()


@app.route("/cache/Authfile")
@app.route("/stashcache/authfile")
def authfile():
    return _get_cache_authfile(public_only=False)


@app.route("/cache/Authfile-public")
@app.route("/stashcache/authfile-public")
def authfile_public():
    return _get_cache_authfile(public_only=True)


@app.route("/cache/grid-mapfile")
@support_cors
def cache_grid_mapfile():
    assert stashcache
    fqdn = request.args.get("fqdn")
    if not fqdn:
        return Response("FQDN of cache server required in the 'fqdn' argument", status=400)
    try:
        return Response(stashcache.generate_cache_grid_mapfile(global_data, fqdn, suppress_errors=False),
                        mimetype="text/plain")
    except ResourceNotRegistered as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@osg-htc.org\n"
                        .format(e),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, e))
        return Response("# Error generating grid-mapfile for this FQDN:\n"
                        "# {}\n"
                        "# Please check configuration in OSG topology or contact help@osg-htc.org\n"
                        .format(e),
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting grid-mapfile, please contact help@osg-htc.org", status=503)


@app.route("/origin/Authfile")
@app.route("/stashcache/origin-authfile")
def origin_authfile():
    return _get_origin_authfile(public_only=False)


@app.route("/origin/Authfile-public")
@app.route("/stashcache/origin-authfile-public")
def origin_authfile_public():
    return _get_origin_authfile(public_only=True)


@app.route("/origin/grid-mapfile")
@support_cors
def origin_grid_mapfile():
    assert stashcache
    fqdn = request.args.get("fqdn")
    if not fqdn:
        return Response("FQDN of origin server required in the 'fqdn' argument", status=400)
    try:
        return Response(stashcache.generate_origin_grid_mapfile(global_data, fqdn, suppress_errors=False),
                        mimetype="text/plain")
    except ResourceNotRegistered as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@osg-htc.org\n"
                        .format(e),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, e))
        return Response("# Error generating grid-mapfile for this FQDN:\n"
                        "# {}\n"
                        "# Please check configuration in OSG topology or contact help@osg-htc.org\n"
                        .format(e),
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting grid-mapfile, please contact help@osg-htc.org", status=503)


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
            cache_scitokens = stashcache.generate_cache_scitokens(global_data, cache_fqdn, suppress_errors=False)
            return Response(cache_scitokens, mimetype="text/plain")
        elif origin_fqdn:
            origin_scitokens = stashcache.generate_origin_scitokens(global_data, origin_fqdn, suppress_errors=False)
            return Response(origin_scitokens, mimetype="text/plain")
    except ResourceNotRegistered as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating scitokens config for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting scitokens config, please contact help@opensciencegrid.org", status=503)


@app.route("/osdf/namespaces")
@app.route("/stashcache/namespaces")
@app.route("/stashcache/namespaces.json")  # for testing; remove before merging
@support_cors
def stashcache_namespaces_json():
    if not stashcache:
        return Response("Can't get scitokens config: stashcache module unavailable", status=503)
    try:
        return Response(to_json_bytes(stashcache.get_namespaces_info(global_data)),
                        mimetype='application/json')
    except ResourceNotRegistered as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating namespaces json file: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting namespaces json file, please contact help@opensciencegrid.org",
                        status=503)


@app.route("/oasis-managers/json")
@cache_control_private
def oasis_managers():
    if not _get_authorized():
        return Response("Not authorized", status=403)
    vo = request.args.get("vo")
    if not vo:
        return Response("'vo' argument is required", status=400)
    if not cilogon_pass:
        return Response("CILOGON_LDAP_PASSFILE not configured; "
                        "OASIS Managers info unavailable", status=503)
    mgrs = get_oasis_manager_endpoint_info(global_data, vo, cilogon_pass)
    return Response(to_json_bytes(mgrs), mimetype='application/json')


def _get_cache_authfile(public_only):
    if not stashcache:
        return Response("Can't get authfile: stashcache module unavailable", status=503)
    cache_fqdn = request.args.get("fqdn") if request.args.get("fqdn") else request.args.get("cache_fqdn")
    try:
        if public_only:
            generate_function = stashcache.generate_public_cache_authfile
        else:
            generate_function = stashcache.generate_cache_authfile
        auth = generate_function(global_data,
                                 fqdn=cache_fqdn,
                                 legacy=app.config["STASHCACHE_LEGACY_AUTH"],
                                 suppress_errors=False)
    except (ResourceNotRegistered, ResourceMissingService) as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except DataError as e:
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
        auth = stashcache.generate_origin_authfile(global_data=global_data, fqdn=request.args['fqdn'],
                                                   suppress_errors=False, public_origin=public_only)
    except (ResourceNotRegistered, ResourceMissingService) as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating authfile for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting authfile, please contact help@opensciencegrid.org", status=503)
    return Response(auth, mimetype="text/plain")


def _get_scitoken_file(fqdn, get_scitoken_function):

    if not stashcache:
        return Response("Can't get scitokens config: stashcache module unavailable", status=503)

    if not fqdn:
        return Response("FQDN of cache or origin server required in the 'fqdn' argument", status=400)

    try:
        scitoken_file = get_scitoken_function(fqdn)
        return Response(scitoken_file, mimetype="text/plain")

    except ResourceNotRegistered as e:
        return Response("# {}\n"
                        "# Please check your query or contact help@opensciencegrid.org\n"
                        .format(str(e)),
                        mimetype="text/plain", status=404)
    except DataError as e:
        app.logger.error("{}: {}".format(request.full_path, str(e)))
        return Response("# Error generating scitokens config for this FQDN: {}\n".format(str(e)) +
                        "# Please check configuration in OSG topology or contact help@opensciencegrid.org\n",
                        mimetype="text/plain", status=400)
    except Exception:
        app.log_exception(sys.exc_info())
        return Response("Server error getting scitokens config, please contact help@opensciencegrid.org", status=503)


def _get_cache_scitoken_file():
    fqdn_arg = request.args.get("fqdn")

    def get_scitoken_function(fqdn):
        return stashcache.generate_cache_scitokens(global_data=global_data, fqdn=fqdn, suppress_errors=False)

    return _get_scitoken_file(fqdn_arg, get_scitoken_function)


def _get_origin_scitoken_file():
    fqdn_arg = request.args.get("fqdn")

    def get_scitoken_function(fqdn):
        return stashcache.generate_origin_scitokens(global_data=global_data, fqdn=fqdn, suppress_errors=False)

    return _get_scitoken_file(fqdn_arg, get_scitoken_function)


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

@app.route("/generate_resource_group_downtime", methods=["GET", "POST"])
def generate_resource_group_downtime():
    form = GenerateResourceGroupDowntimeForm(request.form)

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
        return render_template("generate_resource_group_downtime_form.html.j2", form=form, infos=form.infos, github=github,
                               github_topology_root=github_topology_root, **kwargs)

    topo = global_data.get_topology()

    form.facility.choices = _make_choices(topo.sites_by_facility.keys(), select_one=True)
    facility = form.facility.data
    if form.change_facility.data:

        # If valid facility
        if facility in topo.sites_by_facility:
            form.site.choices = _make_choices(topo.sites_by_facility[facility], True)
            form.site.data = ""
            form.resource_group.choices = [("", "-- Select a site first --")]
            form.resource_group.data = ""

        else:
            form.facility.data = ""
            form.site.choices = [("", "-- Select a facility first --")]
            form.site.data = ""
            form.resource_group.choices = [("", "-- Select a facility and site first --")]
            form.resource_group.data = ""

        return render_form()

    form.site.choices = _make_choices(topo.sites_by_facility[facility], True)
    site = form.site.data
    if form.change_site.data:

        # If valid site
        if site in topo.sites_by_facility[facility]:
            form.resource_group.choices = _make_choices(topo.resource_group_by_site[site], True)
            form.resource_group.data = ""

        else:
            form.site.choices = _make_choices(topo.sites_by_facility[facility], True)
            form.site.data = ""
            form.resource_group.choices = [("", "-- Select a site first --")]
            form.resource_group.data = ""

        return render_form()

    form.resource_group.choices = _make_choices(topo.resource_group_by_site[site], True)
    resource_group = form.resource_group.data
    if form.change_resource_group.data:

        if resource_group not in topo.resource_group_by_site[site]:
            form.resource_group.choices = _make_choices(topo.resource_group_by_site[site], True)
            form.resource_group.data = ""

        return render_form()

    if not form.validate_on_submit():
        return render_form()

    resources = sorted(topo.resources_by_resource_group[resource_group])

    filepath = "topology/" + topo.downtime_path_by_resource[resources[0]]
    # ^ filepath relative to the root of the topology repo checkout
    filename = os.path.basename(filepath)

    # Add github edit URLs or directory URLs for the repo, if we can.
    new_url = edit_url = site_dir_url = ""
    if github:
        site_dir_url = github_url("tree", os.path.dirname(filepath))
        if os.path.exists(os.path.join(global_data.topology_dir, topo.downtime_path_by_resource[resources[0]])):
            edit_url = github_url("edit", filepath)
        else:
            new_url = github_url("new", filepath)

    form.yamloutput.data = form.get_yaml(resources=resources,
                                         service_names_by_resource=topo.service_names_by_resource)

    return render_form(filepath=filepath, filename=filename,
                       edit_url=edit_url, site_dir_url=site_dir_url,
                       new_url=new_url)


@app.route("/generate_project_yaml", methods=["GET", "POST"])
def generate_project_yaml():

    def render_form(**kwargs):
        institutions = list(global_data.get_mappings().project_institution.items())
        session.pop("form_data", None)

        return render_template("generate_project_yaml.html.j2", form=form, infos=form.infos, institutions=institutions, **kwargs)

    def validate_project_name(form, field):
        project_names = set(x['Name'] for x in global_data.get_projects()['Projects']['Project'])
        if field.data in project_names:
            raise ValidationError(f"{field.data} is already registered in OSG Topology. ")

    form = GenerateProjectForm(request.form, **request.args, **session.get("form_data", {}))
    form.field_of_science.choices = _make_choices(global_data.get_mappings().nsfscience.keys(), select_one=True)

    # Add this validator if it is not their
    if not len(form.project_name.validators) > 1:
        form.project_name.validators.append(validate_project_name)

    # If they have returned after logging into Github make the Submission button stand out
    if "github_login" in session:
        form.auto_submit.label.text = "Submit Automatically"
        form.auto_submit.render_kw = {
            "class": "btn btn-warning"
        }

    # Report any external errors
    if "error" in request.args:
        return render_form(error=request.args['error'])

    # Anything past this point needs a valid form
    if not form.validate_on_submit():
        return render_form()

    # If the user has their Github verified
    if request.method == "POST" and "github_login" in session and "auto_submit" in request.form:

        try:
            # Gather necessary data
            create_pr_response = create_file_pr(
                file_path=f"data/{request.values['project_name']}.yaml",
                file_content=form.get_yaml(),
                branch=f"add-project-{request.values['project_name']}",
                message=f"Add Project {request.values['project_name']}",
                committer=GithubUser.from_token(session["github_login"]['access_token']),
                fork_repo=GitHubAuth(
                    app.config["AUTO_PR_GH_API_USER"],
                    app.config["AUTO_PR_GH_API_TOKEN"]
                ).target_repo(app.config["AUTO_PR_GH_API_USER"], 'topology'),
                root_repo=GitHubAuth(
                    app.config["AUTO_PR_GH_API_USER"],
                    app.config["AUTO_PR_GH_API_TOKEN"]
                ).target_repo('opensciencegrid', 'topology'),
            )

            form.clear()

            return render_form(pr_url=create_pr_response['html_url'])

        except GithubReferenceExistsException as error:
            return render_form(error="A Pull-Request for this project already exists, change Project Name and try again.")

        except GithubRequestException as error:
            return render_form(error="Unexpected Error: Please submit manually.")

    # Start Github Oauth Flow
    if request.method == "POST" and "auto_submit" in request.form:

        session['form_data'] = form.as_dict()
        return redirect(f"/github/login?scope=user:email read:user")

    # Generate the yaml for manual addition
    if request.method == "POST" and "manual_submit" in request.form:

        form.yaml_output.data = form.get_yaml()
        return render_form(form_complete=True)

    return render_form()


@app.route("/github/login", methods=["GET"])
def github_login():
    """Used to login to Github and return to previous location"""

    if "code" in request.args:
        if request.args['state'] != session.pop("state"):
            return Response("Github returned incorrect state. Try again or email support@osg-htc.org for support.", 401)

        data = {
            "code": request.args['code'],
            "client_id": "2bf9c248a619961eb14a",
            "client_secret": app.config["GITHUB_OAUTH_CLIENT_SECRET"],
            "redirect_uri": request.args['redirect_uri']
        }

        redirect_data = {}
        try:
            response = requests.post("https://github.com/login/oauth/access_token", data=data, headers={"Accept": "application/json"})
            session['github_login'] = response.json()

        except Exception as error:
            redirect_data['error'] = f"Could not complete exchange with Github for Token: {error}"

        redirect_url = urllib.parse.urlparse(request.args['redirect_uri']).geturl()
        urlencoded_redirect_data = urllib.parse.urlencode(redirect_data)

        return redirect(f"{redirect_url}?{urlencoded_redirect_data}")

    else:
        session['state'] = os.urandom(24).hex()

        params = {
            "client_id": "2bf9c248a619961eb14a",
            "redirect_uri": f"{request.url_root[:-1]}{url_for('github_login')}?redirect_uri={request.environ.get('HTTP_REFERER')}",
            "scope": request.args['scope'],
            "state": session['state']
        }

        AUTH_URL = "https://github.com/login/oauth/authorize"

        return redirect(f"{AUTH_URL}?{urllib.parse.urlencode(params)}", code=303)


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
    app.run(debug=True, use_reloader=True, port=9000)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
