"""
Application File
"""
import flask
import flask.logging
from   flask import Flask, Response, request
import glob
import hmac
import logging
import os
import re
import subprocess
from   subprocess import PIPE
import sys
import json

from webapp import default_config
from webapp import webhook_status_messages
from webapp.common import readfile
from webapp.github import GitHubAuth
from webapp.models import GlobalData
from webapp.automerge_check import reportable_errors, rejectable_errors


app = Flask(__name__)
app.config.from_object(default_config)
app.config.from_pyfile("config.py", silent=True)
if "TOPOLOGY_CONFIG" in os.environ:
    app.config.from_envvar("TOPOLOGY_CONFIG", silent=False)
if "LOGLEVEL" in app.config:
    app.logger.setLevel(app.config["LOGLEVEL"])

global_data = GlobalData(app.config)

src_dir = os.path.abspath(os.path.dirname(__file__))

( _required_repo_owner, _required_repo_name
) = global_data.webhook_data_repo.split(':')[-1].split('/')[-2:]

_required_base_ref = global_data.webhook_data_branch
_required_base_label = "%s:%s" % (_required_repo_owner, _required_base_ref)

webhook_secret = readfile(global_data.webhook_secret_key, app.logger)
if not webhook_secret:
    app.logger.warning("Note, no WEBHOOK_SECRET_KEY configured; "
                       "GitHub payloads will not be validated.")

gh_api_user = global_data.webhook_gh_api_user
gh_api_token = readfile(global_data.webhook_gh_api_token, app.logger).decode()
if gh_api_user and gh_api_token:
    ghauth = GitHubAuth(gh_api_user, gh_api_token, app.logger)
    ghrepo = ghauth.target_repo(_required_repo_owner, _required_repo_name)
    get_api_url           = ghauth.get_api_url
    publish_pr_review     = ghrepo.publish_pr_review
    publish_issue_comment = ghrepo.publish_issue_comment
    hit_merge_button      = ghrepo.hit_merge_button
else:
    get_api_url           = \
    publish_pr_review     = \
    publish_issue_comment = \
    hit_merge_button      = lambda *a,**kw: (False, "No API token configured")
    app.logger.warning("Note, no WEBHOOK_GH_API_TOKEN configured; "
                       "GitHub comments won't be published, nor PRs merged.")

def validate_webhook_signature(data, x_hub_signature):
    if webhook_secret:
        sha1 = hmac.new(webhook_secret, msg=data, digestmod='sha1').hexdigest()
        our_signature = "sha1=" + sha1
        return hmac.compare_digest(our_signature, x_hub_signature)

_max_payload_size = 1024 * 1024  # should be well under this
def validate_request_signature(request):
    if request.content_length > _max_payload_size:
        app.logger.error("Refusing to read overly-large payload of size %s"
                         % request.content_length)
        return False
    payload_body = request.get_data()
    x_hub_signature = request.headers.get('X-Hub-Signature')
    ret = validate_webhook_signature(payload_body, x_hub_signature)
    if ret or ret is None:
        return True  # OK, signature match or secret key not configured
    else:
        app.logger.error("Payload signature did not match for secret key")
        return False

def set_webhook_pr_state(num, sha, state):
    prdir = "%s/%s" % (global_data.webhook_state_dir, num)
    statefile = "%s/%s" % (prdir, sha)
    os.makedirs(prdir, mode=0o755, exist_ok=True)
    if isinstance(state, (tuple,list)):
        state = "\n".join( x.replace("\n"," ") for x in map(str,state) )
    with open(statefile, "w") as f:
        print(state, file=f)

def get_webhook_pr_state(sha, num='*'):
    prdir = "%s/%s" % (global_data.webhook_state_dir, num)
    statefile = "%s/%s" % (prdir, sha)
    def path_check(fn): return re.search(r'/\d+/[a-f\d]{40}$', fn)
    def pr_num(fn): return int(fn.rsplit('/', 2)[-2])
    if num == '*':
        filelist = glob.glob(statefile)
        filelist = list(filter(path_check, filelist))
        if len(filelist) == 0:
            return None, None
        # if there are multiple PRs with this sha, take the newest
        statefile = max(filelist, key=pr_num)
    if os.path.exists(statefile):
        with open(statefile) as f:
            return f.read().strip().split('\n'), pr_num(statefile)
    else:
        return None, None


def check_suite_validates_data(check_runs_url):
    TARGET_CHECK_RUN_NAME = "Validate Topology data"

    ok, resp = get_api_url(check_runs_url)
    if not ok:
        return False
    check_runs = json.load(resp).get("check_runs")
    if not isinstance(check_runs, list):
        return False

    for run in check_runs:
        if isinstance(run, dict) and run.get("name") == TARGET_CHECK_RUN_NAME:
            return True

    return False


