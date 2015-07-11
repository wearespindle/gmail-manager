from django.core.management import BaseCommand

from ...manager import Manager
from ...models import EmailAccount


class Command(BaseCommand):
    help = """
    GetMail Fetches email message from gmail api.

    Sets a pdb after fetching info.

    Args:
        email: email address where emailmessage is stored in
        id: id of the message
    """

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('id')

    def handle(self, email_address, message_id, **kwargs):
        email_account = EmailAccount.objects.get(email_address=email_address)

        manager = Manager(email_account)
        message_info = manager.get_connector().get_message_info(message_id)
        import pdb
        pdb.set_trace()
