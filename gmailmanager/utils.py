import httplib2
import mimetypes
from urllib import unquote

from googleapiclient.discovery import build


def build_gmail_service(credentials):
    """
    Build a Gmail service object.

    Args:
      credentials (instance): OAuth 2.0 credentials.

    Returns:
      Gmail service object.
    """
    http = credentials.authorize(httplib2.Http())
    return build('gmail', 'v1', http=http)


def headers_to_dict(headers):
    """
    create dict from headers list

    Args:
        headers (list): of dicts with header info

    Returns:
        headers: dict with header_name : header_value
    """
    if headers:
        headers = {header['name']: header['value'] for header in headers}
    return headers


def get_extension_for_type(general_type):
    """
    For known mimetypes, use some extensions we know to be good or we prefer
    above others.. This solves some issues when the first of the available
    extensions doesn't make any sense, e.g.
    >>> get_extensions_for_type('txt')
    'asc'

    :param general_type:
    :return:
    """

    preferred_types_map = {
        'text/plain': '.txt',
        'text/html': '.html',
    }

    if general_type in preferred_types_map:
        return preferred_types_map[general_type]

    if not mimetypes.inited:
        mimetypes.init()

    for ext in mimetypes.types_map:
        if mimetypes.types_map[ext] == general_type or mimetypes.types_map[ext].split('/')[0] == general_type:
            return ext

    # return at least an extension for unknown mimetypes
    return '.bak'


def get_attachment_filename_from_url(url):
    return unquote(url).split('/')[-1]
