from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = """
    Create a user quickly
    """

    def handle(self, **kwargs):

        User.objects.create_user(email='test@test.nl', password='test', username='test')
        self.stdout.write('user created')
