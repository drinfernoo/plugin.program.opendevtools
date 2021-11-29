import xbmcgui

import getpass
import os
import requests

from resources.lib import color
from resources.lib import settings
from resources.lib import tools

_addon_id = settings.get_addon_info("id")
_addon_version = settings.get_addon_info("version")

_log_location = tools.translate_path("special://logpath")

_paste_url = "https://paste.kodi.tv/"
_github_token = settings.get_setting_string("github.token")


def _get_log_contents():
    log_file = os.path.join(_log_location, "kodi.log")
    if os.path.exists(log_file):
        return tools.read_from_file(log_file)
    else:
        tools.log("Error finding logs!", "error")


def _censor_log_content(log_content):
    censor_string = "--- CENSORED ---"
    log_content = log_content.replace(getpass.getuser(), censor_string)
    log_content = log_content.replace(_github_token, censor_string)
    return log_content


def log_dialog():
    response, log_key = upload_log()
    if response:
        copied = tools.copy2clip(log_url(log_key))

        dialog = xbmcgui.Dialog()
        text = "{} {}".format(
            settings.get_localized_string(32084), color.color_string(log_url(log_key))
        )
        if copied:
            text += "\n{}".format(settings.get_localized_string(32088))
        dialog.ok(
            settings.get_localized_string(32083),
            text,
        )


def log_url(log_key):
    return _paste_url + "raw/" + log_key


def upload_log():
    log_data = _censor_log_content(_get_log_contents())
    user_agent = "{}: {}".format(_addon_id, _addon_version)

    try:
        response = requests.post(
            _paste_url + "documents",
            data=log_data.encode("utf-8"),
            headers={"User-Agent": user_agent},
        ).json()
        if "key" in response:
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
