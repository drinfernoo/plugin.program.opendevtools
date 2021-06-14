# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import xbmcaddon


def get_localized_string(_id, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getLocalizedString(_id)
    del _addon
    return s


def get_setting(setting, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getSetting(setting)
    del _addon
    return s


def get_setting_boolean(setting, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getSettingBool(setting)
    del _addon
    return s


def get_setting_int(setting, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getSettingInt(setting)
    del _addon
    return s


def get_setting_float(setting, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getSettingNumber(setting)
    del _addon
    return s


def get_setting_string(setting, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getSettingString(setting)
    del _addon
    return s


def set_setting(setting, value, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.setSetting(setting, value)
    del _addon
    return s


def set_setting_boolean(setting, value, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.setSettingBool(setting, value)
    del _addon
    return s


def set_setting_int(setting, value, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.setSettingInt(setting, value)
    del _addon
    return s


def set_setting_float(setting, value, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.setSettingNumber(setting, value)
    del _addon
    return s


def set_setting_string(setting, value, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.setSettingString(setting, value)
    del _addon
    return s


def open_settings(addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.openSettings()
    del _addon
    return s


def get_addon_info(label, addon=None):
    _addon = xbmcaddon.Addon() if not addon else xbmcaddon.Addon(addon)
    s = _addon.getAddonInfo(label)
    del _addon
    return s
