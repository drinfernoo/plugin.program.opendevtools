# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import os
import re
import shutil
import sys
import time
from xml.etree import ElementTree
import zipfile

import xbmcgui
import xbmcvfs

from resources.lib.color import color_string
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI
from resources.lib.thread_pool import ThreadPool

API = GithubAPI()

_addon_name = settings.get_addon_info('name')

_compact = settings.get_setting_boolean('general.compact')
_dependencies = settings.get_setting_boolean('general.dependencies')

_home = tools.translate_path('special://home')
_temp = tools.translate_path('special://temp')
_addons = os.path.join(_home, 'addons')
_addon_path = tools.translate_path(settings.get_addon_info('path'))
_addon_data = tools.translate_path(settings.get_addon_info('profile'))

_media_path = os.path.join(_addon_path, 'resources', 'media')


def _get_zip_file(user, repo, branch=None, sha=None):
    if (sha and branch) or not (sha or branch):
        raise ValueError('Cannot specify both branch and sha')
    else:
        return _store_zip_file(API.get_zipball(user, repo, sha if sha else branch))


def _store_zip_file(zip_contents):
    zip_location = os.path.join(_addon_data, "{}.zip".format(int(time.time())))
    tools.write_to_file(zip_location, zip_contents, bytes=True)

    return zip_location


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
    tools.remove_folder(os.path.join(install_path, base_directory))


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


def _rewrite_kodi_dependency_versions(addon):
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

    content = tools.read_from_file(addon_xml)
    for dep in kodi_deps:
        content = re.sub('<import addon="' + dep + r'" version=".*?"\s?/>',
                         '<import addon="' + dep + '" version="' + kodi_deps[dep] + '" />', content)
    tools.write_to_file(addon_xml, content)


def _install_deps(addon):
    plugin = addon['plugin_id']
    
    visible_cond = 'Window.IsTopMost(yesnodialog)'
    
    xml_path = os.path.join(_addons, plugin, "addon.xml")
    addon_xml = ElementTree.parse(xml_path)
    root = addon_xml.getroot()
    deps = root.find('requires').findall('import')

    for dep in [d for d in deps if not d.get('addon').startswith('xbmc') and not d.get('optional') == "true"]:
        plugin_id = dep.get('addon')
        installed_cond = 'System.HasAddon({0})'.format(plugin_id)
        if tools.get_condition(installed_cond):
            continue

        tools.log('Installing ' + plugin_id)
        tools.execute_builtin('InstallAddon({0})'.format(plugin_id))

        clicked = False
        start = time.time()
        timeout = 10
        while not tools.get_condition(installed_cond):
            if time.time() >= start + timeout:
                tools.log('Timed out installing {}'.format(plugin_id), 'warning')
                break

            tools.sleep(500)

            if tools.get_condition(visible_cond) and not clicked:
                tools.log('Dialog to click open')
                tools.execute_builtin('SendClick(yesnodialog, 11)')
                clicked = True
            else:
                tools.log('...waiting')


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
                label = color_string(tag)
                if label not in [i.getLabel() for i in commit_items]:
                    li = xbmcgui.ListItem(label)
                    li.setArt({'thumb': os.path.join(_media_path, 'tag.png')})
                    commit_items.append(li)
            else:
                date = tools.to_local_time(commit['commit']['author']['date'])
                li = xbmcgui.ListItem(
                    "{} - {}".format(
                        color_string(commit["sha"][:8]),
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


def update_addon(addon=None):
    dialog = xbmcgui.Dialog()
    pool = ThreadPool()
    if addon:
        addon = repository.get_repos(addon)
    else:
        addon = repository.get_repo_selection('update_addon')
    if not addon:
        return
        

    with tools.busy_dialog():
        for b in API.get_repo_branches(addon["user"], addon["repo_name"]):
            if 'message' in b:
                dialog.ok(_addon_name, b['message'])
                return
            pool.put(repository.get_branch_info, addon, b)
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
        li = xbmcgui.ListItem("{} - ({})"
                              .format(i["branch"]["name"], color_string(i["sha"][:8])),
                              label2=settings.get_localized_string(32018).format(date))
        li.setArt({'thumb': art})
        branch_items.append(li)
    selection = dialog.select(settings.get_localized_string(32019), branch_items, useDetails=not _compact)
    if selection > -1:
        branch = sorted_branches[selection]
    else:
        del dialog
        return

    tools.cleanup_old_files()

    commit_sha = None
    selection = dialog.yesno(
        settings.get_localized_string(32020).format(color_string(branch["name"])),
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
                color_string(addon["name"]), color_string(branch["branch"]["name"]) if not commit_sha else commit_label
            ),
    ):
        dialog.notification(_addon_name, settings.get_localized_string(32017))
        del dialog
        return
    tools.remove_folder(os.path.join(_addons, addon["plugin_id"]))
    progress = xbmcgui.DialogProgress()
    progress.create(
        _addon_name, settings.get_localized_string(32025).format(color_string(addon["name"]))
    )
    progress.update(-1)
    
    location = _get_zip_file(
        addon["user"],
        addon["repo_name"],
        branch=branch["branch"]["name"]
    ) if not commit_sha else _get_zip_file(
        addon["user"],
        addon["repo_name"],
        sha=commit_sha
    )

    if location:
        progress.update(-1, settings.get_localized_string(32026).format(color_string(addon["name"])))
        
        _extract_addon(location, addon)
        _rewrite_kodi_dependency_versions(addon)
        _update_addon_version(addon, sorted_branches[0]['name'], branch['name'], branch['sha'] if not commit_sha else commit_label)
        if _dependencies:
            _install_deps(addon)
        tools.clear_temp()

        progress.update(-1, settings.get_localized_string(32027))

    progress.close()
    del progress
    del dialog
    tools.reload_profile()
