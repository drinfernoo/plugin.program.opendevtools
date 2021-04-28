# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import os
import re
import shutil
import sys
import time
import zipfile

import xbmcgui
import xbmcvfs

from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI
from resources.lib.thread_pool import ThreadPool

API = GithubAPI()

_addon_name = settings.get_addon_info('name')

_color = settings.get_setting_string('general.color')
_compact = settings.get_setting_boolean('general.compact')

_home = tools.translate_path('special://home')
_addons = os.path.join(_home, 'addons')
_temp = tools.translate_path('special://temp')
_addon_path = tools.translate_path(settings.get_addon_info('path'))
_addon_data = tools.translate_path(settings.get_addon_info('profile'))

_media_path = os.path.join(_addon_path, 'resources', 'media')


def _get_branch_zip_file(github_user, github_repo, github_branch):
    return _store_zip_file(API.get_zipball(github_user, github_repo, github_branch))


def _store_zip_file(zip_contents):
    zip_location = os.path.join(_addon_data, "{}.zip".format(int(time.time())))
    tools.write_all_text(zip_location, zip_contents)

    return zip_location


def _remove_folder(path):
    if xbmcvfs.exists(tools.ensure_path_is_dir(path)):
        tools.log("Removing {}".format(path))
        try:
            shutil.rmtree(path)
        except Exception as e:
            tools.log("Error removing {}: {}".format(path, e))


def _remove_file(path):
    if xbmcvfs.exists(path):
        tools.log("Removing {}".format(path))
        try:
            os.remove(path)
        except Exception as e:
            tools.log("Error removing {}: {}".format(path, e))


def _extract_addon(zip_location, addon):
    tools.log("Opening {}".format(zip_location))
    with zipfile.ZipFile(zip_location) as file:
        base_directory = file.namelist()[0]
        file.extractall(
            _temp,
            [
                i
                for i in file.namelist()
                if all(e not in i for e in addon.get("exclude_items", []))
            ],
        )
    tools.log("Extracting to: {}".format(os.path.join(_temp, base_directory)))
    install_path = os.path.join(_addons, addon['plugin_id'])
    tools.copytree(os.path.join(_temp, base_directory), install_path, ignore=True)
    _remove_folder(os.path.join(install_path, base_directory))


def _update_addon_version(addon, default_branch_name, branch, gitsha):
    addon_xml = os.path.join(_addons, addon['plugin_id'], "addon.xml")
    tools.log('Rewriting addon version: {}'.format(addon_xml))

    branch = re.sub(r'[^abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.+_@~]', '_', branch)

    if default_branch_name != branch:
        replace_regex = r'<\1"\2.\3.\4-{}~{}"\7>'.format(gitsha[0:8], branch)
    else:
        replace_regex = r'<\1"\2.\3.\4-{}"\7>'.format(gitsha[0:8])

    with open(addon_xml, "r+") as f:
        content = f.read()
        content = re.sub(
            r'<(addon id.*version=)\"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+)?(-.*?)?\"(.*)>',
            replace_regex, content)

        f.seek(0)
        f.write(content)


def _rewrite_addon_xml_dependency_versions(addon):
    kodi_version = tools.kodi_version()
    tools.log("KODI_VERSION: {}".format(kodi_version))
    kodi_dep_versions = {
        18: {"xbmc.python": "2.26.0", "xbmc.gui": "5.14.0"},
        19: {"xbmc.python": "3.0.0", "xbmc.gui": "5.15.0"},
    }

    if kodi_version in kodi_dep_versions:
        kodi_deps = kodi_dep_versions[kodi_version]
    else:
        # Take latest version if we don't have version specific
        kodi_deps = kodi_dep_versions[max(kodi_dep_versions)]
    tools.log("KODI DEPENDENCY VERSIONS: {}".format(kodi_deps))

    addon_xml = os.path.join(_addons, addon['plugin_id'], "addon.xml")
    tools.log('Rewriting {}'.format(addon_xml))

    with open(addon_xml, "r+") as f:
        content = f.read()
        for dep in kodi_deps:
            content = re.sub('<import addon="' + dep + r'" version=".*?"\s?/>',
                             '<import addon="' + dep + '" version="' + kodi_deps[dep] + '" />', content)
        f.seek(0)
        f.write(content)
    pass


