import logging
import os
from email import Encoders
from email.header import Header
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import mimetypes

import anyjson
from bs4 import BeautifulSoup
from django.core.files.storage import default_storage
from django.core.mail import SafeMIMEMultipart, SafeMIMEText
from django.core.urlresolvers import reverse
import html2text

from .models import EmailAttachment
from .sanitze import sanitize_html_email
from .utils import get_attachment_filename_from_url


logger = logging.getLogger(__name__)


def render_email_body(html, mapped_attachments, request):
    """
    Update all the target attributes in the <a> tag.
    After that replace the cid information in the html

    Args:
        html (string): HTML string of the email body to be sent.
        mapped_attachments (list): List of linked attachments to the email
        request (instance): The django request

    Returns:
        html body (string)
    """
    if html is None:
        return None

    email_body = replace_anchors_in_html(html)
    email_body = replace_cid_in_html(email_body, mapped_attachments, request)

    return email_body


def replace_anchors_in_html(html):
    """
    Make all anchors open outside the iframe
    """
    if html is None:
        return None

    soup = create_a_beautiful_soup_object(html)

    if not soup or soup.get_text == '':
        return html

    for anchor in soup.findAll('a'):
        anchor.attrs.update({
            'target': '_blank',
        })

    return soup.encode_contents()


def create_a_beautiful_soup_object(html):
    """
    Try to create a BeautifulSoup object that has not an empty body
    If so try a different HTML parser.

    Args:
        html (string): HTML string of the email body to be sent.

    Returns:
        soup (BeautifulSoup object or None)
    """
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml', from_encoding='utf-8')

    if soup.get_text() == '':
        soup = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')

        if soup.get_text() == '':
            soup = BeautifulSoup(html, 'html5lib', from_encoding='utf-8')

            if soup.get_text() == '':
                soup = BeautifulSoup(html, 'xml', from_encoding='utf-8')

                if soup.get_text == '':
                    soup = None

    return soup


def replace_cid_in_html(html, mapped_attachments, request):
    """
    Replace all the cid image information with a link to the image

    Args:
        html (string): HTML string of the email body to be sent.
        mapped_attachments (list): List of linked attachments to the email
        request (instance): The django request

    Returns:
        html body (string)
    """
    if html is None:
        return None

    soup = create_a_beautiful_soup_object(html)
    cid_done = []
    inline_images = []

    if soup and mapped_attachments:
        inline_images = soup.findAll('img', {'src': lambda src: src and src.startswith('cid:')})

    if (not soup or soup.get_text() == '') and not inline_images:
        html = sanitize_html_email(html)
        return html

    protocol = 'http'
    if request.is_secure():
        protocol = 'https'
    host = request.META['HTTP_HOST']

    for image in inline_images:
        image_cid = image.get('src')[4:]

        for attachment in mapped_attachments:
            if (attachment.cid[1:-1] == image_cid or attachment.cid == image_cid) and attachment.cid not in cid_done:
                proxy_url = reverse('gmail_attachment', kwargs={
                    'message_id': attachment.message_id,
                    'attachment_id': attachment.pk,
                    'file_name': attachment.name,
                })
                image['src'] = '%s://%s%s' % (protocol, host, proxy_url)
                image['cid'] = image_cid
                cid_done.append(attachment.cid)

    html = soup.encode_contents()
    html = sanitize_html_email(html)

    return html


