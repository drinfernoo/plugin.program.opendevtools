# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

from resources.lib import logging
from resources.lib import oauth
from resources.lib import update_addon
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI

API = GithubAPI()

_compact = settings.get_setting_boolean("general.compact")


def main_menu():
    auth = oauth.check_auth()

    if auth:
        actions = tools.build_menu(
            [
                (30074, 30075, update_addon.repo_menu, "github.png"),
                (
                    30069,
                    30070,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )
    else:
        actions = tools.build_menu(
            [
                (30043, 30071, oauth.authorize, "github.png", {"in_addon": True}),
                (
                    30069,
                    30070,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )

    dialog = xbmcgui.Dialog()
    selection = dialog.select(
        settings.get_localized_string(30004), actions[1], useDetails=not _compact
    )
    del dialog

    if selection > -1:
        if len(actions[0][selection]) == 4:
            actions[0][selection][2]()
        elif len(actions[0][selection]) == 5:
            actions[0][selection][2](**actions[0][selection][4])
