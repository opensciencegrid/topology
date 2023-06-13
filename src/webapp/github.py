import base64
import json
import re
import urllib.error
import urllib.request
import urllib.parse
import certifi

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


def http_to_dict(success, http_response, throw_error=True):
    """http json response to dict"""

    if success:
        return json.load(http_response.fp)

    if throw_error:

        if http_response == "Not Found":
            raise GithubNotFoundException(f"Request not successful: {http_response}")

        elif http_response == "Reference already exists":
            raise GithubReferenceExistsException

        else:
            raise GithubRequestException(f"Request not successful: {http_response}")

    return {}


class GithubRequestException(Exception):
    pass


class GithubNotFoundException(GithubRequestException):
    pass


class GithubReferenceExistsException(GithubRequestException):
    pass


class GithubUser:

    def __init__(self, name, email):
        self.name = name
        self.email = email

    @classmethod
    def from_token(cls, token):
        gh_auth = GitHubAuth(None, token)
        user_response = http_to_dict(*gh_auth.get_user())
        email_response = http_to_dict(*gh_auth.get_user_email())

        # Grab the first visible email to use, it doesn't matter
        visible_email = list(filter(lambda x: x['visibility'] != 'private', email_response))[0]['email']

        return cls(user_response["name"], visible_email)

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email
        }


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
        data = {
            'event': action,
            'commit_id': sha
        }
        if body is not None:
            data['body'] = body
        return self.github_api_call('POST', url, data)  # 200 OK

    def approve_pr(self, owner, repo, num, body, sha):
        return self.publish_pr_review(owner, repo, num, body, APPROVE, sha)

    def hit_merge_button(self, owner, repo, num, sha, title=None, msg=None):
        api_path = "/repos/:owner/:repo/pulls/:number/merge"
        url = api_path2url(api_path, owner=owner, repo=repo, number=num)
        data = {}
        if sha:    data['sha'] = sha
        if title:  data['commit_title'] = title
        if msg:    data['commit_message'] = msg
        return self.github_api_call('PUT', url, data)
        # 200 OK / 405 (not mergeable) / 409 (sha mismatch)

    def create_git_ref(self, owner, repo, ref, sha):
        """https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28#create-a-reference"""
        api_path = "/repos/:owner/:repo/git/refs"
        url = api_path2url(api_path, owner=owner, repo=repo)
        data = {
            "ref": ref,
            "sha": sha
        }
        return self.github_api_call('POST', url, data)

    def get_contents(self, owner, repo, path, ref=None):
        """https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#get-repository-content"""
        api_path = "/repos/:owner/:repo/contents/:path"
        url = api_path2url(api_path, owner=owner, repo=repo, path=path)
        data = {}
        if ref: data['ref'] = ref
        return self.github_api_call('GET', url, data)

    def get_branch(self, owner, repo, branch):
        """https://docs.github.com/en/rest/branches/branches?apiVersion=2022-11-28#get-a-branch"""
        api_path = "/repos/:owner/:repo/branches/:branch"
        url = api_path2url(api_path, owner=owner, repo=repo, branch=branch)

        return self.github_api_call("GET", url, None)

    def update_file(self, owner, repo, path, message, content, sha=None, branch=None, committer: GithubUser = None,
                    author: GithubUser = None):
        """https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#create-or-update-file-contents"""
        api_path = "/repos/:owner/:repo/contents/:path"
        url = api_path2url(api_path, owner=owner, repo=repo, path=path)
        data = {
            "message": message,
            "content": content
        }
        if sha: data['sha'] = sha
        if branch: data['branch'] = branch
        if committer: data['committer'] = committer.to_dict()
        if author: data['author'] = author.to_dict()

        return self.github_api_call("PUT", url, data)

    def create_pull(self, owner, repo, title, head, base, body=None, maintainer_can_modify: bool = None,
                    draft: bool = None, issue: int = None):
        """https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#create-a-pull-request"""
        api_path = "/repos/:owner/:repo/pulls"
        url = api_path2url(api_path, owner=owner, repo=repo)
        data = {
            "head": head,
            "base": base
        }
        if title: data['title'] = title
        if body: data['body'] = body
        if maintainer_can_modify: data['maintainer_can_modify'] = maintainer_can_modify
        if draft: data['draft'] = draft
        if issue: data['issue'] = issue

        return self.github_api_call("POST", url, data)

    def get_repo(self, owner, repo):
        """https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#get-a-repository"""
        api_path = "/repos/:owner/:repo"
        url = api_path2url(api_path, owner=owner, repo=repo)

        return self.github_api_call("GET", url, None)

    def get_user(self):
        """https://docs.github.com/en/rest/users/users?apiVersion=2022-11-28#get-the-authenticated-user"""
        api_path = "/user"
        url = api_path2url(api_path)

        return self.github_api_call("GET", url, None)

    def get_user_email(self):
        """https://docs.github.com/en/rest/users/emails?apiVersion=2022-11-28#list-email-addresses-for-the-authenticated-user"""
        api_path = "/user/emails"
        url = api_path2url(api_path)

        return self.github_api_call("GET", url, None)

    def get_api_url(self, url):
        return self.github_api_call('GET', url, None)

    def target_repo(self, owner, repo):
        return GitHubRepoAPI(self, owner, repo)


