# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import sys

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl

from resources.lib.raise_issue import raise_issue
from resources.lib.repository import add_repository
from resources.lib.repository import oauth
from resources.lib.repository import remove_repository
from resources.lib.repository import revoke
from resources.lib.update_addon import update_addon
from resources.lib import settings
from resources.lib.tools import color_picker

_addon_name = settings.get_addon_info('name')
_access_token = settings.get_setting_string('github.token')


def _do_action():
    if len(sys.argv) > 1:
        _params = sys.argv[1:]
        params = {i[0]: i[1] for i in [j.split('=') for j in _params]}
        action = params.get('action', None)
        if action == 'color_picker':
            color_picker()
        elif action == 'authorize':
            oauth()
        elif action == 'revoke':
            revoke()
    else:
        dialog = xbmcgui.Dialog()
        if not _access_token:
            if dialog.yesno(_addon_name, "GitHub has not been authorized. Would you like to authorize now?"):
                oauth(True)

        actions = [('Log Issue', raise_issue), ('Update Addon', update_addon),
                   ('Add Repository', add_repository), ('Remove Repository', remove_repository)]
        selection = dialog.select('Select an action...', [i[0] for i in actions])
        if selection > -1:
            actions[selection][1]()
        del dialog

_do_action()
