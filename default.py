# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import sys

from resources.lib import color
from resources.lib import menu
from resources.lib import oauth
from resources.lib import update_addon


def _build_menu(items):
    action_items = []
    for action in items:
        li = xbmcgui.ListItem(
            settings.get_localized_string(action[0]),
            label2=settings.get_localized_string(action[1]),
        )
        li.setArt({"thumb": os.path.join(_media_path, action[3])})
        action_items.append(li)
    return (items, action_items)


def _repo_menu():
    repo = repository.get_repo_selection()
    if repo is None:
        return

    actions = _build_menu(
        [
            (32000, 32069, update_addon.update_addon, "update.png", {"addon": repo}),
            (
                32001,
                32070,
                raise_issue.raise_issue,
                "issue.png",
                {"selection": {"user": repo["user"], "repo": repo["repo_name"]}},
            ),
            (32003, 32072, repository.remove_repository, "minus.png", {"repo": repo}),
        ]
    )

    dialog = xbmcgui.Dialog()
    selection = dialog.select(
        settings.get_localized_string(32004), actions[1], useDetails=not _compact
    )
    del dialog

    if selection > -1:
        if len(actions[0][selection]) == 4:
            actions[0][selection][2]()
        elif len(actions[0][selection]) == 5:
            actions[0][selection][2](**actions[0][selection][4])


def _do_action():
    if len(sys.argv) > 1:
        _params = sys.argv[1:]
        params = {i[0]: i[1] for i in [j.split("=") for j in _params]}
        action = params.get("action", None)
        id = params.get("id", None)

        if action == "color_picker":
            color.color_picker()
        elif action == "authorize":
            oauth.authorize()
        elif action == "revoke":
            oauth.revoke()
        elif action == "update_addon" and id is not None:
            update_addon.update_addon(id)
    else:
        auth = oauth.check_auth()

        if auth:
            actions = _build_menu(
                [
                    (32090, 32091, _repo_menu, "github.png"),
                    (
                        32085,
                        32086,
                        logging.upload_log,
                        "log.png",
                        {"choose": True, "dialog": True},
                    ),
                ]
            )
        else:
            actions = _build_menu(
                [
                    (32057, 32087, oauth.authorize, "github.png", {"in_addon": True}),
                    (
                        32085,
                        32086,
                        logging.upload_log,
                        "log.png",
                        {"choose": True, "dialog": True},
                    ),
                ]
            )

        dialog = xbmcgui.Dialog()
        selection = dialog.select(
            settings.get_localized_string(32004), actions[1], useDetails=not _compact
        )
        del dialog

        if selection > -1:
            if len(actions[0][selection]) == 4:
                actions[0][selection][2]()
            elif len(actions[0][selection]) == 5:
                actions[0][selection][2](**actions[0][selection][4])


if __name__ == "__main__":
    _do_action()
