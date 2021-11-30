# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import json
import os
import requests

from resources.lib.github_api import GithubAPI
from resources.lib import settings
from resources.lib.thread_pool import ThreadPool
from resources.lib import tools

API = GithubAPI()

_addon_path = tools.translate_path(settings.get_addon_info("path"))
_addon_data = tools.translate_path(settings.get_addon_info("profile"))
_builtin_json_path = os.path.join(_addon_path, "resources", "json")
_json_path = os.path.join(_addon_data, "json")

_addon_id = settings.get_addon_info("id")
_addon_name = settings.get_addon_info("name")

_user = settings.get_setting_string("github.username")
_compact = settings.get_setting_boolean("general.compact")
_collaborator = settings.get_setting_boolean("github.collaborator_repos")
_organization = settings.get_setting_boolean("github.organization_repos")
_show_bundled_repos = settings.get_setting_boolean("general.show_bundled_repos")

_extensions = {
    "xbmc.gui.skin": "skin",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.gui/skin.xsd
    "xbmc.webinterface": "web interface",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.webinterface/webinterface.xsd
    "xbmc.addon.repository": "repository",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.addon/repository.xsd
    "xbmc.service": "service",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/service.xsd
    "xbmc.metadata.scraper.albums": "album information",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.metadata/scraper.xsd
    "xbmc.metadata.scraper.artists": "artist information",  #
    "xbmc.metadata.scraper.movies": "movie information",  #
    "xbmc.metadata.scraper.musicvideos": "music video information",  #
    "xbmc.metadata.scraper.tvshows": "tv information",  #
    "xbmc.metadata.scraper.library": "library information",  #
    "xbmc.player.musicviz": "visualization",
    "xbmc.python.pluginsource": {  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/pluginsource.xsd
        "audio": "music addon",  #
        "image": "picture addon",  #
        "executable": "program addon",  #
        "video": "video addon",  #
        "game": "game addon",  #
        None: "addon",  #
    },
    "xbmc.python.script": {  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/script.xsd
        "audio": "music addon",  #
        "image": "picture addon",  #
        "executable": "program addon",  #
        "video": "video addon",  #
        "game": "game addon",  #
        None: "script",  #
    },
    "xbmc.python.weather": "weather",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/script.xsd
    "xbmc.python.lyrics": "lyrics",  #
    "xbmc.python.library": "python library",  #
    "xbmc.python.module": "python module",  #
    "xbmc.python.script": "python script",  #
    "xbmc.ui.screensaver": "screensaver",  #
    "xbmc.subtitle.module": "subtitle service module",  #
    "xbmc.addon.video": "video addon",
    "xbmc.addon.audio": "music addon",
    "xbmc.addon.image": "picture addon",
    "kodi.resource.font": "font pack",
    "kodi.resource.images": "image pack",  # https://github.com/xbmc/xbmc/blob/master/addons/kodi.resource/images.xsd
    "kodi.resource.language": "language pack",  # https://github.com/xbmc/xbmc/blob/master/addons/kodi.resource/language.xsd
    "kodi.resource.uisounds": "sound pack",  # https://github.com/xbmc/xbmc/blob/master/addons/kodi.resource/uisounds.xsd
    "kodi.context.item": "context menu",  # https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/contextitem.xsd,
    "kodi.game.controller": "game controller",  # https://github.com/xbmc/xbmc/blob/master/addons/kodi.binary.instance.game/controller.xsd
}


def get_repos(key=None):
    repos = {}

    tools.create_folder(_json_path)
    paths = [_json_path]
    if _show_bundled_repos:
        paths.append(_builtin_json_path)

    for path in [_json_path]:
        for j in os.listdir(path):
            file_path = os.path.join(path, j)
            content = json.loads(tools.read_from_file(file_path))
            for r in content:
                repos[r] = content[r]
                repos[r]["filename"] = file_path

    return repos if not key else repos.get(key, {})


