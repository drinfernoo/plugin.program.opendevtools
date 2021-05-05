# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import sys

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl

from resources.lib import color
from resources.lib import oauth
from resources.lib import raise_issue
from resources.lib import repository
from resources.lib import settings
from resources.lib import update_addon


def _do_action():
    if len(sys.argv) > 1:
        _params = sys.argv[1:]
        params = {i[0]: i[1] for i in [j.split('=') for j in _params]}
        action = params.get('action', None)
        id = params.get('id', None)
        if action == 'color_picker':
            color.color_picker()
        elif action == 'authorize':
            oauth.authorize()
        elif action == 'revoke':
            oauth.revoke()
        elif action == 'update_addon' and id:
            update_addon.update_addon(id)
    else:
        oauth.check_auth()
        dialog = xbmcgui.Dialog()

        actions = [(settings.get_localized_string(32000), update_addon.update_addon),
                   (settings.get_localized_string(32001), raise_issue.raise_issue),
                   (settings.get_localized_string(32002), repository.add_repository),
                   (settings.get_localized_string(32003), repository.remove_repository)]

        selection = dialog.select(settings.get_localized_string(32004), [i[0] for i in actions])
        if selection > -1:
            actions[selection][1]()
        del dialog

_do_action()
