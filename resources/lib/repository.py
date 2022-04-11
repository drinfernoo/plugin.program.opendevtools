# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import json
import os
import requests
import time

from resources.lib import color
from resources.lib.github_api import GithubAPI
from resources.lib import raise_issue
from resources.lib import settings
from resources.lib.thread_pool import ThreadPool
from resources.lib import tools
from resources.lib import update_addon

API = GithubAPI()

_addons = os.path.join(tools.translate_path("special://home"), "addons")
_addon_path = tools.translate_path(settings.get_addon_info("path"))
_addon_data = tools.translate_path(settings.get_addon_info("profile"))

_builtin_json_path = os.path.join(_addon_path, "resources", "json")
_json_path = os.path.join(_addon_data, "json")
_media_path = os.path.join(_addon_path, "resources", "media")

_addon_id = settings.get_addon_info("id")
_addon_name = settings.get_addon_info("name")

_authed_user = settings.get_setting_string("github.username")
_compact = settings.get_setting_boolean("general.compact")
_collaborator = settings.get_setting_boolean("github.collaborator_repos")
_organization = settings.get_setting_boolean("github.organization_repos")
_show_bundled_repos = settings.get_setting_boolean("general.show_bundled_repos")
_sort_repos = settings.get_setting_int("general.sort_repos")
_search_subdirs = settings.get_setting_boolean("github.search_subdirs")

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

    for path in paths:
        for j in [i for i in os.listdir(path) if i.endswith('.json')]:
            file_path = os.path.join(path, j)
            content = json.loads(tools.read_from_file(file_path))
            for r in content:
                repos[r] = content[r]
                repos[r]["filename"] = file_path
                if r == key:
                    return repos.get(key, {})

    return repos if not key else repos.get(key, {})


def _build_repo_listitem(repo_def, user):
    byline = (
        "{} - ".format(repo_def["repo_name"])
        + ", ".join(
            [
                settings.get_localized_string(30049).format(repo_def["user"]),
                settings.get_localized_string(30016).format(
                    tools.to_local_time(repo_def["updated_at"])
                ),
            ]
        )
        if repo_def["user"].lower() != user
        else "{} - ".format(repo_def["repo_name"])
        + settings.get_localized_string(30016).format(
            tools.to_local_time(repo_def["updated_at"])
        )
    )
    li = xbmcgui.ListItem(
        "{} - ({})".format(
            repo_def["name"], ", ".join([e.title() for e in repo_def["extensions"]])
        ),
        label2=byline,
    )

    if not _compact:
        li.setArt({"thumb": repo_def["icon"]})

    return li


def add_repository():
    dialog = xbmcgui.Dialog()
    pool = ThreadPool()

    _user = dialog.input(settings.get_localized_string(30022)).lower()
    if not _user:
        dialog.notification(_addon_name, settings.get_localized_string(30023))
        del dialog
        return

    with tools.busy_dialog():
        splits = _user.split("/")
        addon_repos = []
        repo_items = []

        if len(splits) < 2:
            user = _user
            if API.get_user(user).get("type", "User") == "Organization":
                user_repos = API.get_org_repos(user)
            elif user == _authed_user.lower():
                access_level = [
                    "owner",
                    "collaborator" if _collaborator else "",
                    "organization_member" if _organization else "",
                ]
                user_repos = API.get_repos(",".join(access_level))
            else:
                user_repos = API.get_user_repos(user)

            for user_repo in user_repos:
                if "message" in user_repo:
                    dialog.ok(_addon_name, settings.get_localized_string(30065))
                    del dialog
                    return
                pool.put(get_repo_info, user_repo)
            repos = pool.wait_completion()
            if not repos:
                dialog.ok(_addon_name, settings.get_localized_string(30066))
                del dialog
                return

            repos.sort(key=lambda b: b["updated_at"], reverse=True)
        else:
            user, repo = splits[:1]
            subdir = splits[2] if len(splits) > 2 else ""

            if not subdir:
                repos = get_repo_info(API.get_repo(user, repo))

        addon_repos = [i["repo_name"] for i in repos]
        if len(addon_repos) == 0:
            dialog.ok(_addon_name, settings.get_localized_string(30058))
            del dialog
            return

        for i in repos:
            li = _build_repo_listitem(i, user)
            repo_items.append(li)

        selection = dialog.select(
            settings.get_localized_string(30011),
            repo_items,
            useDetails=not _compact,
        )
        if selection < 0:
            del dialog
            return

        if len(splits) < 2:
            user = repos[selection]["user"]
            repo = addon_repos[selection]

        subdir = repos[selection].get("subdirectory")

    if not _check_repo(user, repo):
        del dialog
        return

    addon_xml = API.get_contents(
        user, repo, "{}/addon.xml".format(subdir) if subdir else "addon.xml", raw=True
    )
    if not addon_xml:
        del dialog
        return

    tools.log("Reading {}/addon.xml from {}/{}".format(subdir, user, repo))
    addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

    name = addon.get("name")
    plugin_id = addon.get("id")

    if dialog.yesno(_addon_name, settings.get_localized_string(30059).format(name)):
        _add_repo(user, repo, name, plugin_id, subdir=subdir)
    del dialog


