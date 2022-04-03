# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import collections
from requests import Session

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from resources.lib import settings

_per_page = settings.get_setting_int("general.commits_per_page")


class GithubAPI(Session):
    def __init__(self):
        super(GithubAPI, self).__init__()
        self.access_token = settings.get_setting_string("github.token")
        self.client_id = settings.get_setting_string("github.client_id")
        self.headers.update(
            {
                "Authorization": "Bearer {}".format(self.access_token),
                "Accept": "application/vnd.github.v3+json",
            }
        )
        self.base_url = "https://api.github.com/"
        self.auth_url = "https://github.com/login/"

    def _update_token(self):
        token = settings.get_setting_string("github.token")
        self.access_token = token
        self.headers.update({"Authorization": "Bearer {}".format(self.access_token)})

    def get(self, endpoint, **params):
        return super(GithubAPI, self).get(
            urljoin(self.base_url, endpoint), params=params
        )

    def get_pages(self, endpoint, pages=1, limit=30, **params):
        headers = self.headers.copy()
        headers.update({"per_page": str(limit)})

        for i in range(1, pages + 1):
            headers.update({"page": str(i)})
            response = super(GithubAPI, self).get(
                urljoin(self.base_url, endpoint), headers=headers, **params
            )
            yield response

    def get_pages_json(self, endpoint, pages=1, limit=30, **params):
        for page in self.get_pages(endpoint, pages, limit, **params):
            page = page.json()
            if isinstance(page, (list, set, collections.Sequence)):
                for item in page:
                    yield item
            else:
                yield page

    def get_all_pages(self, endpoint, **params):
        response = self.get(endpoint, **params)
        yield response
        while response.links.get("next", {}).get("url"):
            response = self.get(response.links.get("next", {}).get("url"))
            yield response

    def post(self, endpoint, *args, **params):
        return super(GithubAPI, self).post(
            urljoin(self.base_url, endpoint), *args, **params
        )

    def post_json(self, endpoint, data):
        return self.post(endpoint, json=data).json()

    def get_all_pages_json(self, endpoint, **params):
        for page in self.get_all_pages(endpoint, **params):
            page = page.json()
            if isinstance(page, (list, set, collections.Sequence)):
                for item in page:
                    yield item
            else:
                yield page

    def get_json(self, endpoint, **params):
        return self.get(endpoint, **params).json()

    def get_default_branch(self, user, repo):
        return self.get_json("repos/{}/{}".format(user, repo)).get("default_branch")

    def get_repo_branch(self, user, repo, branch):
        return self.get_json("repos/{}/{}/branches/{}".format(user, repo, branch))

    def get_repo_branches(self, user, repo):
        return self.get_all_pages_json("repos/{}/{}/branches".format(user, repo))

    def get_branch_commits(self, user, repo, branch):
        return self.get_pages_json(
            "repos/{}/{}/commits?sha={}".format(user, repo, branch), limit=_per_page
        )

    def raise_issue(self, user, repo, formatted_issue):
        return self.post_json("/repos/{}/{}/issues".format(user, repo), formatted_issue)

    def get_zipball(self, user, repo, branch):
        return self.get("/repos/{}/{}/zipball/{}".format(user, repo, branch)).content

    def get_commit_zip(self, user, repo, commit_sha):
        return self.get("{}/{}/archive/{}.zip".format(user, repo, commit_sha)).content

    def get_tree(self, user, repo, commit_sha="HEAD", recursive=False):
        if recursive == True:
            recursive = 'true'
        elif recursive == False:
            recursive = 'false'

        return self.get_json(
            "repos/{}/{}/git/trees/{}".format(user, repo, commit_sha),
            recursive=recursive,
        )

    def get_file(self, url):
        headers = self.headers.copy()
        headers.update({"Accept": "application/vnd.github.v3.raw"})
        response = super(GithubAPI, self).get(
            url,
            headers=headers,
        )
        if response.ok:
            return response.content

    def get_contents(self, user, repo, path="", raw=False):
        if raw:
            headers = self.headers.copy()
            headers.update({"Accept": "application/vnd.github.v3.raw"})
            response = super(GithubAPI, self).get(
                urljoin(
                    self.base_url, "/repos/{}/{}/contents/{}".format(user, repo, path)
                ),
                headers=headers,
            )
            if response.ok:
                return response.text
        else:
            return self.get_json("/repos/{}/{}/contents/{}".format(user, repo, path))

    def get_tags(self, user, repo):
        return self.get_all_pages_json("/repos/{}/{}/git/refs/tags".format(user, repo))

    def get_commit(self, user, repo, commit_sha):
        return self.get_json("/repos/{}/{}/commits/{}".format(user, repo, commit_sha))

    def get_user(self, user):
        return self.get_json("/users/{}".format(user))

    def get_username(self):
        self._update_token()
        return self.get_json("/user").get("login", "")

    def get_org_repos(self, org):
        return self.get_json("orgs/{}/repos".format(org))

    def get_user_repos(self, user):
        return self.get_json("/users/{}/repos".format(user))

    def get_repos(self, access=""):
        return self.get_all_pages_json("/user/repos?affiliation={}".format(access))

    def authorize(self, code=None):
        if not code:
            result = super(GithubAPI, self).post(
                urljoin(self.auth_url, "device/code"),
                data={"client_id": self.client_id, "scope": "repo read:user"},
                headers=self.headers,
            )

            return result.json()

        else:
            result = super(GithubAPI, self).post(
                urljoin(self.auth_url, "oauth/access_token"),
                data={
                    "client_id": self.client_id,
                    "device_code": code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers=self.headers,
            )

            return result.json()

    def revoke(self):
        return self.post(
            "applications/{}/grant".format(self.client_id),
            data={"access_token": self.access_token},
        ).ok
