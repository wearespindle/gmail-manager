import logging
import mimetypes

import anyjson
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404, HttpResponse
from django.views.generic import View, DetailView, ListView, FormView
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.xsrfutil import generate_token, validate_token

from .body_parser import render_email_body
from .forms import ComposeEmailForm
from .models import (EmailAccount, EmailMessage, EmailAttachment, EmailOutboxMessage)
from .settings import gmail_settings
from .tasks import (toggle_read_email_message, archive_email_message, trash_email_message, delete_email_message,
                    send_message)
from .utils import get_attachment_filename_from_url


logger = logging.getLogger(__name__)


FLOW = OAuth2WebServerFlow(
    client_id=gmail_settings.CLIENT_ID,
    client_secret=gmail_settings.CLIENT_SECRET,
    redirect_uri=gmail_settings.CALLBACK_URL,
    scope='https://mail.google.com/',
    approval_prompt='force',
)


class SetupEmailAuthView(View):
    """
    View to setup the OAuth2 authentication chain.

    View needs an authenticated user.

    This view will redirect to Google and asks for permission to view and edit
    a GMail account from the user. If successful, Google will redirect to
    given ``settings.CALLBACK_URL``, which should be the url to OAuth2CallbackView.
    """

    @classmethod
    def as_view(cls, *args, **kwargs):
        return login_required(super(SetupEmailAuthView, cls).as_view(*args, **kwargs))

    def get(self, request):
        """
        Get request will redirect to google accounts with a created token and redirect_url.

        :param instance request: Request object

        :return: HttpResponseRedirect to Google Accounts

        """
        state = generate_token(settings.SECRET_KEY, request.user.pk)
        if request.user.pk % 2 == 0:
            FLOW.params['state'] = state
            authorize_url = FLOW.step1_get_authorize_url()
        else:
            FLOW.params['state'] = state
            authorize_url = FLOW.step1_get_authorize_url()

        return HttpResponseRedirect(authorize_url)


class OAuth2CallbackView(View):
    """
    View to finish OAuth2 authentication.

    View needs an authenticated user.

    View will be redirected to by Google. Google will give the correct state and a code.
    Based on the given code, credentials will be fetched from Google. After fetching the
    credentials, an EmailAccount will be created and credentials will be attached to the
    Account.

    Redirects to ``gmail_settings.REDIRECT_URL``.
    """

    @classmethod
    def as_view(cls, *args, **kwargs):
        return login_required(super(OAuth2CallbackView, cls).as_view(*args, **kwargs))

    def get(self, request):
        """
        Get request will check state and with the code it will get the credentials from Google.

        :param instance request: Request object

        :return: HttpResponseRedirect to ``settings.REDIRECT_URL``
        """
        if not self.validate_token(str(request.GET['state'])):
            return HttpResponseBadRequest()

        credentials = self.get_credentials(str(request.GET['code']))
        account = EmailAccount.create_account_from_credentials(credentials, request.user)

        if gmail_settings.REDIRECT_URL:
            return HttpResponseRedirect(gmail_settings.REDIRECT_URL)
        else:
            return HttpResponseRedirect(reverse('gmail_list', kwargs={'account_id': account.id}))

    def validate_token(self, state):
        """
        Check if returned token is still valid.

        :param str state: string to check.

        :return: boolean ``True`` if token is valid.
        """
        return validate_token(settings.SECRET_KEY, str(state), self.request.user.pk)

    def get_credentials(self, code):
        """
        Get credentials from Google with given code.

        :param str code: string to use.

        :return: credentials instance from Google.
        """
        if self.request.user.pk % 2 == 0:
            return FLOW.step2_exchange(code=code)
        else:
            return FLOW.step2_exchange(code=code)


class EmailMessageListView(ListView):
    """
    Display all emails belonging to account
    """
    model = EmailMessage
    template_name = 'gmailmanager/list.html'
    account = None

    def get_queryset(self):
        self.account = EmailAccount.objects.get(id=self.kwargs['account_id'])
        queryset = super(EmailMessageListView, self).get_queryset()
        return queryset.filter(
            account=self.account,
            is_deleted=False,
            is_downloaded=True,
        )

    def get_context_data(self, **kwargs):
        context = super(EmailMessageListView, self).get_context_data(**kwargs)
        context.update({
            'account': self.account,
            'label': 'ALL MAIL'
        })
        return context


