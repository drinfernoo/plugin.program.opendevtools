# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from xml.etree import ElementTree

import os
import re
import sqlite3
import time
import zipfile

import xbmcgui

from resources.lib import color
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib.github_api import GithubAPI
from resources.lib.thread_pool import ThreadPool

API = GithubAPI()

_addon_name = settings.get_addon_info("name")

_compact = settings.get_setting_boolean("general.compact")
_dependencies = settings.get_setting_boolean("general.dependencies")
_commit_stats = settings.get_setting_boolean("general.show_commit_stats")
_add_webpdb = settings.get_setting_boolean("general.add_webpdb")

_home = tools.translate_path("special://home")
_temp = tools.translate_path("special://temp")
_database = tools.translate_path("special://database")
_addons = os.path.join(_home, "addons")
_addon_path = tools.translate_path(settings.get_addon_info("path"))
_addon_data = tools.translate_path(settings.get_addon_info("profile"))

_media_path = os.path.join(_addon_path, "resources", "media")


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
        base_directory = file.namelist()[0]
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
    for root, _, files in os.walk(install_path):
        for file in files:
            if os.path.join(root, file) not in hashes:
                tools.remove_file(os.path.join(root, file))


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


def _get_commit_info(user, repo, sha):
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

    location = _get_zip_file(repo["user"], repo["repo_name"], sha=commit["sha"])

    if location:
        progress.update(
            25,
            settings.get_localized_string(30020).format(
                color.color_string(repo["name"])
            ),
        )

        extensions = repository.get_extensions(repo["user"], repo["repo_name"])
        plugin_id = repo["plugin_id"]
        exists = _exists(plugin_id)
        is_service = "service" in extensions
        is_current_skin = "skin" in extensions and tools.get_current_skin() == plugin_id

        if is_service:
            _set_enabled(plugin_id, False, exists)

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

        _reload_addon(hashes)

        if not exists:
            tools.reload_profile()
        elif is_current_skin:
            tools.reload_skin()

    progress.close()
    del progress
    del dialog


def update_menu(repo):
    action_items = []
    with tools.busy_dialog():
        if type(repo) != dict:
            repo = repository.get_repos(repo)
        if not repo:
            return

        repo_tags = list(API.get_tags(repo["user"], repo["repo_name"]))
        default_branch = API.get_default_branch(repo["user"], repo["repo_name"])
        repo_branches = list(API.get_repo_branches(repo["user"], repo["repo_name"]))

    action_items.append(
        (
            30088,
            settings.get_localized_string(30089).format(
                color.color_string(default_branch)
            ),
            update_addon,
            "default-branch.png",
            {
                "repo": repo,
                "commit": API.get_commit(
                    repo["user"], repo["repo_name"], default_branch
                ),
                "label": default_branch,
            },
        )
    )

    if len(repo_tags) > 0 and "message" not in repo_tags[0]:
        action_items.append(
            (30084, 30094, _tag_menu, "tag.png", {"repo": repo, "repo_tags": repo_tags})
        )

    if len(repo_branches) > 1:
        action_items.append(
            (
                30086,
                30087,
                _branch_menu,
                "branch.png",
                {"repo": repo, "repo_branches": repo_branches},
            )
        )
    elif len(repo_branches) == 1:
        action_items.append(
            (
                30082,
                settings.get_localized_string(30090).format(
                    color.color_string(default_branch)
                ),
                _commit_menu,
                "commit.png",
                {
                    "repo": repo,
                    "branch": repository.get_branch_info(repo, default_branch)[0][
                        "branch"
                    ],
                },
            )
        )

    actions = tools.build_menu(action_items)

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