@app.route("/check_suite", methods=["GET", "POST"])
def check_suite_hook():
    if not validate_request_signature(request):
        return Response("Bad X-Hub-Signature", status=400)

    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "check_suite":
        app.logger.debug("Ignoring non-check_suite hook of type '%s'" % event)
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    action = payload and payload.get('action')
    if action not in ("completed",):
        app.logger.info("Ignoring check_suite hook action '%s'" % action)
        return Response("Not Interested")
    try:
        check_suite = payload['check_suite']
        check_runs_url = check_suite['check_runs_url']
        head_sha = check_suite['head_sha']
        repo = payload['repository']
        owner = repo['owner']['login']          # 'opensciencegrid'
        reponame = repo['name']                 # 'topology'
        app_name = check_suite['app']['name']   # 'GitHub Actions'
        conclusion = check_suite['conclusion']  # 'success' ...
    except (TypeError, KeyError) as e:
        emsg = "Malformed payload for check_suite hook: %s" % e
        app.logger.error(emsg)
        return Response(emsg, status=400)
    app.logger.debug("Got check_suite hook '%s' for '%s'"
                     % (conclusion, head_sha))

    if app_name != 'GitHub Actions':
        app.logger.info("Ignoring non-GHA check_suite hook for '%s'"
                        % app_name)
        return Response("Not Interested; app_name was '%s'" % app_name)

    if owner != _required_repo_owner or reponame != _required_repo_name:
        app.logger.info("Ignoring check_suite hook repo '%s/%s'"
                        % (owner, reponame))
        return Response("Not Interested; repo was '%s/%s'" % (owner, reponame))

    if not check_suite_validates_data(check_runs_url):
        app.logger.info("Ignoring non-data check_suite hook for %s"
                        % check_runs_url)
        return Response("Not Interested; check_suite does not validate data")

    pr_webhook_state, pull_num = get_webhook_pr_state(head_sha)
    if pr_webhook_state is None or len(pr_webhook_state) != 4:
        app.logger.info("Got %s '%s' check_suite hook for commit %s;\n"
                "not merging as No PR automerge info available"
                % (app_name, conclusion, head_sha))
        return Response("No PR automerge info available for %s" % head_sha)

    pr_dt_automerge_ret, base_sha, head_label, sender = pr_webhook_state
    if re.search(r'^-?\d+$', pr_dt_automerge_ret):
        pr_dt_automerge_ret = int(pr_dt_automerge_ret)

    if pr_dt_automerge_ret == 0 and conclusion != 'success':
        if conclusion == 'action_required':
            osg_bot_msg = webhook_status_messages.ci_action_required
        else:
            osg_bot_msg = webhook_status_messages.ci_failure
        body = osg_bot_msg.format(**locals())
        publish_pr_review(pull_num, body, 'COMMENT', head_sha)

    if conclusion != 'success':
        app.logger.info("Ignoring %s '%s' check_suite hook" %
                        (app_name, conclusion))
        return Response("Not interested; check suite conclusion was '%s'"
                        % conclusion)

    if pr_dt_automerge_ret == 0:
        app.logger.info("Got %s success check_suite hook for commit %s;\n"
                "eligible for DT automerge" % (app_name, head_sha))
        body = None
        publish_pr_review(pull_num, body, 'APPROVE', head_sha)
        title = "Auto-merge Downtime PR #{pull_num} from {head_label}" \
                .format(**locals())
        ok, fail_message = hit_merge_button(pull_num, head_sha, title)
        if ok:
            osg_bot_msg = webhook_status_messages.merge_success
        else:
            osg_bot_msg = webhook_status_messages.merge_failure
        body = osg_bot_msg.format(**locals())
        publish_issue_comment(pull_num, body)
    else:
        app.logger.info("Got %s success check_suite hook for commit %s;\n"
                "not eligible for DT automerge" % (app_name, head_sha))

    return Response('Thank You')


@app.route("/pull_request", methods=["GET", "POST"])
def pull_request_hook():
    if not validate_request_signature(request):
        return Response("Bad X-Hub-Signature", status=400)

    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "pull_request":
        app.logger.debug("Ignoring non-pull_request hook of type '%s'" % event)
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    action = payload and payload.get('action')
    if action not in ("opened",):
        app.logger.info("Ignoring pull_request hook action '%s'" % action)
        return Response("Not Interested")
    # status=204 : No Content

    try:
        sender     = payload['sender']['login']

        head_sha   = payload['pull_request']['head']['sha']
        head_label = payload['pull_request']['head']['label']  # user:branch
        head_ref   = payload['pull_request']['head']['ref']    # branch

        base_sha   = payload['pull_request']['base']['sha']
        base_label = payload['pull_request']['base']['label']
        base_ref   = payload['pull_request']['base']['ref']

        pull_num   = payload['pull_request']['number']
        pull_url   = payload['pull_request']['html_url']
        title      = payload['pull_request']['title']

        mergeable  = payload['pull_request']['mergeable']
        if mergeable:
            merge_sha = payload['pull_request']['merge_commit_sha']
    except (TypeError, KeyError) as e:
        emsg = "Malformed payload for pull_request hook: %s" % e
        app.logger.error(emsg)
        return Response(emsg, status=400)
    app.logger.debug("Got pull_request hook for PR #{pull_num}"
                     " at {head_sha} on {head_label} onto {base_label}"
                     .format(**locals()))

    pull_ref   = "pull/{pull_num}/head".format(**locals())

    if base_label != _required_base_label:
        app.logger.info("Ignoring pull_request hook against '%s' "
                "('%s' is required)" % (base_label, _required_base_label))
        return Response("Not Interested")

    global_data.update_webhook_repo()

    script = src_dir + "/webapp/automerge_check.py"
    headmerge_sha = "%s:%s" % (head_sha, merge_sha) if mergeable else head_sha
    cmd = [script, base_sha, headmerge_sha, sender]
    stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)

    webhook_state = (ret, base_sha, head_label, sender)
    set_webhook_pr_state(pull_num, head_sha, webhook_state)

    # only comment on errors if DT files modified or contact unknown
    if ret in reportable_errors:
        osg_bot_msg = webhook_status_messages.automerge_status_messages[ret]
        body = osg_bot_msg.format(**locals())
        action = 'REQUEST_CHANGES' if ret in rejectable_errors else 'COMMENT'
        publish_pr_review(pull_num, body, action, head_sha)

    return Response('Thank You')


def runcmd(cmd, input=None, **kw):
    if input is None:
        stdin = None
    else:
        stdin = PIPE
    p = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=stdin,
                         encoding='utf-8', **kw)
    stdout, stderr = p.communicate(input)
    return stdout, stderr, p.returncode


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, use_reloader=True)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
