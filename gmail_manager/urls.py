from django.conf.urls import patterns, url

from .views import SetupEmailAuth, OAuth2Callback

urlpatterns = patterns(
    '',
    url(r'^setup/$', SetupEmailAuth.as_view(), name='gmail_setup'),
    url(r'^callback/$', OAuth2Callback.as_view(), name='gmail_callback'),
)