class GitHubRepoAPI:
    # wrapper around GitHubAuth with (owner,repo) specified up front

    def __init__(self, ghauth: GitHubAuth, owner, repo):
        self.ghauth = ghauth
        self.owner = owner
        self.repo = repo

        # Add place for Github Repo Data to be added if asked for
        self._repo_data = None

    def __getattr__(self, item):
        """If requested data isn't found locally see if Github has it"""
        if item in self.repo_data:
            return self.repo_data[item]

        return None

    @property
    def repo_data(self):
        if not self._repo_data:
            self._repo_data = http_to_dict(*self.get_repo())

        return self._repo_data

    def get_repo(self):
        return self.ghauth.get_repo(self.owner, self.repo)

    def publish_issue_comment(self, num, body):
        return self.ghauth.publish_issue_comment(self.owner, self.repo,
                                                 num, body)

    def publish_pr_review(self, num, body, action, sha):
        return self.ghauth.publish_pr_review(self.owner, self.repo,
                                             num, body, action, sha)

    def hit_merge_button(self, num, sha, title=None, msg=None):
        return self.ghauth.hit_merge_button(self.owner, self.repo,
                                            num, sha, title, msg)

    def create_git_ref(self, ref, sha):
        return self.ghauth.create_git_ref(self.owner, self.repo, ref=ref, sha=sha)

    def get_contents(self, path, ref=None):
        return self.ghauth.get_contents(self.owner, self.repo,
                                        path, ref)

    def update_file(self, path, message, content, sha=None, branch=None, committer: GithubUser = None,
                    author: GithubUser = None):
        return self.ghauth.update_file(self.owner, self.repo,
                                       path, message, content, sha, branch, committer, author)

    def create_pull(self, title, head, base, body=None, maintainer_can_modify=None, draft=None, issue=None):
        return self.ghauth.create_pull(self.owner, self.repo,
                                       title, head, base, body, maintainer_can_modify, draft, issue)

    def get_branch(self, branch):
        return self.ghauth.get_branch(self.owner, self.repo,
                                      branch)


def update_file_pr(
        file_path: str,
        file_content: str,
        branch: str,
        message: str,
        committer: GithubUser,
        root_repo: GitHubRepoAPI,
        fork_repo: GitHubRepoAPI
):
    """Creates a PR for an updated/new file from a repo fork to the root repository"""

    file_sha = None
    try:
        previous_contents_encoded = http_to_dict(*fork_repo.get_contents(file_path, ref=fork_repo.default_branch))

        previous_contents = base64.b64decode(previous_contents_encoded["content"]).decode("utf-8")
        file_content = f"{previous_contents}\n{file_content}"

        file_sha = previous_contents_encoded['sha']

    except GithubNotFoundException:
        pass

    return create_file_pr(file_path, file_content, branch, message, committer, root_repo, fork_repo, file_sha)


def create_file_pr(
        file_path: str,
        file_content: str,
        branch: str,
        message: str,
        committer: GithubUser,
        root_repo: GitHubRepoAPI,
        fork_repo: GitHubRepoAPI,
        file_sha: str = None,
):
    """Creates a PR for a new file from a repo fork to the root repository"""

    encoded_file_content = base64.b64encode(file_content.encode()).decode("utf-8")

    fork_default_branch = http_to_dict(*fork_repo.get_branch(root_repo.default_branch))

    create_ref_response = http_to_dict(*fork_repo.create_git_ref(
        ref=f"refs/heads/{branch}",
        sha=fork_default_branch['commit']['sha']
    ))

    update_file_response = http_to_dict(*fork_repo.update_file(file_path, message, encoded_file_content, sha=file_sha, branch=branch,
                                                 committer=committer))

    pull_response = http_to_dict(*root_repo.create_pull(
        title=message,
        head=f"{fork_repo.owner}:{branch}",
        base=root_repo.default_branch
    ))

    return pull_response
