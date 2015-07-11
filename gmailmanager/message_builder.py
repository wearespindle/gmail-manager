import base64
from datetime import datetime
import email
import gc
import logging
import re
import StringIO

from bs4 import BeautifulSoup, UnicodeDammit
from django.core.files import File
from django.db import IntegrityError
import pytz

from .models import EmailMessage, EmailHeader, Recipient, EmailAttachment
from .settings import gmail_settings
from .utils import headers_to_dict, get_extension_for_type


logger = logging.getLogger(__name__)


class MessageBuilder(object):
    """
    Builder to get, create or update EmailMessages

    Attributes:
        manager (instance): manager that is controlling this builder
        message (instance): current EmailMessage
    """
    message = None

    def __init__(self, manager):
        self.manager = manager()

    def get_or_create_message(self, message_dict):
        """
        Get or create EmailMessage.

        Sets self.message with an EmailMessage instance

        Arguments:
            message_dict (dict): with message information

        Returns:
            created (boolean): True if message is created
        """
        sent_date = datetime.utcfromtimestamp(int(message_dict['internalDate'])/1000.0)
        sent_date = sent_date.replace(tzinfo=pytz.UTC)
        # Get or create message
        self.message, created = EmailMessage.objects.get_or_create(
            message_id=message_dict['id'],
            account=self.manager.email_account,
            sent_date=sent_date,
        )

        if 'threadId' in message_dict:
            self.message.thread_id = message_dict['threadId']

        return created

    def store_message_info(self, message_info):
        """
        With given dict, create or update current message

        Args:
            message_info (dict): with message info
        """
        self.get_or_create_message(message_info)

        if not self.message.is_downloaded:
            self.message.snippet = message_info['snippet']
            self._save_message_payload(message_info['payload'])
            self.message.is_downloaded = True

        # Always update labels
        self.store_labels_for_message(message_info)

        self.message.save()

        self.message = None
        gc.collect()

    def store_labels_for_message(self, message_info):
        """
        Handle the labels for current Message

        Args:
            message_info (dict): info for EmailMessage
        """
        # UNREAD identifier check to see if message is read
        self.message.read = gmail_settings.UNREAD_LABEL not in message_info.get('labelIds', [])

        # Store all labels
        self.message.labels.clear()
        for label in message_info.get('labelIds', []):
            # Do not save UNREAD_LABEL
            if label == gmail_settings.UNREAD_LABEL:
                continue

            db_label = self.manager.get_label(label)
            self.message.labels.add(db_label)

    def update_message(self, message_info):
        """
        Handle the labels for current Message

        Args:
            message_info (dict): info for EmailMessage
        """
        self.message = EmailMessage.objects.get(message_id=message_info['id'])
        self.message.thread_id = message_info['threadId']

        self.message.labels.clear()
        self.store_labels_for_message(message_info)

        self.message.save()
        self.message = None
        gc.collect()

    def _save_message_payload(self, payload):
        """
        Walk through message and save headers and parts

        Args:
            payload: dict with message payload
        """
        if 'headers' in payload:
            self._create_message_headers(payload['headers'])

        self.message.body_html = ''
        self.message.body_text = ''

        self._parse_message_part(payload)

    def _create_message_headers(self, headers):
        """
        Given header dict, create EmailHeaders for message.

        Args:
            headers (dict): of name, value headers
        """
        for header in headers:
            header_name = header['name']
            header_value = header['value']

            if header_name == 'Subject':
                self.message.subject = header_value
            elif header_name.lower() in ['to', 'from', 'cc', 'delivered-to']:
                self._create_recipients(header_name, header_value)
            else:
                EmailHeader.objects.get_or_create(
                    name=header['name'],
                    value=header['value'],
                    message=self.message,
                )

    def _parse_message_part(self, part):
        """
        Parse message part

        Args:
            part: dict with message part
        """
        # Check if part has child parts
        if 'parts' in part:
            for part in part['parts']:
                self._parse_message_part(part)
        else:
            part_headers = headers_to_dict(part.get('headers', {}))

            # Get content type
            mime_type = part['mimeType']

            # Check if part is an attachment
            if part['filename'] or 'data' not in part['body'] or mime_type == 'text/css':
                self._create_attachment(part, part_headers)

            else:
                # Decode body part
                body = base64.urlsafe_b64decode(part['body']['data'].encode())

                encoding = None
                if part_headers:
                    encoding = self._get_encoding_from_headers(part_headers)

                if mime_type == 'text/html':
                    self._create_body_html(body, encoding)

                elif mime_type == 'text/plain':
                    self._create_body_text(body, encoding)

                elif mime_type == 'text/xml':
                    # Conversation xml, do not store
                    pass

                elif mime_type == 'text/rfc822-headers':
                    # Header part, not needed
                    pass

                elif mime_type in (
                        'text/css',
                        'application/octet-stream',
                        'image/gif',
                        'image/jpg',
                        'image/x-png',
                        'image/png',
                        'image/jpeg',
                ):
                    # attachments
                    self._create_attachment(part, part_headers)
                else:
                    self._create_attachment(part, part_headers)
                    logger.warning('other mime_type %s for message %s, account %s' % (
                        mime_type,
                        self.message.message_id,
                        self.manager.email_account,
                    ))

    def _create_recipients(self, header_name, header_value):
        """
        Create recipient based on header

        Args:
            header_name (string): with name of header
            header_value (string): with value of header
        """
        header_name = header_name.lower()

        # Selects all comma's with the following conditions:
        # 1. Preceded by a TLD (with a max of 16 chars) or
        # 2. Preceded by an angle bracket (>)
        # Then swap out with regex group 1 + a semicolon (\1;)
        # After that split by semicolon (;)
        # Note: Basic tests have shown that char limit on the TLD can be increased without problems
        # 16 chars seems to be enough for now though
        recipients = re.sub(r'(\.[A-Z]{2,16}|>)(,)', r'\1;', header_value, flags=re.IGNORECASE).split('; ')

        for recipient in recipients:
            # Get or create recipient
            email_address = email.utils.parseaddr(recipient)
            recipient = Recipient.objects.get_or_create(
                name=email_address[0],
                email_address=email_address[1],
            )[0]

            # Set recipient to correct field
            if header_name == 'from':
                self.message.sender = recipient
            elif header_name in ['to', 'delivered-to']:
                try:
                    self.message.received_by.add(recipient)
                except IntegrityError:
                    pass
            elif header_name == 'cc':
                try:
                    self.message.received_by_cc.add(recipient)
                except IntegrityError:
                    pass

    def _create_attachment(self, part, headers):
        """
        Create an attachment for the given part

        Args:
            part (dict): with attachment info
            headers (dict): headers for message part

        Raises:
            Attachment exception if attachment couldn't be created
        """
        headers = {name.lower(): value for name, value in headers.iteritems()}

        # Check if attachment is inline
        inline = False
        if headers and headers.get('content-id', False):
            inline = True

        # Get file data from part or from remote
        if 'data' in part['body']:
            file_data = part['body']['data']
        elif 'attachmentId' in part['body']:
            file_data = self.manager.get_attachment(self.message.message_id, part['body']['attachmentId'])
            if file_data:
                file_data = file_data.get('data')
            else:
                logger.warning('No attachment could be downloaded, not storing anything')
                return
        else:
            logger.warning('No attachment, not storing anything')
            return

        file_data = base64.urlsafe_b64decode(file_data.encode('UTF-8'))

        # create as string file
        file = StringIO.StringIO(file_data)
        if headers and 'content-type' in headers:
            file.content_type = headers['content-type'].split(';')[0]
        else:
            file.content_type = 'application/octet-stream'

        file.size = len(file_data)
        file.name = part.get('filename', '').rsplit('\\')[-1].replace(':','')
        if len(file.name) > 200:
            file.name = None

        # No filename in part, create a name
        if not file.name:
            extension = get_extension_for_type(file.content_type)
            if part.get('partId'):
                file.name = 'attachment-%s%s' % (part.get('partId'), extension)
            else:
                logger.warning('No part id, no filename')
                file.name = 'attachment-%s-%s%s' % (self.message.id, self.message.attachments.count(), extension)

        file.name = file.name.encode('ascii', 'ignore')
        final_file = File(file, file.name)

        # Check if inline attachment
        cid = headers.get('content-id') if inline else ''

        # Create a EmailAttachment object
        EmailAttachment.objects.get_or_create(
            attachment=final_file,
            size=file.size,
            inline=inline,
            message=self.message,
            cid=cid,
        )

    def _get_encoding_from_headers(self, headers):
        """
        Try to find encoding from headers

        Args:
            headers (list): of headers

        Returns:
            encoding or None: string with encoding type
        """
        headers = {name.lower(): value for name, value in headers.iteritems()}
        if 'content-type' in headers:
            for header_part in headers.get('content-type').split(';'):
                if 'charset' in header_part.lower():
                    return header_part.split('=')[-1].lower().strip('"\'')

        return None

    def _create_body_text(self, body, encoding=None):
        """
        parse string to a correct coded text body part and add to Message.body_text

        Args:
            body (string): not encoded string
            encoding (string): possible encoding type
        """
        decoded_body = None

        # Use given encoding type
        if encoding:
            try:
                decoded_body = body.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                pass

        # UnicodeDammit decoding second
        if not decoded_body:
            dammit = UnicodeDammit(body)
            if dammit.original_encoding:
                encoding = dammit.original_encoding
                try:
                    decoded_body = body.decode(encoding)
                except (LookupError, UnicodeDecodeError):
                    pass

        # If decoding fails, just force utf-8
        if not decoded_body and body:
            logger.warning('couldn\'t decode, forced utf-8 > %s' % self.message.message_id)
            encoding = 'utf-8'
            decoded_body = body.decode(encoding, errors='replace')

        if decoded_body:
            self.message.body_text += decoded_body.encode(encoding).decode('utf-8')

    def _create_body_html(self, body, encoding=None):
        """
        parse string to a correct coded html body part and add to Message.body_html

        Args:
            body (string): not encoded string
            encoding (string): possible encoding type
        """
        decoded_body = None

        # Use given encoding type
        if encoding:
            try:
                decoded_body = body.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                pass

        # BS4 decoding second
        if not decoded_body:
            soup = BeautifulSoup(body, 'lxml')
            if soup.original_encoding:
                encoding = soup.original_encoding
                try:
                    decoded_body = body.decode(encoding)
                except (LookupError, UnicodeDecodeError):
                    pass

        # If decoding fails, just force utf-8
        if not decoded_body and body:
            logger.warning('couldn\'t decode, forced utf-8 > %s' % self.message.message_id)
            encoding = 'utf-8'
            decoded_body = body.decode(encoding, errors='replace')

        # Only add if there is a body
        if decoded_body:
            self.message.body_html += decoded_body.encode(encoding).decode('utf-8')
