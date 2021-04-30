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

from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI

API = GithubAPI()

_home = tools.translate_path('special://home')
_addons = os.path.join(_home, 'addons')
_addon_data = tools.translate_path(settings.get_addon_info('profile'))
_json_path = os.path.join(_addon_data, 'json')

_addon_name = settings.get_addon_info('name')

_compact = settings.get_setting_boolean('general.compact')
_color = settings.get_setting_string('general.color')

def get_repos():
    repos = {}
    files = []
    
    tools.create_folder(_json_path)
    for j in os.listdir(_json_path):
        file_path = os.path.join(_json_path, j)
        content = json.loads(tools.read_all_text(file_path))
        for r in content:
            repos[r] = content[r]
            files.append(file_path)
    return repos, files


def add_repository():
    dialog = xbmcgui.Dialog()
    
    user = dialog.input(settings.get_localized_string(32028))
    if not user:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return
    repo = dialog.input(settings.get_localized_string(32030))
    if not repo:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return
    
    
    can_get = API.get('repos/{}/{}'.format(user, repo))
    if not can_get.ok:
        dialog.ok(_addon_name, settings.get_localized_string(32031))
        del dialog
        return

    def_name = ''
    def_id = ''
    input_name = settings.get_localized_string(32032)
    input_id = settings.get_localized_string(32033)
    addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
    
    if addon_xml:
        addon = ElementTree.fromstring(addon_xml)

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

    key = user + '-' + plugin_id
    addon_def = {key: {'user': user, 'repo_name': repo, 'name': name, 'plugin_id': plugin_id,
                 'exclude_items': []}}
    filename = key + '.json'
    
    tools.create_folder(_json_path)
    tools.write_all_text(os.path.join(_json_path, filename), json.dumps(addon_def))
    dialog.notification(_addon_name, settings.get_localized_string(32037))
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
    
    
def get_icon(user, repo):
    icon = ''
    addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
    
    if addon_xml:
        addon = ElementTree.fromstring(addon_xml)
        
        try:
            def_icon = [i for i in addon.findall('extension') if i.get('point') == 'xbmc.addon.metadata'][0]
            icon_path = def_icon.find('assets').find('icon').text
            icon_url = API.get_file(user, repo, icon_path)['download_url']
            icon = requests.head(icon_url, allow_redirects=True).url
        except Exception as e:
            tools.log('Could not get icon: {}'.format(e))
    return icon
    

def oauth(in_addon=False):
    init = API.authorize()
    dialog = xbmcgui.Dialog()
    dialogProgress = xbmcgui.DialogProgress()
    dialogProgress.create(_addon_name,
                          settings.get_localized_string(32043).format(
                                           _color,
                                           init['verification_uri'],
                                           _color,
                                           init['user_code']))
                                    
    expires = time.time() + init['expires_in']
    
    while True:
        time.sleep(init['interval'])
        
        token = API.authorize(init['device_code'])
        
        pct_timeout = (time.time() - expires) / init['expires_in'] * 100
        pct_timeout = 100 - int(abs(pct_timeout))
        
        if pct_timeout >= 100:
            dialogProgress.close()
            dialog.notification(_addon_name, settings.get_localized_string(32044))
            break
        if dialogProgress.iscanceled():
            dialogProgress.close()
            dialog.notification(_addon_name, settings.get_localized_string(32045))
            break
            
        dialogProgress.update(int(pct_timeout))
    
        if 'access_token' in token:
            dialogProgress.close()
            _save_oauth(token)
            dialog.notification(_addon_name, settings.get_localized_string(32046))
            break
            
    del dialog
    del dialogProgress
    if not in_addon:
        settings.open_settings()


def revoke():
    dialog = xbmcgui.Dialog()
    if dialog.yesno(_addon_name, settings.get_localized_string(32047).format('https://github.com/settings/connections/applications/')):
        _clear_oauth()
        dialog.notification(_addon_name, settings.get_localized_string(32048))
        settings.open_settings()


def _save_oauth(response):
    settings.set_setting_string('github.username', API.get_username())
    settings.set_setting_string('github.token', response['access_token'])
    

def _clear_oauth():
    settings.set_setting_string('github.username', '')
    settings.set_setting_string('github.token', '')


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
        li = xbmcgui.ListItem("{}".format(name), label2=settings.get_localized_string(32063).format(user))
        
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
