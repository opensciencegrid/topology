import base64
import re
import urllib.request

gh_api_baseurl = "https://api.github.com"

gh_api_user = None
gh_api_token = None
gh_api_authstr = None

def mk_github_authstr(user, passwd):
    return base64.encodestring('%s:%s' % (user,passwd)).replace('\n', '')

def api_setup(api_user, api_token):
    global gh_api_user
    global gh_api_token
    global gh_api_authstr
    gh_api_user = api_user
    gh_api_token = api_token
    gh_api_authstr = mk_github_authstr(gh_api_user, gh_api_token)

def github_api_call(method, url, data):
    req = urllib.request.Request(url, data)
    add_auth_header(req)
    add_gh_preview_header(req)
    req.get_method = lambda : method
    resp = urllib.request.urlopen(req)
    # resp headers in: resp.headers
    # resp body in resp.read()
    # for extended responses, follow resp.headers.getheader('link') -> next
    return resp

def add_auth_header(req):
    if gh_api_authstr:
        req.add_header("Authorization", "Basic %s" % gh_api_authstr)

def github_api_path2url(api_path, **kw):
    fmtstr = re.sub(r':([a-z]+)\b', r'{\1}', api_path)
    path = fmtstr.format(**kw)
    url = "%s/%s" % (gh_api_baseurl, path)
    return url

def publish_issue_comment(owner, repo, num, body):
    api_path = "/repos/:owner/:repo/issues/:number/comments"
    url = github_api_path2url(api_path, owner=owner, repo=repo, number=num)
    data = {'body': body}
    resp = github_api_call('POST', url, data)
    return resp

def publish_pr_review(owner, repo, num, body, action, sha):
    # action: APPROVE, REQUEST_CHANGES, or COMMENT
    api_path = "/repos/:owner/:repo/pulls/:number/reviews"
    url = github_api_path2url(api_path, owner=owner, repo=repo, number=num)
    data = {'body': body, 'event': action, commit_id: sha}
    resp = github_api_call('POST', url, data)
    return resp