def replace_cid_and_change_headers(html, pk):
    """
    Check in the html source if there is an image tag with the attribute cid. Loop through the attachemnts that are
    linked with the email. If there is a match replace the source of the image with the cid information.
    After read the image information form the disk and put the data in a dummy header.
    At least create a plain text version of the html email.

    Args:
        html (string): HTML string of the email body to be sent.
        mapped_attachments (list): List of linked attachments to the email
        request (instance): The django request

    Returns:
        body_html (string),
        body_text (string),
        dummy_headers (dict)
    """
    if html is None:
        return None

    dummy_headers = []
    inline_images = []
    soup = create_a_beautiful_soup_object(html)
    attachments = EmailAttachment.objects.filter(message_id=pk)

    if soup and attachments:
        inline_images = soup.findAll('img', {'cid': lambda cid: cid})

    if (not soup or soup.get_text() == '') and not inline_images:
        body_html = html
    else:
        cid_done = []

        for image in inline_images:
            image_cid = image['cid']

            for attachment in attachments:
                if (attachment.cid[1:-1] == image_cid or attachment.cid == image_cid) and attachment.cid not in cid_done:
                    image['src'] = "cid:%s" % image_cid

                    storage_file = default_storage._open(attachment.attachment.name)
                    filename = get_attachment_filename_from_url(attachment.attachment.name)

                    if hasattr(storage_file, 'key'):
                        content_type = storage_file.key.content_type
                    else:
                        content_type = mimetypes.guess_type(storage_file.file.name)[0]

                    storage_file.open()
                    content = storage_file.read()
                    storage_file.close()

                    response = {
                        'content-type': content_type,
                        'content-disposition': 'inline',
                        'content-filename': filename,
                        'content-id': attachment.cid,
                        'x-attachment-id': image_cid,
                        'content-transfer-encoding': 'base64',
                        'content': content
                    }

                    dummy_headers.append(response)
                    cid_done.append(attachment.cid)
                    del image['cid']

        body_html = soup.encode_contents()

    body_text_handler = html2text.HTML2Text()
    body_text_handler.ignore_links = True
    body_text_handler.body_width = 0
    body_text = body_text_handler.handle(html)

    return body_html, body_text, dummy_headers


def create_email_from_emailmessage(emailmessage):
    to = anyjson.loads(emailmessage.to)
    cc = anyjson.loads(emailmessage.cc)
    bcc = anyjson.loads(emailmessage.bcc)

    if emailmessage.send_from.from_name:
        # Add account name to From header if one is available
        from_email = '"%s" <%s>' % (
            Header(u'%s' % emailmessage.send_from.from_name, 'utf-8'),
            emailmessage.send_from.email_address
        )
    else:
        # Otherwise only add the email address
        from_email = emailmessage.send_from.email_address

    html, text, inline_headers = replace_cid_and_change_headers(emailmessage.body, emailmessage.original_message_id)

    email_message = SafeMIMEMultipart('related')
    email_message['Subject'] = emailmessage.subject
    email_message['From'] = from_email

    if to:
        email_message['To'] = ','.join(list(to))
    if cc:
        email_message['cc'] = ','.join(list(cc))
    if bcc:
        email_message['bcc'] = ','.join(list(bcc))

    email_message_alternative = SafeMIMEMultipart('alternative')
    email_message.attach(email_message_alternative)

    email_message_text = SafeMIMEText(text, 'plain', 'utf-8')
    email_message_alternative.attach(email_message_text)

    email_message_html = SafeMIMEText(html, 'html', 'utf-8')
    email_message_alternative.attach(email_message_html)

    for attachment in emailmessage.attachments.all():
        if attachment.inline:
            continue

        try:
            storage_file = default_storage._open(attachment.attachment.name)
        except IOError:
            logger.exception('Couldn\'t get attachment, not sending %s' % emailmessage.id)
            return False

        filename = get_attachment_filename_from_url(attachment.attachment.name)

        storage_file.open()
        content = storage_file.read()
        storage_file.close()

        content_type, encoding = mimetypes.guess_type(filename)
        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)

        if main_type == 'text':
            msg = MIMEText(content, _subtype=sub_type)
        elif main_type == 'image':
            msg = MIMEImage(content, _subtype=sub_type)
        elif main_type == 'audio':
            msg = MIMEAudio(content, _subtype=sub_type)
        else:
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(content)
            Encoders.encode_base64(msg)

        msg.add_header('Content-Disposition', 'attachment', filename=os.path.basename(filename))

        email_message.attach(msg)

    # Add the inline attachments to email message header
    for inline_header in inline_headers:
        main_type, sub_type = inline_header['content-type'].split('/', 1)
        if main_type == 'image':
            msg = MIMEImage(
                inline_header['content'],
                _subtype=sub_type,
                name=os.path.basename(inline_header['content-filename'])
            )
            msg.add_header(
                'Content-Disposition',
                inline_header['content-disposition'],
                filename=os.path.basename(inline_header['content-filename'])
            )
            msg.add_header('Content-ID', inline_header['content-id'])

            email_message.attach(msg)

    return email_message
