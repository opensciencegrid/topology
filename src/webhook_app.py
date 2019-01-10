"""
Application File
"""
import flask
import flask.logging
from flask import Flask, Response, request, render_template
import logging
import os
import re
import subprocess
from subprocess import PIPE
import sys
import urllib.parse

from webapp import default_config
from webapp.common import to_xml_bytes, Filters
from webapp.forms import GenerateDowntimeForm
from webapp.models import GlobalData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2


class InvalidArgumentsError(Exception): pass

def _verify_config(cfg):
    pass

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

global_data = GlobalData(app.config)

src_dir = os.path.abspath(os.path.dirname(__file__))

repo_owner, repo_name = global_data.webhook_data_repo.split('/')[-2:]

def _fix_unicode(text):
    """Convert a partial unicode string to full unicode"""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8')


'''
# some bash for ya

base_commit=24603d8a
head_commit=5021baa7

base_branch=master

new_sha=$(
  git commit-tree -p $base_commit -p $head_commit \
                  -m "auto-merge downtime x into $base_branch" \
                  refs/pull/98/merge^{tree}
) 

git push origin $new_sha:refs/heads/$base_branch
'''

# already checked in automerge test script
# might want to move the check here though, and pass in merge_sha
def commit_is_merged(ancestor_sha, head_sha):
    cmd = ['git', 'merge-base', '--is-ancestor', ancestor_sha, head_sha]
    stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)
    return ret == 0

def gen_merge_commit(base_sha, head_sha, message):
    # NB: we have already asserted: commit_is_merged(base_sha, head_sha)
    tree_rev = head_sha + "^{tree}"
    cmd = ['git', 'commit-tree', '-p', base_sha, '-p', head_sha,
                                 '-m', message, tree_rev]

    stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)
    return stdout.strip(), stderr, ret




@app.route("/status", methods=["GET", "POST"])
def status_hook():
    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "status":
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    sha = payload['sha']            # '02d565300874d691bfebada6929cbb7c9c1d8018'
    repo = payload['repository']    # { ... }
    owner = repo['owner']['login']  # 'opensciencegrid'
    reponame = repo['name']         # 'topology'
    context = payload['context']    # 'continuous-integration/travis-ci/push'
    target_url = payload.get('target_url')  # travis build url

    if (context != 'continuous-integration/travis-ci/push' or
            owner != repo_owner or reponame != repo_name):
        return Response("Not Interested")

    pr_dt_automerge_ret = global_data.get_webhook_pr_state(pull_num, head_sha)

    return Response('Thank You')


_required_base_label = 'opensciencegrid:master'

@app.route("/pull_request", methods=["GET", "POST"])
def pull_request_hook():
    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "pull_request":
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    action = payload['action']
    if action not in ("opened",):
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
    except (TypeError, KeyError) as e:
        return Response("Malformed payload: {0}".format(e), status=400)

    global_data._update_webhook_repo()

    mergeable  = payload['pull_request']['mergeable']
    if mergeable:
        merge_sha = payload['pull_request']['merge_commit_sha']

    pull_ref   = "pull/{pull_num}/head".format(**locals())

    if base_label != _required_base_label:
        return Response("Not Interested")

    global_data._update_webhook_repo()

    # make sure data repo contains relevant commits
    stdout, stderr, ret = fetch_data_ref(base_ref, pull_ref)

    if ret == 0:
        script = src_dir + "/tests/automerge_downtime_ok.py"
        cmd = [script, base_sha, head_sha, sender]
        stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)

    global_data.set_webhook_pr_state(pull_num, head_sha, ret)

    if ret == 0 and mergeable:
        new_merge_commit = gen_merge_commit(base_sha, head_sha, message)
        push_ref(new_merge_commit, base_ref)

    OK = "Yes" if ret == 0 else "No"

    subject = "Pull Request {pull_url} {action}".format(**locals())

    out = """\
In Pull Request: {pull_url}
GitHub User '{sender}' wants to merge branch {head_label}
        (at commit {head_sha})
into {base_label}
        (at commit {base_sha})

Eligible for downtime automerge? {OK}

automerge_downtime script output:
---
{stdout}
---
{stderr}
---
""".format(**locals())

    recipients = [
        "edquist@cs.wisc.edu",
        "matyas@cs.wisc.edu",
        "blin@cs.wisc.edu",
    ]

    if ret <= 2:
        _,_,_ = send_mailx_email(subject, out, recipients)

    return Response(out)


def runcmd(cmd, input=None, **kw):
    if input is None:
        stdin = None
    else:
        stdin = PIPE
    p = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=stdin,
                         encoding='utf-8', **kw)
    stdout, stderr = p.communicate(input)
    return stdout, stderr, p.returncode

def fetch_data_ref(*refs):
    return runcmd(['git', 'fetch', 'origin'] + list(refs),
                  cwd=global_data.webhook_data_dir)

def send_mailx_email(subject, body, recipients):
    return runcmd(["mailx", "-s", subject] + recipients, input=body)


if __name__ == '__main__':
    if "--auth" in sys.argv[1:]:
        default_authorized = True
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, use_reloader=True)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
