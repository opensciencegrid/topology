"""
Application File
"""
import flask
import flask.logging
from flask import Flask, Response, request, render_template
import glob
import hmac
import logging
import os
import re
import subprocess
from subprocess import PIPE
import sys
import urllib.parse

from webapp import default_config
from webapp.common import to_xml_bytes, Filters, run_git_cmd
from webapp.forms import GenerateDowntimeForm
from webapp.models import GlobalData
from webapp.topology import GRIDTYPE_1, GRIDTYPE_2


class InvalidArgumentsError(Exception): pass

def _verify_config(cfg):
    global ssh_key
    if not cfg["NO_GIT"]:
        ssh_key = cfg["GIT_SSH_KEY"]
        if not ssh_key:
            raise ValueError("GIT_SSH_KEY must be specified if using Git")
        elif not os.path.exists(ssh_key):
            raise FileNotFoundError(ssh_key)
        else:
            st = os.stat(ssh_key)
            perm_ok = st.st_mode & 0o400 and not st.st_mode & 0o7077
            if st.st_uid != os.getuid() or not perm_ok:
                raise PermissionError(ssh_key)

app = Flask(__name__)
app.config.from_object(default_config)
app.config.from_pyfile("config.py", silent=True)
if "TOPOLOGY_CONFIG" in os.environ:
    app.config.from_envvar("TOPOLOGY_CONFIG", silent=False)
_verify_config(app.config)
if "LOGLEVEL" in app.config:
    app.logger.setLevel(app.config["LOGLEVEL"])

global_data = GlobalData(app.config)

src_dir = os.path.abspath(os.path.dirname(__file__))

( _required_repo_owner, _required_repo_name
) = global_data.webhook_data_repo.split(':')[-1].split('/')[-2:]

_required_base_ref = global_data.webhook_data_branch
_required_base_label = "%s:%s" % (_required_repo_owner, _required_base_ref)

def _fix_unicode(text):
    """Convert a partial unicode string to full unicode"""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8')

def _readfile(path):
    """ return stripped file contents, or None on errors """
    if path:
        try:
            with open(path, mode="rb") as f:
                return f.read().strip()
        except IOError as e:
            app.logger.error("Failed to read file '%s': %s" % (path, e))
            return None

webhook_secret = _readfile(global_data.webhook_secret_key)
if not webhook_secret:
    app.logger.warning("Note, no WEBHOOK_SECRET_KEY configured; "
                       "GitHub payloads will not be validated.")

def validate_webhook_signature(data, x_hub_signature):
    if webhook_secret:
        sha1 = hmac.new(webhook_secret, msg=data, digestmod='sha1').hexdigest()
        our_signature = "sha1=" + sha1
        return hmac.compare_digest(our_signature, x_hub_signature)

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

# already checked in automerge test script
# might want to move the check here though, and pass in merge_sha
def commit_is_merged(ancestor_sha, head_sha):
    cmd = ['git', 'merge-base', '--is-ancestor', ancestor_sha, head_sha]
    stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)
    return ret == 0

_git_user_name = "Topology Automerge"
_git_user_email = "help@opensciencegrid.org"
def gen_merge_commit(base_sha, head_sha, message):
    # NOTE: we've already checked this in automerge test script
    if not commit_is_merged(base_sha, head_sha):
        return '', 'commit %s is not merged into %s' % (base_sha, head_sha), 1
    tree_rev = head_sha + "^{tree}"
    cmd = ['git', '-c', 'user.name=%s'  % _git_user_name,
                  '-c', 'user.email=%s' % _git_user_email,
                  'commit-tree', '-p', base_sha, '-p', head_sha,
                                 '-m', message, tree_rev]
    return runcmd(cmd, cwd=global_data.webhook_data_dir)

def push_ref(sha, remote_ref):
    refspec = "%s:refs/heads/%s" % (sha, remote_ref)
    gitcmd = ['push', 'origin', refspec]
    app.logger.info("Pushing downtime automerge commit %s to branch '%s'"
                    % (sha, remote_ref))
    return run_git_cmd(gitcmd, git_dir=global_data.webhook_data_dir,
                       ssh_key=ssh_key)

def do_automerge(base_sha, head_sha, message, base_ref):
    out, err, ret = gen_merge_commit(base_sha, head_sha, message)
    if ret != 0:
        app.logger.error("Failed to generate merge commit of %s onto %s"
                         % (head_sha, base_sha))
        return False
    new_merge_commit = out.strip()

    # for now, send all-clear email rather than actually pushing upstream
    subject = "[DT-AM] Downtime Automerge Approved"
    body = ("Downtime PR eligible for automerge and Status check passed:"
            "\n\n%s" % message)
    send_mailx_email(subject, body)
    return push_ref(new_merge_commit, base_ref)

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

