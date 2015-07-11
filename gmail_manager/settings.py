"""
Settings for REST framework are all namespaced in the REST_FRAMEWORK setting.
For example your project's `settings.py` file might look like this:

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.TemplateHTMLRenderer',
    )
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.TemplateHTMLRenderer',
    )
}

This module provides the `api_setting` object, that is used to access
REST framework settings, checking for user settings first, then falling
back to the defaults.
"""
from django.conf import settings
from django.core.signals import setting_changed

USER_SETTINGS = getattr(settings, 'GMAIL_MANAGER', None)

DEFAULTS = {
    'CLIENT_ID': '',
    'CLIENT_SECRET': '',
    'CALLBACK_URL': 'http://localhost:8000/gmailmanager/callback/'
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
    if setting == 'GMAIL_MANAGER':
        gmail_settings = APISettings(value, DEFAULTS)


setting_changed.connect(reload_gmail_settings)
