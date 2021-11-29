from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import os
import time

from resources.lib.color import color_string
from resources.lib.github_api import GithubAPI
from resources.lib import settings
from resources.lib import tools

API = GithubAPI()

_addon_name = settings.get_addon_info("name")
_access_token = settings.get_setting_string("github.token")


def force_auth():
    dialog = xbmcgui.Dialog()
    if not _access_token:
        if dialog.yesno(_addon_name, settings.get_localized_string(32005)):
            authorize(True)
    del dialog


def check_auth():
    if not _access_token:
        return False
    return True


def authorize(in_addon=False):
    init = API.authorize()
    dialog = xbmcgui.Dialog()
    dialogProgress = xbmcgui.DialogProgress()
    dialogProgress.create(
        _addon_name,
        settings.get_localized_string(32043).format(
            color_string(init["verification_uri"]), color_string(init["user_code"])
        ),
    )

    expires = time.time() + init["expires_in"]

    while True:
        time.sleep(init["interval"])

        token = API.authorize(init["device_code"])

        pct_timeout = (time.time() - expires) / init["expires_in"] * 100
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

        if "access_token" in token:
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
    if dialog.yesno(
        _addon_name,
        settings.get_localized_string(32047).format(
            "https://github.com/settings/connections/applications/"
        ),
    ):
        _clear_oauth()
        dialog.notification(_addon_name, settings.get_localized_string(32048))
        settings.open_settings()


def _save_oauth(response):
    settings.set_setting_string("github.token", response["access_token"])
    settings.set_setting_string("github.username", API.get_username())


def _clear_oauth():
    settings.set_setting_string("github.token", "")
    settings.set_setting_string("github.username", "")