def add_repository():
    dialog = xbmcgui.Dialog()
    pool = ThreadPool()

    user = dialog.input(settings.get_localized_string(32028)).lower()
    if not user:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return

    if API.get_user(user).get("type", "User") == "Organization":
        user_repos = API.get_org_repos(user)
    elif user == _user.lower():
        access_level = [
            "owner",
            "collaborator" if _collaborator else "",
            "organization_member" if _organization else "",
        ]
        user_repos = API.get_repos(",".join(access_level))
    else:
        user_repos = API.get_user_repos(user)

    addon_repos = []
    repo_items = []

    with tools.busy_dialog():
        for user_repo in user_repos:
            if "message" in user_repo:
                dialog.ok(_addon_name, settings.get_localized_string(32080))
                del dialog
                return
            pool.put(get_repo_info, user_repo)
        repos = pool.wait_completion()
        if not repos:
            dialog.ok(_addon_name, settings.get_localized_string(32081))
            del dialog
            return

        repos.sort(key=lambda b: b["updated_at"], reverse=True)
        addon_repos = [i["repo_name"] for i in repos]
        for i in repos:
            byline = (
                "{} - ".format(i["repo_name"])
                + ", ".join(
                    [
                        settings.get_localized_string(32063).format(i["user"]),
                        settings.get_localized_string(32018).format(
                            tools.to_local_time(i["updated_at"])
                        ),
                    ]
                )
                if i["user"].lower() != user
                else "{} - ".format(i["repo_name"])
                + settings.get_localized_string(32018).format(
                    tools.to_local_time(i["updated_at"])
                )
            )
            li = xbmcgui.ListItem(
                "{} - ({})".format(
                    i["name"], ", ".join([e.title() for e in i["extensions"]])
                ),
                label2=byline,
            )

            if not _compact:
                li.setArt({"thumb": i["icon"]})

            repo_items.append(li)

    if len(addon_repos) == 0:
        dialog.ok(_addon_name, settings.get_localized_string(32073))
        del dialog
        return

    selection = dialog.select(
        settings.get_localized_string(32012), repo_items, useDetails=not _compact
    )
    if selection < 0:
        del dialog
        return
    user = repos[selection]["user"]
    repo = addon_repos[selection]

    if not _check_repo(user, repo):
        del dialog
        return

    addon_xml = API.get_file(user, repo, "addon.xml", text=True)
    if not addon_xml:
        del dialog
        return

    tools.log("Reading addon.xml from {}/{}".format(user, repo))
    addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

    name = addon.get("name")
    plugin_id = addon.get("id")

    if dialog.yesno(_addon_name, settings.get_localized_string(32074).format(name)):
        _add_repo(user, repo, name, plugin_id)
    del dialog


def _add_repo(user, repo, name, plugin_id):
    dialog = xbmcgui.Dialog()

    key = user + "-" + plugin_id
    addon_def = {
        key: {
            "user": user,
            "repo_name": repo,
            "name": name,
            "plugin_id": plugin_id,
            "exclude_items": [],
        }
    }
    filename = key + ".json"

    tools.create_folder(_json_path)
    tools.write_to_file(os.path.join(_json_path, filename), json.dumps(addon_def))
    dialog.notification(_addon_name, settings.get_localized_string(32037))

    _prompt_for_update(key)
    del dialog


def _add_custom(user):
    dialog = xbmcgui.Dialog()

    repo = dialog.input(settings.get_localized_string(32030))
    if not repo:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return

    def_name = ""
    def_id = ""
    input_name = settings.get_localized_string(32032)
    input_id = settings.get_localized_string(32033)
    addon_xml = API.get_file(user, repo, "addon.xml", text=True)

    if addon_xml:
        tools.log("Reading addon.xml from {}/{}".format(user, repo))
        addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

        def_name = addon.get("name")
        def_id = addon.get("id")

        input_name = input_name.format(settings.get_localized_string(32034))
        input_id = input_id.format(settings.get_localized_string(32034))
    else:
        input_name = input_name.format(settings.get_localized_string(32035))
        input_id = input_id.format(settings.get_localized_string(32035))

    if "" in [def_name, def_id]:
        if not dialog.yesno(_addon_name, settings.get_localized_string(32036)):
            del dialog
            return

    name = dialog.input(input_name, defaultt=def_name)
    if not name:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return
    plugin_id = dialog.input(input_id, defaultt=def_id)
    if not plugin_id:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return

    _add_repo(user, repo, name, plugin_id)
    del dialog


def _check_repo(user, repo):
    dialog = xbmcgui.Dialog()

    can_get = API.get("repos/{}/{}".format(user, repo))
    if not can_get.ok:
        dialog.ok(_addon_name, settings.get_localized_string(32031))
        del dialog
        return False
    return True


def _prompt_for_update(key):
    dialog = xbmcgui.Dialog()

    if dialog.yesno(_addon_name, settings.get_localized_string(32068)):
        tools.execute_builtin(
            "RunScript({},action=update_addon,id={})".format(_addon_id, key)
        )
    del dialog