def _cleanup_old_files():
    tools.log("Cleaning up old files...")
    for i in [
        i for i in xbmcvfs.listdir(_addon_data)[1] if not i.endswith(".xml")
    ]:
        _remove_file(os.path.join(_addon_data, i))


def _clear_temp():
    try:
        for item in os.listdir(_temp):
            path = os.path.join(_temp, item)
            if os.path.isdir(path):
                os.remove(path)
            elif os.path.isfile(path) and path not in ["kodi.log"]:
                shutil.rmtree(path)
    except (OSError, IOError) as e:
        tools.log("Failed to cleanup temporary storage: {}".format(repr(e)))


def _get_selected_commit(user, repo, branch):
    dialog = xbmcgui.Dialog()
    
    tags = []
    commits = []
    commit_items = []
    with tools.busy_dialog():
        for tag in API.get_tags(user, repo):
            if 'message' in tag:
                break
            tags.append((os.path.split(tag['ref'])[1], tag['object']['sha']))
            commits.append(API.get_commit(user, repo, tag['object']['sha']))
        for branch_commit in API.get_branch_commits(user, repo, branch):
            commits.append(branch_commit)
        
        sorted_commits = sorted(commits,
                                key=lambda b: b['commit']['author']["date"]
                                              if 'commit' in b else
                                              b['author']["date"],
                                reverse=True)

        for commit in sorted_commits:
            if commit['sha'] in [i[1] for i in tags]:
                tag = [i[0] for i in tags if i[1] == commit['sha']][0]
                label = '[COLOR {}]{}[/COLOR]'.format(_color, tag)
                if label not in [i.getLabel() for i in commit_items]:
                    li = xbmcgui.ListItem(label)
                    li.setArt({'thumb': os.path.join(_media_path, 'tag.png')})
                    commit_items.append(li)
            else:
                date = tools.to_local_time(commit['commit']['author']['date'])
                li = xbmcgui.ListItem(
                    "[COLOR {}]{}[/COLOR] - {}".format(
                        _color,
                        commit["sha"][:8],
                        commit["commit"]["message"].replace("\n", "; "),
                    ), label2=settings.get_localized_string(32014).format(commit['commit']['author']['name'], date))
                art = os.path.join(_media_path, 'commit.png')
                if 'pull' in commit["commit"]["message"]:
                    art = os.path.join(_media_path, 'pull.png')
                elif 'merge' in commit["commit"]["message"]:
                    art = os.path.join(_media_path, 'merge.png')
                    
                li.setArt({'thumb': art})
                commit_items.append(li)

    selection = dialog.select(settings.get_localized_string(32016), commit_items, useDetails=not _compact)
    del dialog
    if selection > -1:
        sha = sorted_commits[selection]['sha']
        if sha in [i[1] for i in tags]:
            return [i[0] for i in tags if i[1] == sha][0], [i[1] for i in tags if i[1] == sha][0]
        else:
            return sha[:8], sha
    
    return None, None


def _get_commit_zip_file(user, repo, commit_sha):
    return _store_zip_file(API.get_commit_zip(user, repo, commit_sha))


def _get_branch_info(addon, branch):
    branch = API.get_repo_branch(addon["user"], addon["repo_name"], branch["name"])
    updated_at = branch["commit"]["commit"]["author"]["date"]
    sha = branch["commit"]["sha"]
    protected = branch["protected"]
    return [
        {
            "name": branch["name"],
            "sha": sha,
            "branch": branch,
            "updated_at": updated_at,
            "protected": protected,
        }
    ]


