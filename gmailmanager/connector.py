import logging
import random
import time

import anyjson
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload
import httplib2

from .credentials import get_credentials, InvalidCredentialsError
from .settings import gmail_settings

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    pass


class FailedRequestException(ConnectorError):
    pass


class Connector(object):
    """
    Connector makes it possible to create connections with the GMail Api.

    Attributes:
        history_id (int): current history_id
        email_account (instance): current EmailAccount
        service (instance): service that is used to connect to GMail Api
    """
    history_id = None

    def __init__(self, email_account):
        self.email_account = email_account

        self.service = self.create_service()

    def create_service(self):
        """
        Create the service based on the credentials of the email_account.

        Returns:
            authorized service
        """
        try:
            credentials = get_credentials(self.email_account)
        except InvalidCredentialsError:
            logger.error('Invalid credentials for account: %s' % self.email_account)
            raise ConnectorError
        else:
            http = credentials.authorize(httplib2.Http())
            return build('gmail', 'v1', http=http)

    def execute_request(self, request):
        """
        Tries to execute a request.

        If the call fails because the rate limit is exceeded, sleep x seconds to try again.

        Args:
            request (instance): request instance
        Returns:
            response from request instance
        """
        for n in range(0, 6):
            try:
                return request.execute()
            except HttpError, e:
                try:
                    error = anyjson.loads(e.content)
                    # Error could be nested, so unwrap if necessary
                    error = error.get('error', error)
                except ValueError:
                    logger.exception('error %s' % e)
                    error = e
                if error.get('code') == 403 and error.get('errors')[0].get('reason') in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    # Apply exponential back off.
                    sleep_time = (2 ** n) + random.randint(0, 1000) / 1000.0
                    logger.warning('Limit overrated, sleeping for %s seconds' % sleep_time)
                    time.sleep(sleep_time)
                elif error.get('code') == 429:
                    # Apply exponential back off.
                    sleep_time = (2 ** n) + random.randint(0, 1000) / 1000.0
                    logger.warning('Too many concurrent requests for user, sleeping for %d seconds' % sleep_time)
                    time.sleep(sleep_time)
                elif error.get('code') == 503 or error.get('code') == 500:
                    # Apply exponential back off.
                    sleep_time = (2 ** n) + random.randint(0, 1000) / 1000.0
                    logger.warning('Backend error, sleeping for %d seconds' % sleep_time)
                    time.sleep(sleep_time)
                else:
                    logger.exception('Unknown error code for error %s' % error)
                    raise

        raise FailedRequestException('Request failed after all retries')

    def get_profile(self):
        """
        Fetch all info related to the profile of the current EmailAccount.

        Returns:
            dict with:
                - email address
                - number of messages
                - number of threads
                - current history_id
        """
        return self.execute_request(self.service.users().getProfile(userId='me'))

    def get_all_message_ids(self):
        """
        Fetch all messages from service.

        It all the messages.

        :return: list of messageIds & threadIds
        """
        message_dicts = []

        messages_request = self.service.users().messages()
        request = messages_request.list(userId='me', q='!in:chats')

        while request:
            response = self.execute_request(request)
            message_dicts.extend(response.get('messages', []))
            request = messages_request.list_next(request, response)

        return message_dicts

    def get_history(self):
        """
        Fetch the history list from the gmail api.

        Returns:
            list with messageIds and threadIds
        """
        history = []

        history_request = self.service.users().history()
        request = history_request.list(
            userId='me',
            startHistoryId=self.history_id,
        )

        while request:
            response = self.execute_request(request)
            history.extend(response.get('history', []))
            request = history_request.list_next(request, response)

        # Update the history id if it is bigger then the one already set
        if len(history) and self.history_id < history[-1]['id']:
            self.history_id = history[-1]['id']

        return history

    def get_message_info(self, message_id):
        """
        Fetch message information given message_id.

        Args:
            message_id (string): id of the message

        Returns:
            dict with message info
        """
        return self.execute_request(self.service.users().messages().get(userId='me', id=message_id))

    def get_label_info(self, label_id):
        """
        Fetch label info given label_id

        Args:
            label_id (string): id of the label

        Return dict with label info
        """
        return self.execute_request(self.service.users().labels().get(userId='me', id=label_id))

    def get_attachment(self, message_id, attachment_id):
        """
        Fetch attachment given message_id and attachment_id

        Args:
            message_id (string): id of the message
            attachment_id (string): id of the attachment

        Returns:
            dict with attachment info
        """
        return self.execute_request(
            self.service.users().messages().attachments().get(userId='me', messageId=message_id, id=attachment_id)
        )

    def get_minimal_message_info(self, message_id):
        """
        Fetch minimal message information given message_id.

        Args:
            message_id (string): id of the message

        Returns:
            dict with minimal message info
        """
        return self.execute_request(self.service.users().messages().get(userId='me', id=message_id, format='minimal'))

    def update_labels(self, message_id, labels):
        """
        Update remotely the labels of given message_id.

        Args:
            message_id (string): id of the message
            labels (list): of label_ids

        Returns:
            minimal message info of updated message
        """
        return self.execute_request(
            self.service.users().messages().modify(userId='me', id=message_id, body=labels)
        )

    def get_message_label_list(self, message_id):
        """
        Fetch labels for given message

        Args:
            message_id (string): id of the message

        Returns:
            list with labels given message_id
        """
        labels = self.execute_request(self.service.users().messages().get(
            userId='me',
            id=message_id,
            fields='labelIds'
        ))
        return labels.get('labelIds', [])

    def trash_email_message(self, message_id):
        """
        Move given message remotely to the trash

        Args:
            message_id (string): id of the message

        Returns:
            minimal message info of updated message
        """
        return self.execute_request(
            self.service.users().messages().trash(userId='me', id=message_id)
        )

    def delete_email_message(self, message_id):
        """
        Delete given message remotely

        Args:
            message_id (string): id of the message

        Returns:
            None
        """
        return self.execute_request(
            self.service.users().messages().delete(userId='me', id=message_id)
        )

    def send_email_message(self, message_string, thread_id=None):
        """
        Send given message and add optional thread_id

        Args:
            message_string (string): Python message instance as string
            thread_id (string): thread_id associated with message

        Returns:
            message instance that is sent.
        """
        message_dict = {}
        media = MediaInMemoryUpload(
            message_string,
            mimetype='message/rfc822',
            chunksize=gmail_settings.GMAIL_CHUNK_SIZE,
            resumable=True,
        )
        if thread_id:
            message_dict.update({'threadId': thread_id})
        return self.execute_request(
            self.service.users().messages().send(userId='me', body=message_dict, media_body=media)
        )
