from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import ModificationDateTimeField
from django_extensions.db.models import TimeStampedModel
from oauth2client.django_orm import CredentialsField, Storage

from .utils import build_gmail_service


class DeletedMixin(TimeStampedModel):
    """
    Deleted model, flags when an instance is deleted.
    """
    deleted = ModificationDateTimeField(_('deleted'))
    is_deleted = models.BooleanField(default=False)

    def delete(self, using=None, hard=False):
        """
        Soft delete instance by flagging is_deleted as False.

        Arguments:
            using (str): which db to use
            hard (boolean): If True, permanent removal from db
        """
        if hard:
            super(DeletedMixin, self).delete(using=using)
        else:
            self.is_deleted = True
            self.save()

    class Meta:
        get_latest_by = 'modified'
        ordering = ('-modified', '-created',)
        abstract = True


class EmailAccount(DeletedMixin, models.Model):
    """
    Email Account linked to a user
    """
    email_address = models.EmailField(max_length=254)
    from_name = models.CharField(max_length=254, default='')
    label = models.CharField(max_length=254, default='')
    is_authorized = models.BooleanField(default=False)

    # History id is a field to keep track of the sync status of a gmail box
    history_id = models.BigIntegerField(null=True)
    temp_history_id = models.BigIntegerField(null=True)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='email_accounts_owned')

    @classmethod
    def create_account_from_credentials(cls, credentials, user):
        # Setup service to retrieve email address
        service = build_gmail_service(credentials)
        response = service.users().getProfile(userId='me').execute()

        # Create account based on email address
        account = cls.objects.get_or_create(
            owner=user,
            email_address=response.get('emailAddress'),
            label=response.get('emailAddress'),
        )[0]

        # Store credentials based on new email account
        storage = Storage(GmailCredentialsModel, 'id', account, 'credentials')
        storage.put(credentials)

        # Set account as authorized
        account.is_authorized = True
        account.is_deleted = False
        account.save()
        return account

    def __unicode__(self):
        return u'%s  (%s)' % (self.label, self.email_address)


class GmailCredentialsModel(models.Model):
    """
    OAuth2 credentials for gmail api
    """
    id = models.OneToOneField(EmailAccount, primary_key=True)
    credentials = CredentialsField()
