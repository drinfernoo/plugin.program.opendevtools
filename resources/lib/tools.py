# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmc
import xbmcgui
import xbmcvfs

import collections
from contextlib import contextmanager
from dateutil import parser
from dateutil import tz
import hashlib
import json
import os
import shutil
import sys
from xml.etree import ElementTree

from resources.lib import settings

try:
    translate_path = xbmcvfs.translatePath
except AttributeError:
    translate_path = xbmc.translatePath

_addon_name = settings.get_addon_info("name")
_addon_data = translate_path(settings.get_addon_info("profile"))
_addon_path = translate_path(settings.get_addon_info("path"))
_media_path = os.path.join(_addon_path, "resources", "media")
_temp = translate_path("special://temp")

_log_levels = {
    "debug": xbmc.LOGDEBUG,
    "info": xbmc.LOGINFO,
    "warning": xbmc.LOGWARNING,
    "error": xbmc.LOGERROR,
    "fatal": xbmc.LOGFATAL,
}


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
    execute_builtin("LoadProfile({})".format(xbmc.getInfoLabel("system.profilename")))


def reload_skin():
    execute_builtin("ReloadSkin()")


def remove_folder(path):
    if xbmcvfs.exists(ensure_path_is_dir(path)):
        log("Removing {}".format(path))
        try:
            shutil.rmtree(path)
        except Exception as e:
            log("Error removing {}: {}".format(path, e))


def remove_file(path):
    if xbmcvfs.exists(path):
        log("Removing {}".format(path))
        try:
            os.remove(path)
        except Exception as e:
            log("Error removing {}: {}".format(path, e))


def cleanup_old_files():
    log("Cleaning up old files...")
    for i in [i for i in xbmcvfs.listdir(_addon_data)[1] if not i.endswith(".xml")]:
        remove_file(os.path.join(_addon_data, i))


def clear_temp():
    try:
        for item in os.listdir(_temp):
            path = os.path.join(_temp, item)
            if os.path.isdir(path):
                os.remove(path)
            elif os.path.isfile(path) and path not in ["kodi.log"]:
                shutil.rmtree(path)
    except (OSError, IOError) as e:
        log("Failed to cleanup temporary storage: {}".format(e))


def read_from_file(file_path, bytes=False):
    content = None
    try:
        f = xbmcvfs.File(file_path, "r")
        if bytes:
            content = f.readBytes()
        else:
            content = f.read()
            if sys.version_info < (3, 0, 0):
                content = content.decode("utf-8-sig")
    except IOError:
        return None
    finally:
        try:
            f.close()
        except:
            pass
    return content


def write_to_file(file_path, content, bytes=False):
    if sys.version_info < (3, 0, 0) and not bytes:
        content = content.encode("utf-8")

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


def parse_xml(file=None, text=None):
    if (file and text) or not (file or text):
        raise ValueError("Incorrect parameters for parsing.")
    if file and not text:
        text = read_from_file(file)

    text = text.strip()
    root = None
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        log("Error parsing XML: {}".format(e), level="error")
    return root


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


def smart_merge_dictionary(
    dictionary, merge_dict, keep_original=False, extend_array=True
):
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
            if (
                extend_array
                and isinstance(original_value, (list, set))
                and isinstance(new_value, (list, set))
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


def log(msg, level="debug"):
    xbmc.log(_addon_name + ": " + msg, level=_log_levels[level])


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
    date_long = xbmc.getRegion("datelong")
    time_long = xbmc.getRegion("time")
    format_string = settings.get_localized_string(30035).format(date_long, time_long)

    utc_parsed = parser.parse(utc_time)
    local_time = utc_parsed.astimezone(tz.tzlocal())

    return local_time.strftime(format_string)


def create_folder(path):
    path = ensure_path_is_dir(path)
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdir(path)


def copytree(src, dst, symlinks=False, ignore=None):
    create_folder(dst)
    hashes = {}
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            hashes.update(copytree(s, d, symlinks, ignore))
        else:
            hashes[d] = (
                get_md5_hash(s),
                get_md5_hash(d) if os.path.exists(d) else None,
            )
            if hashes[d][0] != hashes[d][1]:
                remove_file(d)
                shutil.copy2(s, d)
    return hashes


def get_condition(condition):
    return xbmc.getCondVisibility(condition)


def execute_builtin(bi):
    xbmc.executebuiltin(bi)


def execute_jsonrpc(params):
    params.update({"id": 1, "jsonrpc": "2.0"})
    call = json.dumps(params)
    response = xbmc.executeJSONRPC(call)
    return json.loads(response)


def get_current_skin():
    params = {
        "method": "GUI.GetProperties",
        "params": {"properties": ["skin"]},
    }

    skin = execute_jsonrpc(params).get("result", {}).get("skin", {}).get("id")
    return skin


def copy2clip(txt):
    import subprocess

    platform = sys.platform
    if platform == "win32":
        try:
            cmd = "echo " + txt.strip() + "|clip"
            subprocess.check_call(cmd, shell=True)
        except Exception as e:
            log("Failure to copy to clipboard, \n{}".format(e), "error")
            return False
        return True
    elif platform.startswith("linux") or platform == "darwin":
        try:
            cmd = "pbcopy" if platform == "darwin" else ["xsel", "-pi"]
            kwargs = (
                {"stdin": subprocess.PIPE, "text": True}
                if sys.version_info > (3, 0, 0)
                else {"stdin": subprocess.PIPE}
            )
            p = subprocess.Popen(cmd, **kwargs)
            p.communicate(input=str(txt))
        except Exception as e:
            log("Failure to copy to clipboard, \n{}".format(e), "error")
            return False
        return True
    return False


def get_md5_hash(file):
    md5 = hashlib.md5(read_from_file(file, bytes=True))
    return md5.hexdigest()
