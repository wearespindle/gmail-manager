"""
Settings for GMail Manager are all namespaced in the GMAILMANAGER setting.
For example your project's `settings.py` file might look like this:

GMAILMANAGER = {
    'CLIENT_ID': '1234abcd',
    'CLIENT_SECRET': 'abcd1234',
}

This module provides the `gmail_settings` object, that is used to access
GMail Manager settings, checking for user settings first, then falling
back to the defaults.
"""
from django.conf import settings
from django.core.signals import setting_changed

USER_SETTINGS = getattr(settings, 'GMAILMANAGER', None)

DEFAULTS = {
    'CLIENT_ID': '',
    'CLIENT_SECRET': '',
    'CALLBACK_URL': 'http://localhost:8000/gmailmanager/callback/',
    'REDIRECT_URL': None,
    'UNREAD_LABEL': 'UNREAD',
    'EMAIL_ATTACHMENT_UPLOAD_TO': 'downloads/attachments/%(message_id)d/%(filename)s',
    'SYNC_LOCK_LIFETIME': 3600,
    'REDISTOGO_URL': 'redis://redis:6379',
    'GMAIL_CHUNK_SIZE': 1024 * 1024,
}


class APISettings(object):
    """
    A settings object, that allows API settings to be accessed as properties.
    For example:

        from rest_framework.settings import api_settings
        print(api_settings.DEFAULT_RENDERER_CLASSES)

    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    """
    def __init__(self, user_settings=None, defaults=None):
        self.user_settings = user_settings or {}
        self.defaults = defaults or DEFAULTS

    def __getattr__(self, attr):
        if attr not in self.defaults.keys():
            raise AttributeError("Invalid Manager setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Cache the result
        setattr(self, attr, val)
        return val


gmail_settings = APISettings(USER_SETTINGS, DEFAULTS)


def reload_gmail_settings(*args, **kwargs):
    global gmail_settings
    setting, value = kwargs['setting'], kwargs['value']
    if setting == 'GMAILMANAGER':
        gmail_settings = APISettings(value, DEFAULTS)


setting_changed.connect(reload_gmail_settings)