def get_commit_info(user, repo, sha):
    return [API.get_commit(user, repo, sha)]


def sort_branches(repo, branches):
    _default = API.get_default_branch(repo["user"], repo["repo_name"])

    default_branch = []
    protected_branches = []
    normal_branches = []

    for i in sorted(branches, key=lambda b: b["updated_at"], reverse=True):
        if i["name"] == _default:
            default_branch.append(i)
        elif i["protected"]:
            protected_branches.append(i)
        else:
            normal_branches.append(i)

    sorted_branches = default_branch + protected_branches + normal_branches

    return default_branch, protected_branches, sorted_branches


def _add_repo(
    user, repo, name, plugin_id, timestamp=None, update=False, path=None, subdir=""
):
    dialog = xbmcgui.Dialog()

    key = user + "-" + plugin_id
    addon_def = {
        key: {
            "user": user,
            "repo_name": repo,
            "name": name,
            "plugin_id": plugin_id,
            "exclude_items": [],
            "timestamp": timestamp or time.time(),
            "subdirectory": subdir,
        }
    }
    filename = key + ".json"

    tools.create_folder(_json_path)
    tools.write_to_file(
        os.path.join(_json_path, filename) if path is None else path,
        json.dumps(addon_def, indent=4),
    )

    if not update:
        dialog.notification(_addon_name, settings.get_localized_string(30025))
        _prompt_for_update(key)
    del dialog


def _update_repo(repo, **kwargs):
    key = "{}-{}".format(repo["user"], repo["plugin_id"])
    repo_def = get_repos(key)
    repo_def.update(**kwargs)

    tools.create_folder(_json_path)
    tools.write_to_file(
        repo_def["filename"],
        json.dumps({key: repo_def}, indent=4),
    )


def _check_repo(user, repo):
    dialog = xbmcgui.Dialog()

    can_get = API.get("repos/{}/{}".format(user, repo))
    if not can_get.ok:
        dialog.ok(_addon_name, settings.get_localized_string(30024))
        del dialog
        return False
    return True


def _prompt_for_update(key):
    dialog = xbmcgui.Dialog()

    if dialog.yesno(_addon_name, settings.get_localized_string(30053)):
        tools.execute_builtin(
            "RunScript({},action=update_addon,id={})".format(_addon_id, key)
        )
    del dialog


def remove_repository(repo):
    dialog = xbmcgui.Dialog()
    repos = get_repos()

    filename = repo["filename"]
    repo_defs = [i for i in repos.values()]

    indices = [i for i, x in enumerate(repo_defs) if x["filename"] == filename]
    if len(indices) > 1:
        remove = dialog.yesno(
            _addon_name,
            settings.get_localized_string(30026).format(
                ", ".join([repo_defs[i]["name"] for i in indices])
            ),
        )
    else:
        remove = dialog.yesno(
            _addon_name, settings.get_localized_string(30027).format(repo["name"])
        )
    if remove:
        os.remove(filename)
        dialog.notification(
            _addon_name,
            settings.get_localized_string(30028 if len(indices) == 1 else 30029).format(
                len(indices)
            ),
        )
    del dialog