@app.route("/status", methods=["GET", "POST"])
def status_hook():
    if not validate_request_signature(request):
        return Response("Bad X-Hub-Signature", status=400)

    event = request.headers.get('X-GitHub-Event')
    if event == "ping":
        return Response('Pong')
    elif event != "status":
        app.logger.debug("Ignoring non-status hook of type '%s'" % event)
        return Response("Wrong event type", status=400)

    payload = request.get_json()
    try:
        head_sha = payload['sha']
        repo = payload['repository']
        owner = repo['owner']['login'] # 'opensciencegrid'
        reponame = repo['name']        # 'topology'
        context = payload['context']   # 'continuous-integration/travis-ci/push'
        ci_state = payload['state']    # 'success' ...
        target_url = payload.get('target_url')  # travis build url
    except (TypeError, KeyError) as e:
        emsg = "Malformed payload for status hook: %s" % e
        app.logger.error(emsg)
        return Response(emsg, status=400)
    app.logger.debug("Got status hook '%s' for '%s'" % (ci_state, head_sha))

    valid_contexts = ( 'continuous-integration/travis-ci/pr',
                       'continuous-integration/travis-ci/push' )
    if context not in valid_contexts:
        app.logger.info("Ignoring non-travis status hook for '%s'" % context)
        return Response("Not Interested; context was '%s'" % context)

    if owner != _required_repo_owner or reponame != _required_repo_name:
        app.logger.info("Ignoring status hook repo '%s/%s'"
                        % (owner, reponame))
        return Response("Not Interested; repo was '%s/%s'" % (owner, reponame))

    if ci_state != 'success':
        app.logger.info("Ignoring travis '%s' status hook" % ci_state)
        return Response("Not interested; CI state was '%s'" % ci_state)

    pr_webhook_state, pull_num = get_webhook_pr_state(head_sha)
    if pr_webhook_state is None or len(pr_webhook_state) != 4:
        app.logger.info("Got travis success status hook for commit %s;\n"
                "not merging as No PR automerge info available" % head_sha)
        return Response("No PR automerge info available for %s" % head_sha)

    pr_dt_automerge_ret, base_sha, head_label, pr_title = pr_webhook_state
    base_ref = _required_base_ref
    if re.search(r'^-?\d+$', pr_dt_automerge_ret):
        pr_dt_automerge_ret = int(pr_dt_automerge_ret)

    if pr_dt_automerge_ret == 0 and not app.config['NO_GIT']:
        app.logger.info("Got travis success status hook for commit %s;\n"
                "eligible for DT automerge" % head_sha)
        message = "Auto-merge Downtime PR #{pull_num} from {head_label}" \
                  "\n\n{pr_title}".format(**locals())
        ok = do_automerge(base_sha, head_sha, message, base_ref)
    elif pr_dt_automerge_ret != 0:
        app.logger.info("Got travis success status hook for commit %s;\n"
                "not eligible for DT automerge" % head_sha)
    else:
        app.logger.info("Got travis success status hook for commit %s;\n"
                "eligible for DT automerge, but not merging since NO_GIT "
                "is configured" % head_sha)

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
    action = payload['action']
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

    script = src_dir + "/tests/automerge_downtime_ok.py"
    headmerge_sha = "%s:%s" % (head_sha, merge_sha) if mergeable else head_sha
    cmd = [script, base_sha, headmerge_sha, sender]
    stdout, stderr, ret = runcmd(cmd, cwd=global_data.webhook_data_dir)

    webhook_state = (ret, base_sha, head_label, title)
    set_webhook_pr_state(pull_num, head_sha, webhook_state)

    OK = "Yes" if ret == 0 else "No"
    Eligible = "Eligible!" if ret == 0 else "Not Eligible."

    subject = "[DT-AM] PR #{pull_num} {action}: {Eligible}".format(**locals())

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

    # only send email if DT files modified or contact unknown
    if ret <= 2:
        _,_,_ = send_mailx_email(subject, out)

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

def send_mailx_email(subject, body):
    recipients = [
        "edquist@cs.wisc.edu",
        "matyas@cs.wisc.edu",
        "blin@cs.wisc.edu",
    ]
    app.logger.info("Sending email to %s, Re: %s" % (recipients, subject))
    return runcmd(["mailx", "-s", subject] + recipients, input=body)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, use_reloader=True)
else:
    root = logging.getLogger()
    root.addHandler(flask.logging.default_handler)
