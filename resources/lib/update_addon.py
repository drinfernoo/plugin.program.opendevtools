# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

from xml.etree import ElementTree

import os
import re
import sqlite3
import time
import zipfile

from resources.lib import color
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI

API = GithubAPI()

_addon_name = settings.get_addon_info("name")

_dependencies = settings.get_setting_boolean("general.dependencies")
_add_webpdb = settings.get_setting_boolean("general.add_webpdb")

_home = tools.translate_path("special://home")
_temp = tools.translate_path("special://temp")
_database = tools.translate_path("special://database")
_addons = os.path.join(_home, "addons")
_addon_data = tools.translate_path(settings.get_addon_info("profile"))


def _download_files_in_folder(user, repo, subdir="", sha="HEAD"):
    tree = API.get_tree(user, repo, commit_sha=sha, recursive=True)
    
    contents = [i for i in tree["tree"] if i["path"].startswith(subdir)]
    tools.remove_folder(os.path.join(_addons, subdir))
    
    for entry in contents:
        path = os.path.join(_addons, entry["path"])
        if entry["type"] == "tree":
            tools.create_folder(path)
        elif entry["type"] == "blob":
            tools.write_to_file(path, API.get_file(entry["url"]), True)


def _get_zip_file(user, repo, branch=None, sha=None):
    if (sha and branch) or not (sha or branch):
        raise ValueError("Cannot specify both branch and sha")
    else:
        return _store_zip_file(API.get_zipball(user, repo, sha if sha else branch))


def _store_zip_file(zip_contents):
    zip_location = os.path.join(_addon_data, "{}.zip".format(int(time.time())))
    tools.write_to_file(zip_location, zip_contents, bytes=True)

    return zip_location


def _extract_addon(zip_location, repo):
    tools.log("Opening {}".format(zip_location))
    with zipfile.ZipFile(zip_location) as file:
        base_directory = (
            os.path.join(file.namelist()[0], repo.get("subdirectory"))
            if repo.get("subdirectory")
            else file.namelist()[0]
        )
        tools.log("Extracting to: {}".format(os.path.join(_temp, base_directory)))
        for f in [
            i
            for i in file.namelist()
            if all(e not in i for e in repo.get("exclude_items", []))
        ]:
            try:
                file.extract(f, _temp)
            except Exception as e:
                tools.log("Could not extract {}: {}".format(f, e))
    install_path = os.path.join(_addons, repo["plugin_id"])
    hashes = tools.copytree(
        os.path.join(_temp, base_directory), install_path, ignore=True
    )
    tools.remove_folder(os.path.join(_temp, base_directory))
    tools.remove_file(zip_location)
    return hashes


def _cleanup_addon(hashes, repo):
    install_path = os.path.join(_addons, repo["plugin_id"])
    existing_files = {
        os.path.join(dp, f) for dp, dn, fn in os.walk(install_path) for f in fn
    }
    leftovers = existing_files.difference(set(hashes.keys()))
    for file in leftovers:
        tools.remove_file(file)


def _update_addon_version(addon, gitsha):
    addon_xml = os.path.join(_addons, addon, "addon.xml")
    tools.log("Rewriting addon version: {}".format(addon_xml))

    replace_regex = r'<\1"\2.\3.\4-{}"\7>'.format(gitsha[:7])

    content = tools.read_from_file(addon_xml)
    content = re.sub(
        r"<(addon id.*version=)\"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+)?(-.*?)?\"(.*)>",
        replace_regex,
        content,
    )
    tools.write_to_file(addon_xml, content)


def _add_webpdb_to_addon(addon):
    addon_xml_path = os.path.join(_addons, addon, "addon.xml")
    if os.path.exists(addon_xml_path):
        addon_xml = ElementTree.parse(addon_xml_path)
        addon_root = addon_xml.getroot()
        requires = addon_root.find("requires")
        if requires is not None:
            requires.append(
                ElementTree.Element("import", {"addon": "script.module.web-pdb"})
            )
        else:
            requires = ElementTree.Element("requires")
            requires.append(
                ElementTree.Element("import", {"addon": "script.module.web-pdb"})
            )
            addon_root.append(requires)
        addon_xml.write(addon_xml_path, encoding="utf-8", xml_declaration=True)


