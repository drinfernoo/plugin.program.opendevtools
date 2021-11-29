# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import getpass
import os
import requests

from resources.lib.color import color_string
from resources.lib import logging
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI

API = GithubAPI()

_home = tools.translate_path("special://home")

_addon_name = settings.get_addon_info("name")
_addon_id = settings.get_addon_info("id")
_addon_version = settings.get_addon_info("version")

_compact = settings.get_setting_boolean("general.compact")


def raise_issue():
    selection = repository.get_repo_selection("open_issue")
    if selection:
        dialog = xbmcgui.Dialog()
        title = dialog.input(settings.get_localized_string(32006))
        if title:
            description = dialog.input(settings.get_localized_string(32007))
            log_key = None
            response, log_key = logging.upload_log()

            if response:
                try:
                    resp = _post_issue(
                        _format_issue(title, description, log_key),
                        selection["user"],
                        selection["repo"],
                    )
                    if "message" not in resp:
                        dialog.notification(
                            _addon_name,
                            settings.get_localized_string(32009).format(
                                color_string(selection["repo"]), color_string(log_key)
                            ),
                        )
                    else:
                        dialog.ok(_addon_name, resp["message"])
                except requests.exceptions.RequestException as e:
                    dialog.notification(
                        _addon_name, settings.get_localized_string(32010)
                    )
                    tools.log("Error opening issue: {}".format(e), "error")
        else:
            dialog.ok(_addon_name, settings.get_localized_string(32011))
        del dialog


def _format_issue(title, description, log_key):
    log_desc = "{}\n\n{}\n\nLog File - {}".format(
        settings.get_localized_string(32013).format(_addon_name),
        description,
        logging.log_url(log_key),
    )

    return {"title": title, "body": log_desc}
