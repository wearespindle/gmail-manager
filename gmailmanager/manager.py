import logging
import weakref

import anyjson
from celery import chord, group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from googleapiclient.errors import HttpError

from .connector import Connector, ConnectorError
from .lock import EmailSyncLock
from .message_builder import MessageBuilder
from .models import EmailMessage, EmailLabel, EmailTemplateAttachment, EmailOutboxAttachment, EmailAttachment
from .settings import gmail_settings


logger = logging.getLogger(__name__)


class ManagerError(Exception):
    pass


class Manager(object):
    connector = None
    message_builder = None

    def __init__(self, email_account):
        """
        Args:
            email_account (instance): EmailAccount instance

        Raises:
            ManagerError: if sync is not possible
        """
        self.email_account = email_account

    def get_connector(self):
        if not self.connector:
            try:
                self.connector = Connector(self.email_account)
            except ConnectorError:
                raise ManagerError
        return self.connector

    def get_message_builder(self):
        if not self.message_builder:
            self.message_builder = MessageBuilder(weakref.ref(self))
        return self.message_builder

    def synchronize(self):
        """
        Synchronize complete email account.
        """
        self.synchronize_messages()

    def synchronize_messages(self):
        """
        Synchronize the email account

        If complete_download is set to True, update by history, otherwise a complete sync.
        """
        logger.debug('Syncing account: %s' % self.email_account)

        if self.email_account.complete_download:
            logger.debug('Syncing by history: %s' % self.email_account)
            self.sync_by_history()
        else:
            logger.debug('Full sync: %s' % self.email_account)
            if not self.email_account.history_id:
                self.email_account.history_id = self.get_connector().get_profile()['historyId']
                self.email_account.save()

            lock = EmailSyncLock(self.email_account.id, prefix=EmailSyncLock.FIRST_SYNC_PREFIX)
            if not lock.is_set():
                lock.acquire()
                self.sync_all_messages()
            else:
                logger.debug('Full Sync already in progress: %s' % self.email_account)

    def sync_all_messages(self):
        """
        Syncing all messages.

        For every message, a new task is created to download the message
        """
        from .tasks import sync_message, finish_sync_all_messages

        logger.debug('Syncing all messages for:%s' % self.email_account)

        message_ids = self.get_connector().get_all_message_ids()
        message_ids_downloaded = set(
            EmailMessage.objects.filter(
                account=self.email_account,
                is_downloaded=True,
            ).values_list(
                'message_id',
                flat=True,
            )
        )

        tasks = []
        for message in message_ids:
            if message['id'] not in message_ids_downloaded:
                tasks.append(sync_message.subtask((self.email_account.id, message['id']), queue='first_sync_messages'))

        # As a callback, call the same function (through a task, to check every email is synced)
        callback = finish_sync_all_messages.s(self.email_account.id)
        if tasks:
            chord(tasks)(callback)
        else:
            # When every email is fetched, there are no tasks to be done, so finish the sync
            self.email_account.complete_download = True
            self.email_account.save()
            logger.debug('Finishing sync all messages for: %s' % self.email_account)
            lock = EmailSyncLock(self.email_account.id, prefix=EmailSyncLock.FIRST_SYNC_PREFIX)
            lock.release()

    def sync_all_labels_for_all_messages(self):
        """
        Syncing all messages and update the labels of all the messages

        All messages, also the one already downloaded, are synced again
        """
        from .tasks import sync_message

        logger.debug('Syncing all labels for all messages for: %s' % self.email_account)

        message_ids = self.get_connector().get_all_message_ids()

        tasks = []
        for message in message_ids:
            tasks.append(sync_message.s(self.email_account.id, message['id']))

        if tasks:
            group(tasks)()

    def sync_message(self, message_id):
        """
        Sync message given message_id

        Args:
            message_id (string): message_id of the message
        """
        message = EmailMessage.objects.filter(message_id=message_id, is_downloaded=True)

        if not message.exists() or not message.first().is_downloaded:
            logger.debug('New message for %s, download: %s' % (self.email_account, message_id))
            message_info = self.get_connector().get_message_info(message_id)
            self.get_message_builder().store_message_info(message_info)
        else:
            logger.debug('Update message for %s, fetch labels: %s' % (self.email_account, message_id))
            message_info = self.get_connector().get_minimal_message_info(message_id)
            self.get_message_builder().update_message(message_info)

    def sync_by_history(self):
        """
        Fetch the updates from the connector and create a task for every history item
        """
        from .tasks import sync_history_item
        logger.warning('Syncing history for: %s' % self.email_account)
        self.get_connector().history_id = self.email_account.history_id

        history = self.get_connector().get_history()

        if history:
            group([sync_history_item.s(self.email_account.id, history_item) for history_item in history])()
            self.email_account.history_id = self.get_connector().history_id
            self.email_account.save()

    def sync_history_item(self, history_item):
        """
        Given the history_item, update the messages involved.

        Args:
            history_item (dict): updates that need to be parsed
        """
        from .tasks import sync_message

        logger.debug('Parsing history item for: %s' % self.email_account)

        # Get new messages
        for message_dict in history_item.get('messagesAdded', []):
            sync_message.delay(self.email_account.id, message_dict['message']['id'])

        # Remove messages
        for message_dict in history_item.get('messagesDeleted', []):
            logger.debug('Message %s deleted for account: %s' % (message_dict['message']['id'], self.email_account))
            EmailMessage.objects.filter(message_id=message_dict['message']['id'], account=self.email_account).delete()

        # Add labels to existing messages
        for message_dict in history_item.get('labelsAdded', []):
            self.add_labels_to_message(message_dict)

        # Remove labels from existing messages
        for message_dict in history_item.get('labelsRemoved', []):
            self.remove_labels_from_message(message_dict)

    def add_labels_to_message(self, message_dict):
        """
        Given the message_dict, add the message labels & update read status

        Args:
            message_dict (dict): with label info
        """
        from .tasks import sync_message

        logger.debug('Labels added for %s, message: %s' % (self.email_account, message_dict['message']['id']))

        try:
            message = EmailMessage.objects.get(
                message_id=message_dict['message']['id'],
                account=self.email_account
            )
        except EmailMessage.DoesNotExist:
            # EmailMessage should be there, let's download
            sync_message.delay(self.email_account.id, message_dict['message']['id'])
        else:
            for added_label_id in message_dict['labelIds']:
                # UNREAD_LABEL is only used to flag message read or unread
                if added_label_id == gmail_settings.UNREAD_LABEL:
                    message.read = False
                    message.save()
                else:
                    message.labels.add(self.get_label(added_label_id))

    def remove_labels_from_message(self, message_dict):
        """
        Given the message_dict, remove the message labels & update read status

        Args:
            message_dict (dict): with label info
        """
        from .tasks import sync_message

        logger.debug('Labels removed for %s, message: %s' % (self.email_account, message_dict['message']['id']))
        try:
            message = EmailMessage.objects.get(message_id=message_dict['message']['id'], account=self.email_account)
        except EmailMessage.DoesNotExist:
            # EmailMessage should be there, let's download
            sync_message.delay(self.email_account.id, message_dict['message']['id'])
        else:
            for removed_label_id in message_dict['labelIds']:
                if removed_label_id == gmail_settings.UNREAD_LABEL:
                    message.read = True
                    message.save()
                else:
                    message.labels.remove(self.get_label(removed_label_id))

    def get_label(self, label_id):
        """
        Returns the label given the label_id

        Args:
            label_id (string): label_id of the label

        Returns:
            EmailLabel instance
        """
        try:
            label = EmailLabel.objects.get(account=self.email_account, label_id=label_id)
        except EmailLabel.DoesNotExist:
            label_info = self.get_connector().get_label_info(label_id)

            label_type = EmailLabel.LABEL_SYSTEM if label_info['type'] == 'system' else EmailLabel.LABEL_USER

            # Async issue that adds a label right after the get call which
            # makes the create fail due to unique constraint
            label, created = EmailLabel.objects.get_or_create(
                account=self.email_account,
                label_id=label_info['id'],
                label_type=label_type,
            )
            # Name could have changed, always set the name
            label.name = label_info['name']
            label.save()

        return label

    def get_attachment(self, message_id, attachment_id):
        """
        Returns the attachment given the message_id and attachment_id

        Args:
            message_id (string): message_id of the message
            attachment_id (string): attachment_id of the message

        Returns:
            dict with attachment info
        """
        return self.get_connector().get_attachment(message_id, attachment_id)

    def update_unread_count(self):
        """
        Update unread count on every label.
        """
        logger.debug('Updating unread count for every label, account %s' % self.email_account)
        for label in self.email_account.labels.all():
            unread_count = label.messages.filter(read=False).count()
            label.unread = unread_count
            label.save()

    def toggle_read_email_message(self, email_message, read=True):
        """
        Mark message as read or unread.

        Args:
            email_message(instance): EmailMessage instance
            read (bool, optional): If True, mark message as read
        """
        if read:
            self.add_and_remove_labels_for_message(email_message, remove_labels=[gmail_settings.UNREAD_LABEL])
        else:
            self.add_and_remove_labels_for_message(email_message, add_labels=[gmail_settings.UNREAD_LABEL])

    def add_and_remove_labels_for_message(self, email_message, add_labels=None, remove_labels=None):
        """
        Add and/or removes labels for the EmailMessage.

        Args:
            email_message (instance): EmailMessage instance
            add_labels (list, optional): list of label_ids to add
            remove_labels (list, optional): list of label_ids to remove
        """
        labels = {}
        if remove_labels:
            labels['removeLabelIds'] = []
            for label_id in remove_labels:
                labels['removeLabelIds'].append(label_id)

        if add_labels:
            labels['addLabelIds'] = []
            for label_id in add_labels:
                # Only add existing labels or unread label
                if label_id == gmail_settings.UNREAD_LABEL or email_message.account.labels.filter(label_id=label_id).exists():
                    labels.setdefault('addLabelIds', []).append(label_id)

        # First update labels on server side
        try:
            self.get_connector().update_labels(email_message.message_id, labels)
        except HttpError, e:
            error = anyjson.loads(e.content)
            error = error.get('error', error)
            if error.get('code') != 400:
                # No label error, raise
                raise
        else:
            # When successful, edit the labels from model
            if remove_labels:
                for label_id in remove_labels:
                    if label_id == gmail_settings.UNREAD_LABEL:
                        email_message.read = True
                        email_message.save()
                    else:
                        label = self.get_label(label_id)
                        email_message.labels.remove(label)
            if add_labels:
                for label_id in add_labels:
                    if label_id == gmail_settings.UNREAD_LABEL:
                        email_message.read = False
                        email_message.save()
                    else:
                        label = self.get_label(label_id)
                        email_message.labels.add(label)

        self.update_unread_count()

    def archive_email_message(self, email_message):
        """
        Archive message by removing all labels except for possible UNREAD label

        Args:
            email_message(instance): EmailMessage instance
        """
        existing_labels = self.get_connector().get_message_label_list(email_message.message_id)

        if existing_labels:
            self.add_and_remove_labels_for_message(email_message, remove_labels=existing_labels)

    def trash_email_message(self, email_message):
        """
        Trash current EmailMessage.

        Args:
            email_message (instance): EmailMessage instance
        """
        minimal_message_info = self.get_connector().trash_email_message(email_message.message_id)

        # Store updated message
        self.get_message_builder().update_message(minimal_message_info)
        self.update_unread_count()

    def delete_email_message(self, email_message):
        """
        Trash current EmailMessage.

        Args:
            email_message (instance): EmailMessage instance
        """
        self.get_connector().delete_email_message(email_message.message_id)
        email_message.delete()
        self.update_unread_count()

    def send_email_message(self, message):
        """
        Send EmailOutboxMessage

        Args:
            email_outbox_message (instance): EmailOutboxMessage instance
        """
        from .tasks import sync_message

        # Add template attachments
        if message.template_attachment_ids:
            template_attachment_id_list = message.template_attachment_ids.split(',')
            for template_attachment_id in template_attachment_id_list:
                try:
                    template_attachment = EmailTemplateAttachment.objects.get(pk=template_attachment_id)
                except EmailTemplateAttachment.DoesNotExist:
                    pass
                else:
                    attachment = EmailOutboxAttachment()
                    attachment.content_type = template_attachment.content_type
                    attachment.size = template_attachment.size
                    attachment.email_outbox_message = message
                    attachment.attachment = template_attachment.attachment
                    attachment.save()

        #  Add attachment from original message (if mail is being forwarded)
        if message.original_attachment_ids:
            original_attachment_id_list = message.original_attachment_ids.split(',')
            for attachment_id in original_attachment_id_list:
                try:
                    original_attachment = EmailAttachment.objects.get(pk=attachment_id)
                except EmailAttachment.DoesNotExist:
                    pass
                else:
                    outbox_attachment = EmailOutboxAttachment()
                    outbox_attachment.email_outbox_message = message
                    outbox_attachment.tenant_id = original_attachment.message.tenant_id

                    file = default_storage._open(original_attachment.attachment.name)
                    file.open()
                    content = file.read()
                    file.close()

                    file = ContentFile(content)
                    file.name = original_attachment.attachment.name

                    outbox_attachment.attachment = file
                    outbox_attachment.inline = original_attachment.inline
                    outbox_attachment.size = file.size
                    outbox_attachment.save()

        thread_id = None
        if message.original_message_id:
            original_message = EmailMessage.objects.get(pk=message.original_message_id)
            if original_message.account.id is self.email_account.id:
                thread_id = original_message.thread_id

        # Send message
        message_dict = self.get_connector().send_email_message(message.as_string(), thread_id)

        logger.debug('Sent message \'%s\'for %s' % (message.subject, self.email_account))

        # Store the sent message
        sync_message.delay(self.email_account.id, message_dict['id'])
