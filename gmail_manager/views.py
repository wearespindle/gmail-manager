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

    Redirects to ``settings.REDIRECT_URL``.
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
        EmailAccount.create_account_from_credentials(credentials, request.user)

        return HttpResponseRedirect(gmail_settings.REDIRECT_URL)

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
        return FLOW.step2_exchange(code=code)