def _get_repo_subdirectories(user, repo):
    contents = API.get_contents(user, repo)
    if not contents:
        return []

    subdirs = []
    if type(contents) == list:
        for i in [i for i in contents if i.get("type") == "dir"]:
            subdirs.append(i)
    elif type(contents) == dict and contents.get("type") == "dir":
        subdirs.append(contents)

    return subdirs


def get_repo_info(repo_def, subdir=None):
    repo_infos = []

    user = repo_def["owner"]["login"]
    repo = repo_def["name"]
    addon_xml = API.get_contents(
        user,
        repo,
        "{}/addon.xml".format(subdir) if subdir else "addon.xml",
        raw=True,
    )
    if not addon_xml and _search_subdirs:
        subdirectories = _get_repo_subdirectories(user, repo)
        for dir in subdirectories:
            repo_infos.append(get_repo_info(repo_def, dir["name"]))
    else:
        tools.log("Reading {}/addon.xml from {}/{}".format(subdir, user, repo))
        addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

        def_name = addon.get("name")
        def_id = addon.get("id")

        icon = get_icon(
            user, repo, plugin_id=def_id, addon_xml=addon_xml, subdir=subdir
        )
        extensions = get_extensions(user, repo, addon_xml=addon_xml, subdir=subdir)

        repo_infos.append(
            {
                "name": def_name,
                "user": user,
                "repo_name": repo,
                "updated_at": repo_def["updated_at"],
                "icon": icon,
                "extensions": extensions,
                "subdirectory": "",
            }
        )

    return repo_infos


def get_branch_info(repo, branch):
    branch = API.get_repo_branch(
        repo["user"],
        repo["repo_name"],
        branch["name"] if type(branch) == dict else branch,
    )
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


def get_icon(user, repo, plugin_id, addon_xml=None, subdir=None):
    icon = ""

    addon_path = os.path.join(_addons, plugin_id)
    if os.path.exists(addon_path):
        addon_xml = tools.read_from_file(os.path.join(addon_path, "addon.xml"))
    if not addon_xml:
        addon_xml = API.get_contents(
            user,
            repo,
            "{}/addon.xml".format(subdir) if subdir else "addon.xml",
            raw=True,
        )

    if addon_xml:
        tools.log("Finding icon in {}/addon.xml from {}/{}".format(subdir, user, repo))
        addon = tools.parse_xml(text=addon_xml.encode("utf-8"))

        try:
            icon_path = "icon.png"
            def_icon = list(addon.iter("icon"))

            if def_icon and len(def_icon) > 0:
                icon_path = def_icon[0].text

            if os.path.exists(addon_path):
                icon = os.path.join(addon_path, icon_path)
            else:
                icon_url = API.get_contents(
                    user,
                    repo,
                    "{}/{}".format(subdir, icon_path) if subdir else icon_path,
                )["download_url"]
                icon = requests.head(icon_url, allow_redirects=True).url
        except Exception as e:
            tools.log("Could not get icon: {}".format(e), level="warning")

    return icon


def get_extensions(user, repo, addon_xml=None, subdir=None):
    extensions = []
    if not addon_xml:
        addon_xml = API.get_contents(user, repo, "addon.xml", raw=True)

    if addon_xml:
        tools.log(
            "Checking for extensions in {}/addon.xml from {}/{}".format(
                subdir, user, repo
            )
        )
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


