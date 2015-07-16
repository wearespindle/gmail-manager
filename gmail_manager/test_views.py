from django.contrib.auth.models import User, AnonymousUser
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory
from mock import patch, MagicMock
from gmail_manager.settings import gmail_settings

from .views import SetupEmailAuth, OAuth2Callback


class SetupViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='jacob', email='jacob@_', password='top_secret')

    def test_setup_redirects_anon_user(self):
        request = self.factory.get(reverse('gmail_setup'))
        request.user = AnonymousUser()

        response = SetupEmailAuth.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_setup_accepts_logged_user(self):
        request = self.factory.get(reverse('gmail_setup'))
        request.user = self.user

        response = SetupEmailAuth.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google', response.url)


class CallbackViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='jacob', email='jacob@_', password='top_secret')

    def test_callback_redirects_anon_user(self):
        request = self.factory.get(reverse('gmail_callback'))
        request.user = AnonymousUser()

        response = OAuth2Callback.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_callback_accepts_logged_user(self):
        request = self.factory.get('%s?state=testing_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user
        response = OAuth2Callback.as_view()(request)

        self.assertNotEqual(response.status_code, 302)

    @patch.object(OAuth2Callback, 'validate_token', return_value=False)
    def test_callback_checks_token(self, mock_method):
        request = self.factory.get('%s?state=testing_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user
        OAuth2Callback.as_view()(request)

        mock_method.assert_called_once_with('testing_state')

    @patch.object(OAuth2Callback, 'validate_token', return_value=False)
    def test_callback_gives_bad_respone_with_wrong_token(self, mock_method):
        request = self.factory.get('%s?state=invalid_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user
        response = OAuth2Callback.as_view()(request)

        self.assertEqual(response.status_code, 400)

    @patch.object(OAuth2Callback, 'validate_token', return_value=True)
    def test_callback_correct_token_gets_credentials(self, mock_validation):
        request = self.factory.get('%s?state=valid_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user

        with patch.object(OAuth2Callback, 'get_credentials') as mock_method:
            with patch('gmail_manager.views.EmailAccount'):
                OAuth2Callback.as_view()(request)

                mock_method.assert_called_once_with('testing_code')

    @patch.object(OAuth2Callback, 'validate_token', return_value=True)
    def test_callback_correct_credentials_creates_account(self, mock_validation):
        request = self.factory.get('%s?state=valid_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user

        mock_credentials = MagicMock()
        with patch.object(OAuth2Callback, 'get_credentials', return_value=mock_credentials):
            with patch('gmail_manager.views.EmailAccount') as email_account:
                OAuth2Callback.as_view()(request)

                email_account.create_account_from_credentials.assert_called_once_with(mock_credentials, self.user)

    @patch.object(OAuth2Callback, 'validate_token', return_value=True)
    def test_callback_redirects_to_redirect_url(self, mock_validation):
        request = self.factory.get('%s?state=valid_state&code=testing_code' % reverse('gmail_callback'))
        request.user = self.user

        mock_credentials = MagicMock()
        with patch.object(OAuth2Callback, 'get_credentials', return_value=mock_credentials):
            with patch('gmail_manager.views.EmailAccount'):
                response = OAuth2Callback.as_view()(request)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, gmail_settings.REDIRECT_URL)

