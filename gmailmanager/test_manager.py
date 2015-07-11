from django.test import TestCase
from mock import patch, MagicMock

from .factories import EmailAccountFactory
from gmailmanager.connector import ConnectorError
from .manager import Manager, ManagerError


class ManagerTestCase(TestCase):

    def test_manager_cannot_init_without_email_account_id(self):
        with self.assertRaises(TypeError):
            Manager()

    @patch('gmailmanager.manager.Connector', new=MagicMock())
    def test_manager_can_init_with_email_account_id(self):
        email_account = EmailAccountFactory.build()
        manager = Manager(email_account)

        self.assertIsInstance(manager, Manager)

    @patch('gmailmanager.manager.Connector')
    def test_manager_should_create_an_connector_instance(self, mock_connector):
        email_account = EmailAccountFactory.build()
        manager = Manager(email_account)

        mock_connector.assert_called_with(email_account)
        self.assertEqual(manager.connector, mock_connector())

    @patch('gmailmanager.manager.Connector')
    def test_manager_should_raise_error_if_connector_error(self, mock_connector):
        email_account = EmailAccountFactory.build()
        mock_connector.side_effect = ConnectorError

        with self.assertRaises(ManagerError):
            Manager(email_account)

    @patch('gmailmanager.manager.Connector', new=MagicMock())
    def test_manager_on_synchronize_should_sync_messages(self):
        email_account = EmailAccountFactory.build()
        email_account.history_id = None

        manager = Manager(email_account)

        with patch.object(manager, 'synchronize_messages') as sync_function:
            manager.synchronize()

            sync_function.assert_called_with()

    @patch('gmailmanager.manager.Connector', new=MagicMock())
    def test_manager_should_do_a_complete_sync_if_no_history(self):
        email_account = EmailAccountFactory.build()
        email_account.history_id = None

        manager = Manager(email_account)

        with patch.object(manager, 'sync_all_messages') as sync_function:
            manager.synchronize()

            sync_function.assert_called_with()

    @patch('gmailmanager.manager.Connector', new=MagicMock())
    def test_manager_should_do_a_partial_sync_if_history(self):
        email_account = EmailAccountFactory.build()
        email_account.history_id = 1

        manager = Manager(email_account)

        with patch.object(manager, 'sync_by_history') as sync_function:
            manager.synchronize()

            sync_function.assert_called_with()


class FullSyncTestCase(TestCase):

    def setUp(self):

        with patch('gmailmanager.manager.Connector') as MockConnector:
            self.connector = MockConnector()
            self.manager = Manager(EmailAccountFactory.build())

    def test_manager_should_fetch_all_message_ids(self):
        self.manager.synchronize()

        self.connector.get_all_message_ids.assert_called_with()

    def test_manager_should_create_task_for_every_message(self):
        self.connector.get_all_message_ids.return_value = [
            {
                "id": "14ea386ab36cbc16",
                "threadId": "14ea386ab36cbc16"
            },
            {
                "id": "14e9d9d63e70c1f9",
                "threadId": "14e9af9ba03c8190"
            },
        ]

        self.manager.synchronize()
