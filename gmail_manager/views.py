from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.views.generic import View
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.xsrfutil import generate_token, validate_token

from .models import EmailAccount
from .settings import gmail_settings

FLOW = OAuth2WebServerFlow(
    client_id=gmail_settings.CLIENT_ID,
    client_secret=gmail_settings.CLIENT_SECRET,
    redirect_uri=gmail_settings.CALLBACK_URL,
    scope='https://mail.google.com/',
    approval_prompt='force',
)


class LoginRequiredMixin(object):
    """
    Use this mixin if you want that the view is only accessed when a user is logged in.

    This should be the first mixin as a superclass.
    """

    @classmethod
    def as_view(cls, *args, **kwargs):
        return login_required(super(LoginRequiredMixin, cls).as_view(*args, **kwargs))


class SetupEmailAuth(LoginRequiredMixin, View):
    def get(self, request):
        state = generate_token(settings.SECRET_KEY, request.user.pk)
        FLOW.params['state'] = state
        authorize_url = FLOW.step1_get_authorize_url()

        return HttpResponseRedirect(authorize_url)


class OAuth2Callback(LoginRequiredMixin, View):
    def get(self, request):
        if not validate_token(settings.SECRET_KEY, str(request.GET['state']), request.user.pk):
            return HttpResponseBadRequest()

        credentials = FLOW.step2_exchange(code=str(request.GET['code']))
        account = EmailAccount.create_account_from_credentials(credentials, request.user)

        return HttpResponseRedirect('/#/preferences/emailaccounts/edit/%s' % account.pk)