def remove_repository():
    dialog = xbmcgui.Dialog()

    repos = get_repos()
    repo = get_repo_selection("remove_repository")

    if repo:
        filename = repo["filename"]
        repo_defs = [i for i in repos.values()]

        indices = [i for i, x in enumerate(repo_defs) if x["filename"] == filename]
        if len(indices) > 1:
            remove = dialog.yesno(
                _addon_name,
                settings.get_localized_string(32039).format(
                    ", ".join([repo_defs[i]["name"] for i in indices])
                ),
            )
        else:
            remove = dialog.yesno(
                _addon_name, settings.get_localized_string(32040).format(repo["name"])
            )
        if remove:
            os.remove(filename)
            dialog.notification(
                _addon_name,
                settings.get_localized_string(
                    32041 if len(indices) == 1 else 32042
                ).format(len(indices)),
            )
    del dialog


def get_repo_info(repo_def):
    user = repo_def["owner"]["login"]
    repo = repo_def["name"]
    addon_xml = API.get_file(user, repo, "addon.xml", text=True)
    if not addon_xml:
        return

    tools.log("Reading addon.xml from {}/{}".format(user, repo))
    addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

    def_name = addon.get("name")
    icon = get_icon(user, repo, addon_xml)
    extensions = get_extensions(user, repo, addon_xml)

    return [
        {
            "name": def_name,
            "user": user,
            "repo_name": repo,
            "updated_at": repo_def["updated_at"],
            "icon": icon,
            "extensions": extensions,
        }
    ]


def get_branch_info(addon, branch):
    branch = API.get_repo_branch(addon["user"], addon["repo_name"], branch["name"])
    updated_at = branch["commit"]["commit"]["author"]["date"]
    sha = branch["commit"]["sha"]
    protected = branch["protected"]

    return [
        {
            "name": branch["name"],
            "sha": sha,
            "branch": branch,
            "updated_at": updated_at,
            "protected": protected,
        }
    ]


def get_icon(user, repo, addon_xml=None):
    icon = ""
    if not addon_xml:
        addon_xml = API.get_file(user, repo, "addon.xml", text=True)

    if addon_xml:
        tools.log("Finding icon in addon.xml from {}/{}".format(user, repo))
        addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

        try:
            icon_path = "icon.png"
            def_icon = list(addon.iter("icon"))

            if def_icon and len(def_icon) > 0:
                icon_path = def_icon[0].text

            icon_url = API.get_file(user, repo, icon_path)["download_url"]
            icon = requests.head(icon_url, allow_redirects=True).url
        except Exception as e:
            tools.log("Could not get icon: {}".format(e), level="warning")

    return icon


def get_extensions(user, repo, addon_xml=None):
    extensions = []
    if not addon_xml:
        addon_xml = API.get_file(user, repo, "addon.xml", text=True)

    if addon_xml:
        tools.log("Checking for extensions in {}/{}".format(user, repo))
        root = tools.parse_xml(text=addon_xml.encode("utf-8"))

        try:
            tags = root.findall("extension")
            if tags is not None:
                for ext in tags:
                    point = ext.get("point")
                    if point and point in _extensions:
                        ext_point = _extensions[point]
                        if isinstance(ext_point, dict):
                            provides = ext.find("provides")
                            if provides is not None and provides.text:
                                all_provides = provides.text.split(" ")
                                for p in all_provides:
                                    if p in ext_point:
                                        extensions.append(ext_point[p])
                            else:
                                extensions.append(ext_point[None])
                        else:
                            extensions.append(ext_point)
        except Exception as e:
            tools.log("Could not check for extensions: {}".format(e), level="warning")
    return extensions


def get_repo_selection(ret):
    dialog = xbmcgui.Dialog()
    repos = get_repos()
    repo_defs = sorted(repos.values(), key=lambda b: b["name"])

    repo_items = []
    with tools.busy_dialog():
        for repo in repo_defs:
            user = repo["user"]
            repo_name = repo["repo_name"]
            name = repo["name"]

            li = xbmcgui.ListItem(
                name,
                label2="{} - ".format(repo_name)
                + settings.get_localized_string(32063).format(user),
            )

            if not _compact:
                icon = get_icon(user, repo_name)
                li.setArt({"thumb": icon})

            repo_items.append(li)

    selection = dialog.select(
        settings.get_localized_string(32012), repo_items, useDetails=not _compact
    )
    if selection == -1:
        dialog.notification(_addon_name, settings.get_localized_string(32029))
        del dialog
        return None
    else:
        repo = repo_defs[selection]
        if ret in ["update_addon", "remove_repository"]:
            return repo
        elif ret == "open_issue":
            return {"user": repo["user"], "repo": repo["repo_name"]}
        del dialog
        return None
