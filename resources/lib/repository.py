# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import json
import os
import re
import requests
import time
import unidecode
from xml.etree import ElementTree

from resources.lib.color import color_string
from resources.lib.github_api import GithubAPI
from resources.lib import settings
from resources.lib import tools

API = GithubAPI()

_home = tools.translate_path('special://home')
_addons = os.path.join(_home, 'addons')
_addon_data = tools.translate_path(settings.get_addon_info('profile'))
_json_path = os.path.join(_addon_data, 'json')

_addon_id = settings.get_addon_info('id')
_addon_name = settings.get_addon_info('name')

_user = settings.get_setting_string('github.username')
_compact = settings.get_setting_boolean('general.compact')

def get_repos(key=None):
    repos = {}
    files = []
    
    tools.create_folder(_json_path)
    for j in os.listdir(_json_path):
        file_path = os.path.join(_json_path, j)
        content = json.loads(tools.read_from_file(file_path))
        for r in content:
            repos[r] = content[r]
            files.append(file_path)
    if key:
        return repos.get(key, {})

    return repos, files


def add_repository():
    dialog = xbmcgui.Dialog()
    
    user = dialog.input(settings.get_localized_string(32028))
    if not user:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return
    
    if API.get_user(user).get('type', 'User') == 'Organization':
        user_repos = sorted(API.get_org_repos(user), key=lambda b: b['updated_at'], reverse=True)
    elif user == _user:
        user_repos = sorted(API.get_repos(), key=lambda b: b['updated_at'], reverse=True)
    else:
        user_repos = sorted(API.get_user_repos(user), key=lambda b: b['updated_at'], reverse=True)
    
    addon_repos = ['custom']
    repo_items = [xbmcgui.ListItem(settings.get_localized_string(32067))]
    
    with tools.busy_dialog():
        for user_repo in user_repos:
            name = user_repo['name']
            addon_xml = API.get_file(user, name, 'addon.xml', text=True)
            if not addon_xml:
                continue
            
            addon = ElementTree.fromstring(addon_xml.encode('utf-8'))

            def_name = addon.get('name')
            li = xbmcgui.ListItem(def_name, settings.get_localized_string(32018).format(tools.to_local_time(user_repo['updated_at'])))
            
            if not _compact:
                icon = get_icon(user, name)
                li.setArt({'thumb': icon})

            repo_items.append(li)
            addon_repos.append(name)
    
    selection = dialog.select(settings.get_localized_string(32012), repo_items, useDetails=not _compact)
    if selection < 0:
        del dialog
        return
    repo = addon_repos[selection]
    
    if repo == 'custom':
        _add_custom(user)
        del dialog
    else:    
        if not _check_repo(user, repo):
            del dialog
            return
        
        addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
        if not addon_xml:
            del dialog
            return
            
        addon = ElementTree.fromstring(addon_xml.encode('utf-8'))

        name = addon.get('name')
        plugin_id = addon.get('id')
        
        _add_repo(user, repo, name, plugin_id)
        del dialog
    
    
def _add_repo(user, repo, name, plugin_id):
    dialog = xbmcgui.Dialog()
    
    key = user + '-' + plugin_id
    addon_def = {key: {'user': user, 'repo_name': repo, 'name': name, 'plugin_id': plugin_id,
                 'exclude_items': []}}
    filename = key + '.json'
    
    tools.create_folder(_json_path)
    tools.write_to_file(os.path.join(_json_path, filename), json.dumps(addon_def))
    dialog.notification(_addon_name, settings.get_localized_string(32037))
    
    _prompt_for_update(key)
    del dialog
    
    
def _add_custom(user):
    dialog = xbmcgui.Dialog()
    
    repo = dialog.input(settings.get_localized_string(32030))
    if not repo:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return

    def_name = ''
    def_id = ''
    input_name = settings.get_localized_string(32032)
    input_id = settings.get_localized_string(32033)
    addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
    
    if addon_xml:
        addon = ElementTree.fromstring(addon_xml.encode('utf-8'))

        def_name = addon.get('name')
        def_id = addon.get('id')
    
        input_name = input_name.format(settings.get_localized_string(32034))
        input_id = input_id.format(settings.get_localized_string(32034))
    else:
        input_name = input_name.format(settings.get_localized_string(32035))
        input_id = input_id.format(settings.get_localized_string(32035))
    
    if '' in [def_name, def_id]:
        if not dialog.yesno(_addon_name, settings.get_localized_string(32036)):
            del dialog
            return
    
    name = dialog.input(input_name, defaultt=def_name)
    if not name:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return
    plugin_id = dialog.input(input_id, defaultt=def_id)
    if not plugin_id:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return

    _add_repo(user, repo, name, plugin_id)
    del dialog
    
    
def _check_repo(user, repo):
    dialog = xbmcgui.Dialog()
    
    can_get = API.get('repos/{}/{}'.format(user, repo))
    if not can_get.ok:
        dialog.ok(_addon_name, settings.get_localized_string(32031))
        del dialog
        return False
    return True
    
    
def _prompt_for_update(key):
    dialog = xbmcgui.Dialog()
    
    if dialog.yesno(_addon_name, settings.get_localized_string(32068)):
        tools.execute_builtin('RunScript({},action=update_addon,id={})'.format(_addon_id, key))
    del dialog


def remove_repository():
    dialog = xbmcgui.Dialog()
    
    selection = get_repo_selection('remove_repository')
    
    if selection:
        file_path = selection['files'][selection['selection']]
        indices = [i for i, x in enumerate(selection['files']) if x == file_path]
        if len(indices) > 1:
            remove = dialog.yesno(_addon_name, settings.get_localized_string(32039).format(', '.join([selection['addon_names'][i] for i in indices])))
        else:
            remove = dialog.yesno(_addon_name, settings.get_localized_string(32040).format(selection['addon_names'][selection['selection']]))
        if remove:
            os.remove(file_path)
            dialog.notification(_addon_name, settings.get_localized_string(32041 if len(indices) == 1 else 32042).format(len(indices)))
    del dialog
    

def get_branch_info(addon, branch):
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

    
def get_icon(user, repo):
    icon = ''
    addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
    
    if addon_xml:
        addon = ElementTree.fromstring(addon_xml.encode('utf-8'))
        
        try:
            def_icon = [i for i in addon.findall('extension') if i.get('point') == 'xbmc.addon.metadata'][0]
            icon_path = def_icon.find('assets').find('icon').text
            icon_url = API.get_file(user, repo, icon_path)['download_url']
            icon = requests.head(icon_url, allow_redirects=True).url
        except Exception as e:
            tools.log('Could not get icon: {}'.format(e))
    return icon


def get_repo_selection(ret):
    dialog = xbmcgui.Dialog()
    repos, files = get_repos()
    names = [i for i in [i["name"] for i in repos.values()]]
    keys = [i for i in repos]
    
    repo_items = []
    for repo in repos.values():
        user = repo['user']
        repo_name = repo['repo_name']
        name = repo['name']
        li = xbmcgui.ListItem(name, label2=settings.get_localized_string(32063).format(user))
        
        if not _compact:
            icon = get_icon(user, repo_name)
            li.setArt({'thumb': icon})

        repo_items.append(li)

    selection = dialog.select(settings.get_localized_string(32012), repo_items, useDetails=not _compact)
    if selection == -1:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return None
    else:
        repo = repos[keys[selection]]
        if ret == 'update_addon':
            return repo
        elif ret == 'remove_repository':
            return {'files': files, 'addon_names': names, 'selection': selection}
        elif ret == 'open_issue':
            return {'user': repo['user'], 'repo': repo['repo_name']}
