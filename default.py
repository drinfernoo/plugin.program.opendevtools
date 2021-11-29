# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import os
import sys

from resources.lib import color
from resources.lib import oauth
from resources.lib import logging
from resources.lib import raise_issue
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib import update_addon

_addon_path = tools.translate_path(settings.get_addon_info("path"))
_media_path = os.path.join(_addon_path, "resources", "media")

_compact = settings.get_setting_boolean("general.compact")


def _do_action():
    if len(sys.argv) > 1:
        _params = sys.argv[1:]
        params = {i[0]: i[1] for i in [j.split("=") for j in _params]}
        action = params.get("action", None)
        id = params.get("id", None)
        if action == "color_picker":
            color.color_picker()
        elif action == "authorize":
            oauth.authorize()
        elif action == "revoke":
            oauth.revoke()
        elif action == "update_addon" and id:
            update_addon.update_addon(id)
    else:
        auth = oauth.check_auth()
        dialog = xbmcgui.Dialog()

        if auth:
            actions = [
                (32000, 32069, update_addon.update_addon, "update.png"),
                (32001, 32070, raise_issue.raise_issue, "issue.png"),
                (32002, 32071, repository.add_repository, "plus.png"),
                (32003, 32072, repository.remove_repository, "minus.png"),
                (32085, 32086, logging.log_dialog, "log.png"),
            ]
        else:
            actions = [
                (32057, 32087, oauth.authorize, "github.png"),
                (32085, 32086, logging.log_dialog, "log.png"),
            ]

        action_items = []
        for action in actions:
            li = xbmcgui.ListItem(
                settings.get_localized_string(action[0]),
                label2=settings.get_localized_string(action[1]),
            )
            li.setArt({"thumb": os.path.join(_media_path, action[3])})
            action_items.append(li)

        selection = dialog.select(
            settings.get_localized_string(32004), action_items, useDetails=not _compact
        )
        if selection > -1:
            actions[selection][2]()
        del dialog


_do_action()