def _rewrite_kodi_dependency_versions(addon):
    kodi_version = tools.kodi_version()
    tools.log("KODI_VERSION: {}".format(kodi_version))
    kodi_dep_versions = {
        18: {"xbmc.python": "2.26.0", "xbmc.gui": "5.14.0"},
        19: {"xbmc.python": "3.0.0", "xbmc.gui": "5.15.0"},
    }

    if kodi_version in kodi_dep_versions:
        kodi_deps = kodi_dep_versions[kodi_version]
    else:
        # Take latest version if we don't have version specific
        kodi_deps = kodi_dep_versions[max(kodi_dep_versions)]
    tools.log("KODI DEPENDENCY VERSIONS: {}".format(kodi_deps))

    addon_xml = os.path.join(_addons, addon, "addon.xml")
    tools.log("Rewriting {}".format(addon_xml))

    content = tools.read_from_file(addon_xml)
    for dep in kodi_deps:
        content = re.sub(
            '<import addon="' + dep + r'" version=".*?"\s?/>',
            '<import addon="' + dep + '" version="' + kodi_deps[dep] + '" />',
            content,
        )
    tools.write_to_file(addon_xml, content)


def _install_deps(addon):
    failed_deps = []
    visible_cond = "Window.IsTopMost(yesnodialog)"

    xml_path = os.path.join(_addons, addon, "addon.xml")
    tools.log("Finding dependencies in {}".format(xml_path))
    root = tools.parse_xml(file=xml_path)
    if root is None:
        return

    requires = root.find("requires")
    if not requires:
        return
    deps = requires.findall("import")

    for dep in [
        d
        for d in deps
        if not d.get("addon").startswith("xbmc") and not d.get("optional") == "true"
    ]:
        plugin_id = dep.get("addon")
        installed_cond = "System.HasAddon({0})".format(plugin_id)
        if tools.get_condition(installed_cond):
            continue

        tools.log("Installing dependency: {}".format(plugin_id))
        tools.execute_builtin("InstallAddon({0})".format(plugin_id))

        clicked = False
        start = time.time()
        timeout = 10
        while not tools.get_condition(installed_cond):
            if time.time() >= start + timeout:
                tools.log(
                    "Timed out installing dependency: {}".format(plugin_id),
                    level="warning",
                )
                failed_deps.append(plugin_id)
                break

            tools.sleep(500)

            if tools.get_condition(visible_cond) and not clicked:
                tools.log("Dialog to click open")
                tools.execute_builtin("SendClick(yesnodialog, 11)")
                clicked = True
            else:
                tools.log("...waiting")
    return failed_deps


def _get_addons_db():
    for db in os.listdir(_database):
        if db.lower().startswith("addons") and db.lower().endswith(".db"):
            return os.path.join(_database, db)


def _set_enabled(addon, enabled, exists=True):
    enabled_params = {
        "method": "Addons.GetAddonDetails",
        "params": {"addonid": addon, "properties": ["enabled"]},
    }

    params = {
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon, "enabled": enabled},
    }

    if not exists and not enabled:
        return False
    elif not exists and enabled:
        db_file = _get_addons_db()
        connection = sqlite3.connect(db_file)
        cursor = connection.cursor()
        date = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM installed WHERE addonID = ?", (addon,))
        cursor.execute(
            "INSERT INTO installed (addonID, enabled, installDate) VALUES (?, 1, ?)",
            (addon, date),
        )
        connection.commit()

        connection.close()
    else:
        tools.execute_jsonrpc(params)

    new_status = (
        tools.execute_jsonrpc(enabled_params)
        .get("result", {})
        .get("addon", {})
        .get("enabled", enabled)
    ) == enabled

    tools.log(
        "{}{}{}abled".format(
            addon, " " if new_status else " not ", "en" if enabled else "dis"
        )
    )
    return new_status


