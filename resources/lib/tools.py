# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmc
import xbmcgui
import xbmcvfs

import calendar
import collections
from contextlib import contextmanager
from io import open
import os
import shutil
import sys
import time

from resources.lib import settings

try:
    translate_path = xbmcvfs.translatePath
except AttributeError:
    translate_path = xbmc.translatePath

_addon_name = settings.get_addon_info('name')


try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin

_log_levels = {'debug'  : xbmc.LOGDEBUG,
               'info'   : xbmc.LOGINFO,
               'warning': xbmc.LOGWARNING,
               'error'  : xbmc.LOGERROR,
               'fatal'  : xbmc.LOGFATAL}

_color_chart = [
    "black",
    "white",
    "whitesmoke",
    "gainsboro",
    "lightgray",
    "silver",
    "darkgray",
    "gray",
    "dimgray",
    "snow",
    "floralwhite",
    "ivory",
    "beige",
    "cornsilk",
    "antiquewhite",
    "bisque",
    "blanchedalmond",
    "burlywood",
    "darkgoldenrod",
    "ghostwhite",
    "azure",
    "aliveblue",
    "lightsaltegray",
    "lightsteelblue",
    "powderblue",
    "lightblue",
    "skyblue",
    "lightskyblue",
    "deepskyblue",
    "dodgerblue",
    "royalblue",
    "blue",
    "mediumblue",
    "midnightblue",
    "navy",
    "darkblue",
    "cornflowerblue",
    "slateblue",
    "slategray",
    "yellowgreen",
    "springgreen",
    "seagreen",
    "steelblue",
    "teal",
    "fuchsia",
    "deeppink",
    "darkmagenta",
    "blueviolet",
    "darkviolet",
    "darkorchid",
    "darkslateblue",
    "darkslategray",
    "indigo",
    "cadetblue",
    "darkcyan",
    "darkturquoise",
    "turquoise",
    "cyan",
    "paleturquoise",
    "lightcyan",
    "mintcream",
    "honeydew",
    "aqua",
    "aquamarine",
    "chartreuse",
    "greenyellow",
    "palegreen",
    "lawngreen",
    "lightgreen",
    "lime",
    "mediumspringgreen",
    "mediumturquoise",
    "lightseagreen",
    "mediumaquamarine",
    "mediumseagreen",
    "limegreen",
    "darkseagreen",
    "forestgreen",
    "green",
    "darkgreen",
    "darkolivegreen",
    "olive",
    "olivedab",
    "darkkhaki",
    "khaki",
    "gold",
    "goldenrod",
    "lightyellow",
    "lightgoldenrodyellow",
    "lemonchiffon",
    "yellow",
    "seashell",
    "lavenderblush",
    "lavender",
    "lightcoral",
    "indianred",
    "darksalmon",
    "lightsalmon",
    "pink",
    "lightpink",
    "hotpink",
    "magenta",
    "plum",
    "violet",
    "orchid",
    "palevioletred",
    "mediumvioletred",
    "purple",
    "marron",
    "mediumorchid",
    "mediumpurple",
    "mediumslateblue",
    "thistle",
    "linen",
    "mistyrose",
    "palegoldenrod",
    "oldlace",
    "papayawhip",
    "moccasin",
    "navajowhite",
    "peachpuff",
    "sandybrown",
    "peru",
    "chocolate",
    "orange",
    "darkorange",
    "tomato",
    "orangered",
    "red",
    "crimson",
    "salmon",
    "coral",
    "firebrick",
    "brown",
    "darkred",
    "tan",
    "rosybrown",
    "sienna",
    "saddlebrown",
]


def sleep(ms):
    xbmc.sleep(ms)
    

def kodi_version():
    return int(xbmc.getInfoLabel("System.BuildVersion")[:2])


@contextmanager
def busy_dialog():
    execute_builtin("ActivateWindow(busydialognocancel)")
    try:
        yield
    finally:
        execute_builtin("Dialog.Close(busydialog)")
        execute_builtin("Dialog.Close(busydialognocancel)")    


def reload_profile():
        execute_builtin('LoadProfile({})'.format(xbmc.getInfoLabel("system.profilename")))


