# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmc
import xbmcgui

import getpass
import os
import requests

from resources.lib import qr
from resources.lib import settings
from resources.lib import tools

_addon_id = settings.get_addon_info("id")
_addon_version = settings.get_addon_info("version")
_addon_data = tools.translate_path(settings.get_addon_info("profile"))

_log_location = tools.translate_path("special://logpath")

_paste_url = "https://paste.kodi.tv/"
_github_token = settings.get_setting_string("github.token")

_color = settings.get_setting_string("general.color")


def _get_log_files():
    files = []
    if not os.path.exists(_log_location):
        return

    for log in [
        i
        for i in os.listdir(_log_location)
        if os.path.isfile(os.path.join(_log_location, i)) and not i.endswith('.dmp')
    ]:
        files.append(os.path.join(_log_location, log))

    return files


def _select_log_file():
    dialog = xbmcgui.Dialog()
    log_files = _get_log_files()

    filenames = [os.path.split(i)[1] for i in log_files]
    f = dialog.select(
        settings.get_localized_string(32092),
        filenames,
        preselect=filenames.index("kodi.log"),
    )

    del dialog

    if f > -1:
        return log_files[f]


def _get_log_contents(logfile=None):
    if logfile == None:
        logfile = os.path.join(_log_location, "kodi.log")
    if os.path.exists(logfile):
        return tools.read_from_file(logfile)
    else:
        tools.log("Error finding logs!", "error")


def _censor_log_content(log_content):
    censor_string = "--- CENSORED ---"
    log_content = log_content.replace(getpass.getuser(), censor_string)
    log_content = log_content.replace(_github_token, censor_string)
    return log_content


def _log_dialog(log_key):
    url = log_url(log_key)
    copied = tools.copy2clip(url)

    qr_code = qr.generate_qr(url, _addon_data, "{}.png".format(log_key))
    top = [(settings.get_localized_string(32084), "#efefefff"), (url, _color)]
    bottom = [(settings.get_localized_string(32088), "#efefefff")] if copied else []
    qr.qr_dialog(
        qr_code,
        top_text=top,
        bottom_text=bottom,
    )

    tools.execute_builtin("ShowPicture({})".format(qr_code))
    while tools.get_condition("Window.IsActive(slideshow)"):
        xbmc.sleep(1000)
    os.remove(qr_code)


def log_url(log_key):
    return _paste_url + "raw/" + log_key


def upload_log(choose=False, dialog=False):
    logfile = _select_log_file() if choose else None
    log_data = _censor_log_content(_get_log_contents(logfile))
    user_agent = "{}: {}".format(_addon_id, _addon_version)

    try:
        response = requests.post(
            _paste_url + "documents",
            data=log_data.encode("utf-8"),
            headers={"User-Agent": user_agent},
        ).json()
        if "key" in response:
            if dialog:
                _log_dialog(response["key"])
            return True, response["key"]
        elif "message" in response:
            tools.log("Upload failed: {}".format(response["message"]), level="error")
            return False, response["message"]
        else:
            tools.log("Invalid response: {}".format(response), level="error")
            return False, "Error posting the log file."
    except requests.exceptions.RequestException as e:
        tools.log("Failed to retrieve the paste URL: {}".format(e), level="error")
        return False, "Failed to retrieve the paste URL."