class EmailMessageLabelListView(EmailMessageListView):
    """
    Display all emails belonging to a label of an account
    """
    def get_queryset(self):
        queryset = super(EmailMessageLabelListView, self).get_queryset()
        return queryset.filter(labels__id=self.kwargs['label_id'])

    def get_context_data(self, **kwargs):
        context = super(EmailMessageLabelListView, self).get_context_data(**kwargs)
        context.update({
            'label': self.kwargs['label_id'],
        })
        return context


class EmailMessageView(DetailView):
    """
    Display an email body in an isolated html.
    """
    model = EmailMessage
    template_name = 'gmailmanager/emailmessage.html'

    def get_context_data(self, **kwargs):
        context = super(EmailMessageView, self).get_context_data(**kwargs)

        context['body_html'] = render_email_body(self.object.body_html, self.object.attachments.all(), self.request)

        context['attachments'] = self.object.attachments.filter(inline=False)

        return context

    def render_to_response(self, context, **response_kwargs):
        if not self.object.read:
            toggle_read_email_message.delay(self.object.id, not self.object.read)

        return super(EmailMessageView, self).render_to_response(context, **response_kwargs)


class EmailAttachmentProxy(View):
    """
    Get the EmailAttachment from storage and serve to user.
    """
    def get(self, request, *args, **kwargs):
        try:
            attachment = EmailAttachment.objects.get(
                pk=self.kwargs['attachment_id'],
                message_id=self.kwargs['message_id'])
        except:
            logger.error('unable to find attachment: emailmessage: %d, attachment: %d' % (
                self.kwargs['message_id'],
                self.kwargs['attachment_id']
            ))
            raise Http404()

        s3_file = default_storage._open(attachment.attachment.name)

        wrapper = FileWrapper(s3_file)
        if hasattr(s3_file, 'key'):
            content_type = s3_file.key.content_type
        else:
            content_type = mimetypes.guess_type(s3_file.file.name)[0]

        response = HttpResponse(wrapper, content_type=content_type)

        inline = 'attachment'
        if attachment.inline:
            inline = 'inline'

        response['Content-Disposition'] = '%s; filename=%s' % (inline, get_attachment_filename_from_url(s3_file.name))
        response['Content-Length'] = attachment.size
        return response


class EmailMessageArchiveView(DetailView):
    """
    Archive an EmailMessage and redirect back to previous view
    """
    model = EmailMessage

    def render_to_response(self, context, **response_kwargs):
        archive_email_message.delay(self.object.id)

        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class EmailMessageTrashView(DetailView):
    """
    Trash an EmailMessage and redirect back to previous view
    """
    model = EmailMessage

    def render_to_response(self, context, **response_kwargs):
        trash_email_message.delay(self.object.id)

        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class EmailMessageDeleteView(DetailView):
    """
    Trash an EmailMessage and redirect back to previous view
    """
    model = EmailMessage

    def render_to_response(self, context, **response_kwargs):
        delete_email_message.delay(self.object.id)

        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class EmailMessageComposeView(FormView):
    template_name = 'gmailmanager/compose.html'
    form_class = ComposeEmailForm
    success_url = 'gmailmanager/account/1/INBOX/'

    def create_outbox_message(self, email_draft):
        email_account = email_draft['send_from']
        soup = BeautifulSoup(email_draft['body'], 'lxml', from_encoding='utf-8')
        mapped_attachments = soup.findAll('img', {'cid': lambda cid: cid})

        email_outbox_message = EmailOutboxMessage.objects.create(
            subject=email_draft['subject'],
            send_from=email_account,
            to=anyjson.dumps(email_draft['to'] if len(email_draft['to']) else None),
            cc=anyjson.dumps(email_draft['cc'] if len(email_draft['cc']) else None),
            bcc=anyjson.dumps(email_draft['bcc'] if len(email_draft['bcc']) else None),
            body=email_draft['body'],
            headers=anyjson.dumps(self.get_email_headers()),
            mapped_attachments=len(mapped_attachments),
            original_message_id=self.kwargs.get('message_id')
        )

        return email_outbox_message

    def form_valid(self, form):
        email_outbox_message = self.create_outbox_message(form.cleaned_data)
        send_message.delay(email_outbox_message.id)

        return HttpResponseRedirect(reverse('gmail_label_list', kwargs={
            'account_id': email_outbox_message.send_from.id,
            'label_id': '1',
        }))

    def get_form_kwargs(self):
        kwargs = super(EmailMessageComposeView, self).get_form_kwargs()
        kwargs['user'] = self.request.user

        return kwargs

    def get_success_url(self):
        success_url = self.request.POST.get('success_url', None)
        # Success url can be empty on send, so double check
        if success_url:
            self.success_url = success_url

        return '/' + self.success_url

    def get_email_headers(self):
        return {}
