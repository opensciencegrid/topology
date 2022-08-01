import base64
import json
import re
import urllib.error
import urllib.request

api_baseurl = "https://api.github.com"

# review actions
APPROVE         = 'APPROVE'
REQUEST_CHANGES = 'REQUEST_CHANGES'
COMMENT         = 'COMMENT'


def mk_github_authstr(user, passwd):
    raw = '%s:%s' % (user, passwd)
    return base64.encodebytes(raw.encode()).decode().replace('\n', '')

def api_path2url(api_path, **kw):
    fmtstr = re.sub(r':([a-z]+)\b', r'{\1}', api_path)
    path = fmtstr.format(**kw)
    url = api_baseurl + path
    return url

class GitHubAuth:
    api_user = None
    api_token = None
    api_authstr = None
    logger = None

    def __init__(self, api_user, api_token, logger=None):
        self.api_user = api_user
        self.api_token = api_token
        self.api_authstr = mk_github_authstr(api_user, api_token)
        self.logger = logger

    def elog(self, msg):
        if self.logger:
            self.logger.error(msg)

    def dlog(self, msg):
        if self.logger:
            self.logger.debug(msg)

    def github_api_call(self, method, url, data):
        if data is not None:
            data = json.dumps(data).encode()
        req = urllib.request.Request(url, data, method=method)
        self._add_auth_header(req)
        #add_gh_preview_header(req)
        try:
            resp = urllib.request.urlopen(req)
            self.dlog("GitHub API call success for %s" % url)
            return True, resp
        except urllib.error.HTTPError as resp:
            status = resp.getheader('status')
            message = json.load(resp).get('message')
            self.elog("GitHub API call failure for %s; got %s: %s"
                      % (url, status, message))
            return False, message
        # status in resp.getcode()
        # resp headers in: resp.headers
        # resp body in resp.read() or json.load(resp)
        # for extended responses, follow resp.headers.getheader('link') -> next

    def _add_auth_header(self, req):
        req.add_header("Authorization", "Basic %s" % self.api_authstr)

    def publish_issue_comment(self, owner, repo, num, body):
        api_path = "/repos/:owner/:repo/issues/:number/comments"
        url = api_path2url(api_path, owner=owner, repo=repo, number=num)
        data = {'body': body}
        return self.github_api_call('POST', url, data)  # 201 Created

    def publish_pr_review(self, owner, repo, num, body, action, sha):
        # action: APPROVE, REQUEST_CHANGES, or COMMENT
        api_path = "/repos/:owner/:repo/pulls/:number/reviews"
        url = api_path2url(api_path, owner=owner, repo=repo, number=num)
        data = {'event': action, 'commit_id': sha}
        if body is not None:
            data['body'] = body
        return self.github_api_call('POST', url, data)  # 200 OK

    def approve_pr(self, owner, repo, num, body, sha):
        return self.publish_pr_review(owner, repo, num, body, APPROVE, sha)

    def hit_merge_button(self, owner, repo, num, sha, title=None, msg=None):
        api_path = "/repos/:owner/:repo/pulls/:number/merge"
        url = api_path2url(api_path, owner=owner, repo=repo, number=num)
        data = {}
        if sha:    data['sha']            = sha
        if title:  data['commit_title']   = title
        if msg:    data['commit_message'] = msg
        return self.github_api_call('PUT', url, data)
        # 200 OK / 405 (not mergeable) / 409 (sha mismatch)

    def get_api_url(url):
        return self.github_api_call('GET', url, None)

    def target_repo(self, owner, repo):
        return GitHubRepoAPI(self, owner, repo)

class GitHubRepoAPI:
    # wrapper around GitHubAuth with (owner,repo) specified up front

    def __init__(self, ghauth, owner, repo):
        self.ghauth = ghauth
        self.owner = owner
        self.repo = repo

    def publish_issue_comment(self, num, body):
        return self.ghauth.publish_issue_comment(self.owner, self.repo,
                                                 num, body)

    def publish_pr_review(self, num, body, action, sha):
        return self.ghauth.publish_pr_review(self.owner, self.repo,
                                        num, body, action, sha)

    def hit_merge_button(self, num, sha, title=None, msg=None):
        return self.ghauth.hit_merge_button(self.owner, self.repo,
                                       num, sha, title, msg)