def _exists(addon):
    params = {"method": "Addons.GetAddons"}

    addons = tools.execute_jsonrpc(params)
    exists = False
    if addon in [a.get("addonid") for a in addons.get("result", {}).get("addons", {})]:
        exists = True

    tools.log("{} {} installed".format(addon, "is" if exists else "not"))
    return exists


def _reload_addon(hashes):
    tools.execute_builtin("UpdateLocalAddons()")

    lang_files_changed = False
    for file in [i for i in hashes if i.endswith(".po")]:
        if hashes[file][0] != hashes[file][1]:
            lang_files_changed = True
            break

    if not lang_files_changed:
        return

    get_lang_params = {
        "method": "Settings.GetSettingValue",
        "params": {"setting": "locale.language"},
    }
    set_lang_params = {
        "method": "Settings.SetSettingValue",
        "params": {"setting": "locale.language", "value": ""},
    }

    current_language = (
        tools.execute_jsonrpc(get_lang_params).get("result", {}).get("value", "")
    )

    for lang in ["resource.language.foo_bar", current_language]:
        set_lang_params["params"]["value"] = lang
        tools.execute_jsonrpc(set_lang_params)
        tools.sleep(1000)


def get_commit_info(user, repo, sha):
    return [API.get_commit(user, repo, sha)]


def update_addon(repo, commit=None, label=None):
    dialog = xbmcgui.Dialog()
    tools.cleanup_old_files()

    if not dialog.yesno(
        settings.get_localized_string(30000),
        settings.get_localized_string(30018).format(
            color.color_string(repo["name"]),
            color.color_string(label),
        ),
    ):
        dialog.notification(_addon_name, settings.get_localized_string(30015))
        del dialog
        return

    progress = xbmcgui.DialogProgress()
    progress.create(
        _addon_name,
        settings.get_localized_string(30019).format(color.color_string(repo["name"])),
    )
    progress.update(0)
    
    extensions = repository.get_extensions(repo["user"], repo["repo_name"])
    plugin_id = repo["plugin_id"]
    exists = _exists(plugin_id)
    is_service = "service" in extensions
    is_current_skin = "skin" in extensions and tools.get_current_skin() == plugin_id
    
    if is_service:
        _set_enabled(plugin_id, False, exists)

    if repo.get("subdirectory"):
        _download_files_in_folder(
            repo["user"],
            repo["repo_name"],
            subdir=repo.get("subdirectory"),
            sha=commit["sha"],
        )
    else:
        location = _get_zip_file(repo["user"], repo["repo_name"], sha=commit["sha"])

        if location:
            progress.update(
                25,
                settings.get_localized_string(30020).format(
                    color.color_string(repo["name"])
                ),
            )

            tools.remove_folder(os.path.join(_addons, plugin_id))

            hashes = _extract_addon(location, repo)
            _cleanup_addon(hashes, repo)

    progress.update(
        50,
        settings.get_localized_string(30062).format(
            color.color_string(repo["name"])
        ),
    )

    if _add_webpdb:
        _add_webpdb_to_addon(plugin_id)

    _rewrite_kodi_dependency_versions(plugin_id)
    _update_addon_version(
        plugin_id,
        commit["sha"],
    )

    failed_deps = []
    if _dependencies:
        progress.update(
            75,
            settings.get_localized_string(30063).format(
                color.color_string(repo["name"])
            ),
        )
        failed_deps = _install_deps(plugin_id)

    _set_enabled(plugin_id, True, exists)

    progress.update(
        100, settings.get_localized_string(30067 if not exists else 30021)
    )

    if failed_deps:
        dialog.ok(
            _addon_name,
            settings.get_localized_string(30064).format(
                ", ".join(failed_deps), repo["name"]
            ),
        )

    if not exists:
        tools.reload_profile()
    elif is_current_skin:
        tools.reload_skin()

        _reload_addon(hashes)

        if not exists:
            tools.reload_profile()
        elif is_current_skin:
            tools.reload_skin()

    progress.close()
    del progress
    del dialog
