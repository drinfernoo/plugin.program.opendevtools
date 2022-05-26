# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcgui

import os
import time

from resources.lib import color
from resources.lib import logging
from resources.lib import oauth
from resources.lib import raise_issue
from resources.lib import repository
from resources.lib import settings
from resources.lib import tools
from resources.lib import update_addon
from resources.lib.github_api import GithubAPI
from resources.lib.thread_pool import ThreadPool

API = GithubAPI()

_addon_name = settings.get_addon_info("name")
_addon_path = tools.translate_path(settings.get_addon_info("path"))

_media_path = os.path.join(_addon_path, "resources", "media")

_compact = settings.get_setting_boolean("general.compact")
_sort_repos = settings.get_setting_int("general.sort_repos")
_commit_stats = settings.get_setting_boolean("general.show_commit_stats")


def _build_menu(items):
    action_items = []
    for action in items:
        li = xbmcgui.ListItem(
            settings.get_localized_string(action[0])
            if type(action[0]) == int
            else action[0],
            label2=settings.get_localized_string(action[1])
            if type(action[1]) == int
            else action[1],
        )
        li.setArt({"thumb": os.path.join(_media_path, action[3])})
        action_items.append(li)
    return (items, action_items)


def main_menu():
    auth = oauth.check_auth()

    if auth:
        actions = _build_menu(
            [
                (30074, 30075, repo_menu, "github.png"),
                (
                    30069,
                    30070,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )
    else:
        actions = _build_menu(
            [
                (30043, 30071, oauth.authorize, "github.png", {"in_addon": True}),
                (
                    30069,
                    30070,
                    logging.upload_log,
                    "log.png",
                    {"choose": True, "dialog": True},
                ),
            ]
        )

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


def repo_menu():
    dialog = xbmcgui.Dialog()
    repos = repository.get_repos()

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
                li.setArt({"thumb": repository.get_icon(user, repo_name, plugin_id)})

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
            repository.add_repository()
        else:
            manage_menu(repo_defs[selection - 1])


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
            update_addon.update_addon,
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
            (30084, 30094, tag_menu, "tag.png", {"repo": repo, "repo_tags": repo_tags})
        )

    if len(repo_branches) > 1:
        action_items.append(
            (
                30086,
                30087,
                branch_menu,
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
                commit_menu,
                "commit.png",
                {
                    "repo": repo,
                    "branch": repository.get_branch_info(repo, default_branch)[0][
                        "branch"
                    ],
                },
            )
        )

    actions = _build_menu(action_items)

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


def manage_menu(repo):
    actions = _build_menu(
        [
            (30000, 30054, update_menu, "update.png", {"repo": repo}),
            (
                30001,
                30055,
                raise_issue.raise_issue,
                "issue.png",
                {"selection": repo},
            ),
            (30095, 30096, repository.exclude_filter, "xor.png", {"repo": repo}),
            (30003, 30057, repository.remove_repository, "minus.png", {"repo": repo}),
        ]
    )

    repository.update_repo(repo, timestamp=time.time())

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


def tag_menu(repo, repo_tags):
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


def branch_menu(repo, repo_branches):
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
        commit_menu(repo, sorted_branches[selection])
    else:
        del dialog
        return


def commit_menu(repo, branch):
    pool = ThreadPool()

    commits = []
    commit_items = []
    with tools.busy_dialog():
        for branch_commit in list(
            API.get_branch_commits(repo["user"], repo["repo_name"], branch["name"])
        ):
            pool.put(
                update_addon.get_commit_info,
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
        update_addon.update_addon(
            repo, sorted_commits[selection], sorted_commits[selection]["sha"][:7]
        )
    else:
        dialog.notification(_addon_name, settings.get_localized_string(30015))
        del dialog
