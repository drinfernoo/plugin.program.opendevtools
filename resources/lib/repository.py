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
    
    user = dialog.input('Enter GitHub Username')
    if not user:
        dialog.notification(_addon_name, 'Cancelled')
        del dialog
        return
    repo = dialog.input('Enter GitHub Repo Name')
    if not repo:
        dialog.notification(_addon_name, 'Cancelled')
        del dialog
        return
    
    
    can_get = API.get('repos/{}/{}'.format(user, repo))
    if not can_get.ok:
        dialog.ok(_addon_name, 'This repository either does not exist, '
                               'or you do not have access to it. Please verify '
                               'the repository owner and name, and that you have access.')
        del dialog
        return

    def_name = ''
    def_id = ''
    input_name = '{} the name of this addon'
    input_id = '{} the plugin ID of this addon'
    addon_xml = API.get_file(user, repo, 'addon.xml', text=True)
    
    if addon_xml:
        addon = ElementTree.fromstring(addon_xml)

        def_name = addon.get('name')
        def_id = addon.get('id')
    
        input_name = input_name.format('Confirm')
        input_id = input_id.format('Confirm')
    else:
        input_name = input_name.format('Enter')
        input_id = input_id.format('Enter')
    
    if '' in [def_name, def_id]:
        if not dialog.yesno(_addon_name, 'This repository seems to not contain an addon in its root folder. Do you still want to add it?'):
            del dialog
            return
    
    name = dialog.input(input_name, defaultt=def_name)
    if not name:
        dialog.notification(_addon_name, 'Cancelled')
        del dialog
        return
    plugin_id = dialog.input(input_id, defaultt=def_id)
    if not plugin_id:
        dialog.notification(_addon_name, 'Cancelled')
        del dialog
        return

    key = unidecode.unidecode(name)
    key = re.sub(r'[^\w\s-]', '', key).strip().lower()
    addon_def = {key: {'user': user, 'repo_name': repo, 'name': name, 'plugin_id': plugin_id,
                 'exclude_items': []}}
    
    tools.create_folder(_json_path)
    tools.write_all_text(os.path.join(_json_path, key + '.json'), json.dumps(addon_def))
    dialog.notification(_addon_name, 'Repository Added')
    del dialog


def remove_repository():
    dialog = xbmcgui.Dialog()
    
    repos, files = get_repos()
    addon_names = [i for i in [i["name"] for i in repos.values()]]
    
    addon_items = []
    for name in addon_names:
        li = xbmcgui.ListItem("Remove {}".format(name))
        
        if not _compact:
            repo_def = [repos[i] for i in repos if repos[i]['name'] == name][0]
            user = repo_def['user']
            repo = repo_def['repo_name']
            icon = get_icon(user, repo)
            li.setArt({'thumb': icon})

        addon_items.append(li)
    
    selection = dialog.select(_addon_name, addon_items, useDetails=not _compact)

    if selection > -1:
        # import web_pdb; web_pdb.set_trace()
        file_path = files[selection]
        indices = [i for i, x in enumerate(files) if x == file_path]
        if len(indices) > 1:
            remove = dialog.yesno(_addon_name, 'Removing this repository will remove the following repositories: {}.'
                                             ' Are you sure you want to remove them?'.format(', '.join([addon_names[i] for i in indices])))
        else:
            remove = dialog.yesno(_addon_name, 'Are you sure you want to remove {}?'.format(addon_names[selection]))
        if remove:
            os.remove(files[selection])
            dialog.notification(_addon_name, '{} Repositor{} Removed'.format(len(indices), 'y' if len(indices) == 1 else 'ies'))
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
            pass
    return icon
    

def oauth(in_addon=False):
    init = API.authorize()
    dialog = xbmcgui.Dialog()
    dialogProgress = xbmcgui.DialogProgress()
    dialogProgress.create(_addon_name,
                          ('Visit the following site from any device: '
                           '[COLOR skyblue][B]{}[/B][/COLOR]\nAnd enter the code: '
                           '[COLOR skyblue][B]{}[/B][/COLOR]').format(
                                           init['verification_uri'],
                                           init['user_code']))
                                    
    expires = time.time() + init['expires_in']
    
    while True:
        time.sleep(init['interval'])
        
        token = API.authorize(init['device_code'])
        
        pct_timeout = (time.time() - expires) / init['expires_in'] * 100
        pct_timeout = 100 - int(abs(pct_timeout))
        
        if pct_timeout >= 100:
            dialogProgress.close()
            dialog.notification(_addon_name, 'GitHub Authorization Failed')
            break
        if dialogProgress.iscanceled():
            dialogProgress.close()
            dialog.notification(_addon_name, 'GitHub Authorization Cancelled')
            break
            
        dialogProgress.update(int(pct_timeout))
    
        if 'access_token' in token:
            dialogProgress.close()
            _save_oauth(token)
            dialog.notification(_addon_name, 'GitHub Authorized Successfully')
            break
            
    del dialog
    del dialogProgress
    if not in_addon:
        settings.open_settings()


def revoke():
    dialog = xbmcgui.Dialog()
    if dialog.yesno(_addon_name, 'Are you sure you want to clear your authorization? To fully revoke your OAuth key, please visit https://github.com/settings/connections/applications/.'):
        _clear_oauth()
        dialog.notification(_addon_name, 'GitHub Authorization Cleared')
        settings.open_settings()


def _save_oauth(response):
    settings.set_setting_string('github.username', API.get_username())
    settings.set_setting_string('github.token', response['access_token'])
    

def _clear_oauth():
    settings.set_setting_string('github.username', '')
    settings.set_setting_string('github.token', '')
