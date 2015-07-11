import logging
from django.core.management import BaseCommand

from ...models import EmailAccount
from ...tasks import sync_all_messages_for_email_account, sync_labels_for_all_messages_for_email_account

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    SyncAccount syncs email account given the email address.

    Args:
        email: email address from account
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            help='Email address of the account that needs to be synced',
        )

        parser.add_argument(
            '--full',
            action='store_true',
            dest='full',
            default=False,
            help='Sync all the labels for all messages',
        )

    def handle(self, *args, **options):
        email_account = EmailAccount.objects.get(email_address=options['email'])
        if options['full']:
            sync_all_messages_for_email_account.delay(email_account.id)
            self.stdout.write('Full sync for: %s' % email_account)
        else:
            sync_labels_for_all_messages_for_email_account.delay(email_account.id)
            self.stdout.write('Search for not downloaded messages: %s' % email_account)

