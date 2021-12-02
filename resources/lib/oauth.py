from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import os
import time

from resources.lib import color
from resources.lib.github_api import GithubAPI
from resources.lib import qr
from resources.lib import settings
from resources.lib import tools

API = GithubAPI()

_addon_id = settings.get_addon_info("id")
_addon_name = settings.get_addon_info("name")
_addon_data = tools.translate_path(settings.get_addon_info("profile"))

_access_token = settings.get_setting_string("github.token")
_auth_url = "https://github.com/settings/connections/applications/"

_color = settings.get_setting_string("general.color")


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
    qr_code = qr.generate_qr(init["verification_uri"], _addon_data, "auth.png")
    top = [
        (settings.get_localized_string(32093), "#efefefff"),
        (init["verification_uri"], _color),
    ]
    bottom = [
        (settings.get_localized_string(32094), "#efefefff"),
        (init["user_code"], _color),
    ]
    qr.qr_dialog(
        qr_code,
        top_text=top,
        bottom_text=bottom,
    )

    tools.execute_builtin("ShowPicture({})".format(qr_code))
    expires = time.time() + init["expires_in"]

    while True:
        time.sleep(init["interval"])

        token = API.authorize(init["device_code"])

        pct_timeout = (time.time() - expires) / init["expires_in"] * 100
        pct_timeout = 100 - int(abs(pct_timeout))

        if pct_timeout >= 100:
            tools.execute_builtin('Action(Back)')
            dialog.notification(_addon_name, settings.get_localized_string(32044))
            break
        if not tools.get_condition("Window.IsActive(slideshow)"):
            dialog.notification(_addon_name, settings.get_localized_string(32045))
            break

        if "access_token" in token:
            tools.execute_builtin('Action(Back)')
            _save_oauth(token)
            dialog.notification(_addon_name, settings.get_localized_string(32046))
            break

    del dialog
    os.remove(qr_code)

    if in_addon:
        tools.execute_builtin("RunScript({})".format(_addon_id))
    else:
        settings.open_settings()


def revoke():
    dialog = xbmcgui.Dialog()
    if dialog.yesno(
        settings.get_localized_string(32059),
        settings.get_localized_string(32047).format(color.color_string(_auth_url)),
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
