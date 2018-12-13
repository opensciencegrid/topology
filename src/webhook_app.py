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

def _fix_unicode(text):
    """Convert a partial unicode string to full unicode"""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8')


@app.route("/pull_request", methods=["GET", "POST"])
def pull_request_hook():
    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "pull_request":
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    action = payload['action']
    if action not in ("opened", "edited", "reopened", "synchronize"):
        return Response("Not Interested")
    # status=204 : No Content

    sender     = payload['sender']['login']

    head_sha   = payload['pull_request']['head']['sha']
    head_label = payload['pull_request']['head']['label']
    head_ref   = payload['pull_request']['head']['ref']

    base_sha   = payload['pull_request']['base']['sha']
    base_label = payload['pull_request']['base']['label']
    base_ref   = payload['pull_request']['base']['ref']

    pull_num   = payload['pull_request']['number']
    pull_url   = payload['pull_request']['html_url']

    pull_ref   = "pull/{pull_num}/head".format(**locals())

    # make sure data repo contains relevant commits
    stdout, stderr, ret = fetch_data_ref(base_ref, pull_ref)

    if ret == 0:
        script = src_dir + "/tests/automerge_downtime_ok.py"
        cmd = [script, base_sha, head_sha, sender]
        stdout, stderr, ret = runcmd(cmd, cwd=global_data.topology_data_dir)

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

    recipients = [ x + "@cs.wisc.edu" for x in ("edquist", "matyas", "blin") ]
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
                  cwd=global_data.topology_data_dir)

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
