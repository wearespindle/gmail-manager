from django.test import TestCase
from googleapiclient.http import HttpMock
from mock import patch

from .connector import Connector, ConnectorError
from .credentials import InvalidCredentialsError
from .factories import EmailAccountFactory


class ConnectorTestCase(TestCase):

    def setUp(self):
        self.email_account = EmailAccountFactory.build()

    def test_connector_cannot_init_without_EmailAccount(self):
        with self.assertRaises(TypeError):
            Connector()

    @patch('gmailmanager.connector.get_credentials')
    @patch('gmailmanager.connector.build')
    def test_connector_can_init_with_EmailAccount(self, build_mock, credentials_mock):
        connector = Connector(self.email_account)

        self.assertIsInstance(connector, Connector)

    @patch('gmailmanager.connector.get_credentials')
    @patch('gmailmanager.connector.build')
    def test_connector_will_get_credentials(self, build_mock, credentials_mock):
        Connector(self.email_account)

        credentials_mock.assert_called_once_with(self.email_account)

    @patch('gmailmanager.connector.get_credentials')
    def test_connector_will_raise_error_on_invalid_credentials(self, credentials_mock):
        credentials_mock.side_effect = InvalidCredentialsError

        with self.assertRaises(ConnectorError):
            Connector(self.email_account)
