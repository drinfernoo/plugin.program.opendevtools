# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import sys

from resources.lib import color
from resources.lib import menu
from resources.lib import oauth
from resources.lib import update_addon


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
            update_addon.update_menu(id)
    else:
        menu.main_menu()


if __name__ == "__main__":
    _do_action()
