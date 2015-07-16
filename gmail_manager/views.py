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


class SetupEmailAuth(View):

    @classmethod
    def as_view(cls, *args, **kwargs):
        return login_required(super(SetupEmailAuth, cls).as_view(*args, **kwargs))

    def get(self, request):
        state = generate_token(settings.SECRET_KEY, request.user.pk)
        FLOW.params['state'] = state
        authorize_url = FLOW.step1_get_authorize_url()

        return HttpResponseRedirect(authorize_url)


class OAuth2Callback(View):

    @classmethod
    def as_view(cls, *args, **kwargs):
        return login_required(super(OAuth2Callback, cls).as_view(*args, **kwargs))

    def get(self, request):
        if not self.validate_token(str(request.GET['state'])):
            return HttpResponseBadRequest()

        credentials = self.get_credentials(str(request.GET['code']))
        account = EmailAccount.create_account_from_credentials(credentials, request.user)

        return HttpResponseRedirect(gmail_settings.REDIRECT_URL)

    def validate_token(self, state):
        """
        Check if returned token is still valid.
        """
        return validate_token(settings.SECRET_KEY, str(state), self.request.user.pk)

    def get_credentials(self, code):
        """
        Get credentials with given code
        """
        return FLOW.step2_exchange(code=code)