def _tag_menu(repo, repo_tags):
    pool = ThreadPool()

    commits = []
    tag_items = []
    tags = []
    with tools.busy_dialog():
        for tag in repo_tags:
            if "message" in tag:
                break
            tags.append((os.path.split(tag["ref"])[1], tag["object"]["sha"]))
            pool.put(
                repository.get_commit_info,
                repo["user"],
                repo["repo_name"],
                tag["object"]["sha"],
            )
        commits = pool.wait_completion()

        sorted_commits = sorted(
            commits,
            key=lambda b: b["commit"]["author"]["date"]
            if "commit" in b
            else b["author"]["date"],
            reverse=True,
        )

        for commit in sorted_commits:
            tag = [i[0] for i in tags if i[1] == commit["sha"]][0]
            label = color.color_string(tag)
            if label not in [i.getLabel() for i in tag_items]:
                li = xbmcgui.ListItem(label)
                if not _compact:
                    li.setArt({"thumb": os.path.join(_media_path, "tag.png")})
                tag_items.append(li)

    dialog = xbmcgui.Dialog()
    selection = dialog.select(
        settings.get_localized_string(30014), tag_items, useDetails=not _compact
    )
    del dialog

    if selection > -1:
        sha = sorted_commits[selection]["sha"]
        update_addon(
            repo,
            sorted_commits[selection],
            [i[0] for i in tags if i[1] == sha][0],
        )


def _branch_menu(repo, repo_branches):
    dialog = xbmcgui.Dialog()
    pool = ThreadPool()

    with tools.busy_dialog():
        for branch in repo_branches:
            if "message" in branch:
                break
            pool.put(repository.get_branch_info, repo, branch)
        branches = pool.wait_completion()
        default_branch, protected_branches, sorted_branches = repository.sort_branches(
            repo, branches
        )

        branch_items = []
        for i in sorted_branches:
            date = tools.to_local_time(i["updated_at"])
            li = xbmcgui.ListItem(
                "{} - ({})".format(
                    i["branch"]["name"], color.color_string(i["sha"][:7])
                ),
                label2=settings.get_localized_string(30016).format(date),
            )

            if not _compact:
                art = os.path.join(_media_path, "branch.png")
                if i in default_branch:
                    art = os.path.join(_media_path, "default-branch.png")
                elif i in protected_branches:
                    art = os.path.join(_media_path, "protected-branch.png")
                li.setArt({"thumb": art})

            branch_items.append(li)
    selection = dialog.select(
        settings.get_localized_string(30017), branch_items, useDetails=not _compact
    )
    if selection > -1:
        _commit_menu(repo, sorted_branches[selection])
    else:
        del dialog
        return


def _commit_menu(repo, branch):
    pool = ThreadPool()

    commits = []
    commit_items = []
    with tools.busy_dialog():
        for branch_commit in list(
            API.get_branch_commits(repo["user"], repo["repo_name"], branch["name"])
        ):
            pool.put(
                _get_commit_info,
                repo["user"],
                repo["repo_name"],
                branch_commit["sha"],
            )
        commits = pool.wait_completion()

        sorted_commits = sorted(
            commits,
            key=lambda b: b["commit"]["author"]["date"]
            if "commit" in b
            else b["author"]["date"],
            reverse=True,
        )

        for commit in sorted_commits:
            date = tools.to_local_time(commit["commit"]["author"]["date"])
            byline = settings.get_localized_string(30013).format(
                commit["commit"]["author"]["name"], date
            )
            if _commit_stats:
                stats = commit['stats']
                adds = stats.get("additions", 0)
                deletes = stats.get("deletions", 0)
                add_text = (
                    color.color_string("[B]+[/B] {}".format(adds), "springgreen")
                    if adds > 0
                    else "[B]+[/B] {}".format(adds)
                )
                delete_text = (
                    color.color_string("[B]-[/B] {}".format(deletes), "crimson")
                    if deletes > 0
                    else "[B]-[/B] {}".format(deletes)
                )

                byline = "{} {}: ".format(add_text, delete_text) + byline
            li = xbmcgui.ListItem(
                "{} - {}".format(
                    color.color_string(commit["sha"][:7]),
                    commit["commit"]["message"].replace("\n", "; "),
                ),
                label2=byline,
            )

            if not _compact:
                art = os.path.join(_media_path, "commit.png")
                if "pull" in commit["commit"]["message"]:
                    art = os.path.join(_media_path, "pull.png")
                elif "merge" in commit["commit"]["message"]:
                    art = os.path.join(_media_path, "merge.png")

                li.setArt({"thumb": art})

            commit_items.append(li)

    dialog = xbmcgui.Dialog()
    selection = dialog.select(
        settings.get_localized_string(30014), commit_items, useDetails=not _compact
    )

    if selection > -1:
        del dialog
        update_addon(
            repo, sorted_commits[selection], sorted_commits[selection]["sha"][:7]
        )
    else:
        dialog.notification(_addon_name, settings.get_localized_string(30015))
        del dialog