def repo_menu():
    dialog = xbmcgui.Dialog()
    repos = get_repos()

    repo_items = []
    with tools.busy_dialog():
        add = xbmcgui.ListItem(
            settings.get_localized_string(30002),
            label2=settings.get_localized_string(30056),
        )
        add.setArt({"thumb": os.path.join(_media_path, "plus.png")})
        repo_items.append(add)

        repo_defs = sorted(
            repos.values(),
            key=lambda b: b.get("timestamp", 0) if _sort_repos else b.get("name"),
            reverse=True,
        )
        for repo in repo_defs:
            user = repo["user"]
            repo_name = repo["repo_name"]
            name = repo["name"]
            plugin_id = repo["plugin_id"]

            li = xbmcgui.ListItem(
                name,
                label2="{} - ".format(repo_name)
                + settings.get_localized_string(30049).format(user),
            )

            if not _compact:
                li.setArt({"thumb": get_icon(user, repo_name, plugin_id)})

            repo_items.append(li)

    selection = dialog.select(
        settings.get_localized_string(30011), repo_items, useDetails=not _compact
    )
    if selection == -1:
        dialog.notification(_addon_name, settings.get_localized_string(30023))
        del dialog
        return None
    else:
        del dialog
        if selection == 0:
            add_repository()
        else:
            manage_menu(repo_defs[selection - 1])


def _exclude_filter(repo):
    excludes = repo.get("exclude_items")
    addon_path = os.path.join(_addons, repo["plugin_id"])

    dialog = xbmcgui.Dialog()
    if not os.path.exists(addon_path):
        dialog.ok(
            settings.get_localized_string(30095),
            settings.get_localized_string(30097),
        )
        return

    items = sorted(
        [
            "/{}".format(i)
            for i in os.listdir(addon_path)
            if os.path.isdir(os.path.join(addon_path, i))
        ]
    )
    items += sorted(
        [
            i
            for i in os.listdir(addon_path)
            if not os.path.isdir(os.path.join(addon_path, i))
        ]
    )
    if excludes is not None:
        items += excludes

    selected = []
    list_items = []
    for i in items:
        li = xbmcgui.ListItem(i)
        if not _compact:
            art = "file.png"
            if os.path.isdir(os.path.join(addon_path, i.lstrip('/'))):
                art = "folder.png"
            else:
                ext = i.split('.')[-1]
                file = os.path.join(_media_path, "{}.png".format(ext))
                if os.path.exists(file):
                    art = "{}.png".format(ext)
            li.setArt({"thumb": os.path.join(_media_path, art)})
        list_items.append(li)

        if i in excludes or i.startswith(('.', "/.")):
            selected.append(items.index(i))

    selection = dialog.multiselect(
        settings.get_localized_string(30100),
        list_items,
        preselect=selected,
        useDetails=not _compact,
    )

    if selection is None:
        dialog.notification(_addon_name, settings.get_localized_string(30101))
        del dialog
        return
    else:
        excluded_items = [items[i] for i in selection]
        if excluded_items == excludes:
            dialog.notification(_addon_name, settings.get_localized_string(30101))
            del dialog
            return

    update = dialog.yesno(
        settings.get_localized_string(30095),
        settings.get_localized_string(30098).format(
            color.color_string(len(selection)),
            color.color_string(repo["repo_name"]),
        ),
    )

    if update:
        _update_repo(repo, exclude_items=excluded_items)
        delete = dialog.yesno(
            settings.get_localized_string(30095), settings.get_localized_string(30099)
        )
        del dialog
        if delete:
            for i in excluded_items:
                filepath = os.path.join(addon_path, i.lstrip('/'))
                if os.path.isdir(filepath):
                    tools.remove_folder(filepath)
                else:
                    tools.remove_file(filepath)
    else:
        dialog.notification(_addon_name, settings.get_localized_string(30101))
        del dialog
        return


def manage_menu(repo):
    actions = tools.build_menu(
        [
            (30000, 30054, update_addon.update_menu, "update.png", {"repo": repo}),
            (
                30001,
                30055,
                raise_issue.raise_issue,
                "issue.png",
                {"selection": repo},
            ),
            (30095, 30096, _exclude_filter, "xor.png", {"repo": repo}),
            (30003, 30057, remove_repository, "minus.png", {"repo": repo}),
        ]
    )

    _update_repo(repo, timestamp=time.time())

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