def update_addon():
    dialog = xbmcgui.Dialog()
    pool = ThreadPool()
    repos, _ = repository.get_repos()
    addon_names = [i for i in [i["name"] for i in repos.values()]]
    addon_items = []
    for addon_name in addon_names:
        li = xbmcgui.ListItem(settings.get_localized_string(32015).format(addon_name))
        
        if not _compact:
            repo_def = [repos[i] for i in repos if repos[i]['name'] == addon_name][0]
            user = repo_def['user']
            repo = repo_def['repo_name']
            icon = repository.get_icon(user, repo)
            li.setArt({'thumb': icon})

        addon_items.append(li)
            
    selection = dialog.select(settings.get_localized_string(32012), addon_items, useDetails=not _compact)
    if selection == -1:
        dialog.notification(_addon_name, settings.get_localized_string(32017))
        del dialog
        sys.exit(0)

    addon = [
        i for i in repos.values() if i["name"] == addon_names[selection]
    ][0]

    with tools.busy_dialog():
        for b in API.get_repo_branches(addon["user"], addon["repo_name"]):
            if 'message' in b:
                dialog.ok(_addon_name, b['message'])
                return
            pool.put(_get_branch_info, addon, b)
        branch_items = pool.wait_completion()

        _default = API.get_default_branch(addon['user'], addon['repo_name'])
        
        default_branch = [
            i for i in branch_items if i["name"] == _default
        ]
        protected_branches = sorted(
            [
                i
                for i in branch_items
                if i["protected"] and i["name"] != _default
            ],
            key=lambda b: b["updated_at"],
            reverse=True,
        )
        normal_branches = sorted(
            [
                i
                for i in branch_items
                if not i["protected"] and i["name"] != _default
            ],
            key=lambda b: b["updated_at"],
            reverse=True,
        )
        sorted_branches = default_branch + protected_branches + normal_branches

    branch_items = []
    for i in sorted_branches:
        art = os.path.join(_media_path, 'branch.png')
        if i in default_branch:
            art = os.path.join(_media_path, 'default-branch.png')
        elif i in protected_branches:
            art = os.path.join(_media_path, 'protected-branch.png')
        date = tools.to_local_time(i['updated_at'])
        li = xbmcgui.ListItem("{} - ([COLOR {}]{}[/COLOR])"
                              .format(i["branch"]["name"], _color, i["sha"][:8]),
                              label2=settings.get_localized_string(32018).format(date))
        li.setArt({'thumb': art})
        branch_items.append(li)
    selection = dialog.select(settings.get_localized_string(32019), branch_items, useDetails=not _compact)
    if selection > -1:
        branch = sorted_branches[selection]
    else:
        del dialog
        return

    _cleanup_old_files()

    commit_sha = None
    selection = dialog.yesno(
        settings.get_localized_string(32020).format(_color, branch["name"]),
        settings.get_localized_string(32021),
        yeslabel=settings.get_localized_string(32022),
        nolabel=settings.get_localized_string(32023),
    )
    if selection:
        commit_label, commit_sha = _get_selected_commit(
            addon["user"], addon["repo_name"], branch["sha"]
        )
        if not commit_sha:
            dialog.notification(_addon_name, settings.get_localized_string(32017))
            del dialog
            return

    if not dialog.yesno(
            settings.get_localized_string(32000),
            settings.get_localized_string(32024).format(
                _color, addon["name"], _color, branch["branch"]["name"] if not commit_sha else commit_label
            ),
    ):
        dialog.notification(_addon_name, settings.get_localized_string(32017))
        del dialog
        return
    _remove_folder(os.path.join(_addons, addon["plugin_id"]))
    progress = xbmcgui.DialogProgress()
    progress.create(
        _addon_name, settings.get_localized_string(32025).format(_color, addon["name"])
    )
    progress.update(-1)
    location = _get_branch_zip_file(
        addon["user"],
        addon["repo_name"],
        branch["branch"]["name"] if not commit_sha else commit_sha,
    )

    progress.update(-1, settings.get_localized_string(32026).format(_color, addon["name"]))
    _extract_addon(location, addon)
    _rewrite_addon_xml_dependency_versions(addon)
    _update_addon_version(addon, sorted_branches[0]['name'], branch['name'], branch['sha'] if not commit_sha else commit_label)
    _clear_temp()

    progress.update(-1, settings.get_localized_string(32027))
    progress.close()
    del progress
    del dialog
    tools.reload_profile()