def read_all_text(file_path):
    try:
        f = xbmcvfs.File(file_path, "r")
        content = f.read()
        if sys.version_info > (3, 0, 0):
            return content
        else:
            return content.decode("utf-8-sig")
    except IOError:
        return None
    finally:
        try:
            f.close()
        except:
            pass


def write_all_text(file_path, content):
    try:
        f = xbmcvfs.File(file_path, "w")
        return f.write(content)
    except IOError:
        return None
    finally:
        try:
            f.close()
        except:
            pass


def extend_array(array1, array2):
    """
    Safe combining of two lists
    :param array1: List to combine
    :type array1: list
    :param array2: List to combine
    :type array2: list
    :return: Combined lists
    :rtype: list
    """
    result = []
    if array1 and isinstance(array1, list):
        result.extend(array1)
    if array2 and isinstance(array2, list):
        result.extend(array2)
    return result


def smart_merge_dictionary(dictionary, merge_dict, keep_original=False, extend_array=True):
    """Method for merging large multi typed dictionaries, it has support for handling arrays.

    :param dictionary:Original dictionary to merge the second on into.
    :type dictionary:dict
    :param merge_dict:Dictionary that is used to merge into the original one.
    :type merge_dict:dict
    :param keep_original:Boolean that indicates if there are duplicated values to keep the original one.
    :type keep_original:bool
    :param extend_array:Boolean that indicates if we need to extend existing arrays with the enw values..
    :type extend_array:bool
    :return:Merged dictionary
    :rtype:dict
    """
    if not isinstance(dictionary, dict) or not isinstance(merge_dict, dict):
        return dictionary
    for new_key, new_value in merge_dict.items():
        original_value = dictionary.get(new_key, {})
        if isinstance(new_value, (dict, collections.Mapping)):
            if original_value is None:
                original_value = {}
            new_value = smart_merge_dictionary(original_value, new_value, keep_original)
        else:
            if original_value and keep_original:
                continue
            if extend_array and isinstance(original_value, (list, set)) and isinstance(
                    new_value, (list, set)
            ):
                original_value.extend(x for x in new_value if x not in original_value)
                try:
                    new_value = sorted(original_value)
                except TypeError:  # Sorting of complex array doesn't work.
                    new_value = original_value
                    pass
        if new_value:
            dictionary[new_key] = new_value
    return dictionary


def log(msg, level='debug'):
    xbmc.log(_addon_name + ': ' + msg, level=_log_levels[level])


def ensure_path_is_dir(path):
    """
    Ensure provided path string will work for kodi methods involving directories
    :param path: Path to directory
    :type path: str
    :return: Formatted path
    :rtype: str
    """
    if not path.endswith("\\") and sys.platform == "win32":
        if path.endswith("/"):
            path = path.split("/")[0]
        return path + "\\"
    elif not path.endswith("/"):
        return path + "/"
    return path
    
    
def to_local_time(utc_time):
    rem = '#' if sys.platform == 'win32' else '-'
    utc_string = '%Y-%m-%dT%H:%M:%SZ'
    format_string = settings.get_localized_string(32049).format(rem)
    
    return time.strftime(format_string, time.gmtime(calendar.timegm(time.strptime(utc_time, utc_string))))


def create_folder(path):
    path = ensure_path_is_dir(path)
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdir(path)


def color_picker():
    select_list = []
    dialog = xbmcgui.Dialog()
    current_color = settings.get_setting_string('general.color')
    for i in _color_chart:
        select_list.append(color_string(i, i))
    color = dialog.select(
        "{}: {}".format(_addon_name, settings.get_localized_string(32050)), select_list,
        preselect=_color_chart.index(current_color)
    )
    if color > -1:
        settings.set_setting_string("general.display_color", color_string(_color_chart[color], _color_chart[color]))
        settings.set_setting_string("general.color", _color_chart[color])


def color_string(text, color=None):
    return "[COLOR {}]{}[/COLOR]".format(color, text)
    
    
def copytree(src, dst, symlinks=False, ignore=None):
    create_folder(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def get_condition(condition):
    return xbmc.getCondVisibility(condition)


def execute_builtin(bi):
    xbmc.executebuiltin(bi)
