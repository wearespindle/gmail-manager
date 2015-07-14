from django.conf.urls import patterns, url

from .views import SetupEmailAuthView, OAuth2CallbackView

urlpatterns = patterns(
    '',
    url(r'^setup/$', SetupEmailAuthView.as_view(), name='gmail_setup'),
    url(r'^callback/$', OAuth2CallbackView.as_view(), name='gmail_callback'),
)
