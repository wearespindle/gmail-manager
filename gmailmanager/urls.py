from django.conf.urls import patterns, url

from .views import (SetupEmailAuthView, OAuth2CallbackView, EmailMessageView, EmailAttachmentProxy,
                    EmailMessageListView, EmailMessageLabelListView, EmailMessageArchiveView, EmailMessageTrashView,
                    EmailMessageComposeView, EmailMessageDeleteView)

urlpatterns = patterns(
    '',
    url(r'^account/(?P<account_id>[\d-]+)/$', EmailMessageListView.as_view(), name='gmail_list'),
    url(
        r'^account/(?P<account_id>[\d-]+)/(?P<label_id>[\w-]+)/$',
        EmailMessageLabelListView.as_view(),
        name='gmail_label_list',
    ),
    url(r'^setup/$', SetupEmailAuthView.as_view(), name='gmail_setup'),
    url(r'^callback/$', OAuth2CallbackView.as_view(), name='gmail_callback'),
    url(r'^archive/(?P<pk>[\d-]+)/$', EmailMessageArchiveView.as_view(), name='gmail_archive'),
    url(r'^trash/(?P<pk>[\d-]+)/$', EmailMessageTrashView.as_view(), name='gmail_trash'),
    url(r'^delete/(?P<pk>[\d-]+)/$', EmailMessageDeleteView.as_view(), name='gmail_delete'),
    url(r'^html/(?P<pk>[\d-]+)/$', EmailMessageView.as_view(), name='gmail_html'),
    url(r'^compose/(?P<message_id>[\d-]+)/$', EmailMessageComposeView.as_view(), name='gmail_compose'),
    url(r'^compose/$', EmailMessageComposeView.as_view(), name='gmail_compose'),
    url(
        r'^attachment/(?P<message_id>[\d-]+)/(?P<attachment_id>[\d-]+)/(?P<file_name>[\.\w-]+)$',
        EmailAttachmentProxy.as_view(),
        name='gmail_attachment',
    ),
)
