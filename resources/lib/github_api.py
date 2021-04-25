# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import collections
from requests import Session

from resources.lib import settings
from resources.lib import tools

_addon_name = settings.get_addon_info('name')


class GithubAPI(Session):

    def __init__(self):
        super(GithubAPI, self).__init__()
        self.access_token = settings.get_setting_string('github.token')
        self.client_id = settings.get_setting_string('github.client_id')
        self.headers.update({"Authorization": "Bearer {}".format(self.access_token),
                             "Accept": "application/vnd.github.v3+json"})
        self.base_url = 'https://api.github.com/'
        self.auth_url = 'https://github.com/login/'

    def get(self, endpoint, **params):
        return super(GithubAPI, self).get(tools.urljoin(self.base_url, endpoint), params=params)

    def get_all_pages(self, endpoint, **params):
        response = self.get(endpoint, **params)
        yield response
        while response.links.get('next', {}).get('url'):
            response = self.get(response.links.get('next', {}).get('url'))
            yield response

    def post(self, endpoint, *args, **params):
        return super(GithubAPI, self).post(tools.urljoin(self.base_url, endpoint), *args, **params)

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
        return self.get_json('repos/{}/{}'.format(user, repo)).get('default_branch', 'master')

    def get_repo_branch(self, user, repo, branch):
        return self.get_json('repos/{}/{}/branches/{}'.format(user, repo, branch))

    def get_repo_branches(self, user, repo):
        return self.get_all_pages_json('repos/{}/{}/branches'.format(user, repo))

    def get_branch_commits(self, user, repo, branch):
        return self.get_all_pages_json('repos/{}/{}/commits?sha={}'.format(user, repo, branch))

    def raise_issue(self, user, repo, formatted_issue):
        return self.post_json('/repos/{}/{}/issues'.format(user, repo), formatted_issue)

    def get_zipball(self, user, repo, branch):
        return self.get('/repos/{}/{}/zipball/{}'.format(user, repo, branch if branch != 'main' else '')).content

    def get_commit_zip(self, user, repo, commit_sha):
        return self.get('{}/{}/archive/{}.zip'.format(user, repo, commit_sha)).content

    def get_file(self, user, repo, path):
        self.headers.update({"Accept": "application/vnd.github.v3.raw"})
        return self.get_json('/repos/{}/{}/contents/{}'.format(user, repo, path))

    def get_tags(self, user, repo):
        return self.get_all_pages_json('/repos/{}/{}/git/refs/tags'.format(user, repo))

    def get_commit(self, user, repo, commit_sha):
        return self.get_json('/repos/{}/{}/git/commits/{}'.format(user, repo, commit_sha))

    def get_username(self):
        return self.get_json('/user').get('login', '')

    def authorize(self, code=None):
        if not code:
            result = super(GithubAPI, self).post(tools.urljoin(self.auth_url, 'device/code'),
                                data={'client_id': self.client_id, 'scope': 'repo read:user'},
                                headers=self.headers)
                                
            return result.json()
            
        else:
            result = super(GithubAPI, self).post(tools.urljoin(self.auth_url, 'oauth/access_token'),
                                data={'client_id': self.client_id,
                                      'device_code': code,
                                      'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'},
                                headers=self.headers)
                                        
            return result.json()
            
        return False

    def revoke(self):
        return self.post('applications/{}/grant'.format(self.client_id), data={"access_token": self.access_token}).ok