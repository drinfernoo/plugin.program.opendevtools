# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

from resources.lib import logging
from resources.lib import oauth
from resources.lib import repository
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
                (32090, 32091, repository.repo_menu, "github.png"),
                (
                    32085,
                    32086,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )
    else:
        actions = tools.build_menu(
            [
                (32057, 32087, oauth.authorize, "github.png", {"in_addon": True}),
                (
                    32085,
                    32086,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )

    dialog = xbmcgui.Dialog()
    selection = dialog.select(
        settings.get_localized_string(32004), actions[1], useDetails=not _compact
    )
    del dialog

    if selection > -1:
        if len(actions[0][selection]) == 4:
            actions[0][selection][2]()
        elif len(actions[0][selection]) == 5:
            actions[0][selection][2](**actions[0][selection][4])
