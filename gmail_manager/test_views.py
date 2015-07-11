from django.contrib.auth.models import User, AnonymousUser
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory

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
        request = self.factory.get(reverse('gmail_callback'))
        request.user = self.user

        response = OAuth2Callback.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google', response.url)

