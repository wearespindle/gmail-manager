import logging

from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import ModificationDateTimeField
from django_extensions.db.models import TimeStampedModel
from oauth2client.django_orm import CredentialsField, Storage
from gmailmanager.fields import HashField

from .settings import gmail_settings


logger = logging.getLogger(__name__)


class DeletedMixin(TimeStampedModel):
    """
    Deleted model, flags when an instance is deleted.
    """
    deleted = ModificationDateTimeField(_('deleted'))
    is_deleted = models.BooleanField(default=False, db_index=True)

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
    complete_download = models.BooleanField(default=False)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='email_accounts_owned')

    @classmethod
    def create_account_from_credentials(cls, credentials, user):
        from .utils import build_gmail_service

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


class EmailLabel(models.Model):
    """
    Label for EmailAccount and EmailMessage
    """
    LABEL_SYSTEM, LABEL_USER = range(2)
    LABEL_TYPES = (
        (LABEL_SYSTEM, _('System')),
        (LABEL_USER, _('User')),
    )

    account = models.ForeignKey(EmailAccount, related_name='labels')
    label_type = models.IntegerField(choices=LABEL_TYPES, default=LABEL_SYSTEM)
    label_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    unread = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        return self.name

    class Meta:
        unique_together = ('account', 'label_id')


class Recipient(models.Model):
    """
    Name and email address of a recipient
    """
    name = models.CharField(max_length=1000, null=True)
    email_address = models.CharField(max_length=1000, null=True, db_index=True)

    def __unicode__(self):
        return u'%s <%s>' % (self.name, self.email_address)

    class Meta:
        unique_together = ('name', 'email_address')


class EmailMessage(DeletedMixin, models.Model):
    """
    EmailMessage has all information from an email message
    """
    account = models.ForeignKey(EmailAccount, related_name='messages')
    body_html = models.TextField(default='')
    body_text = models.TextField(default='')
    draft_id = models.CharField(max_length=50, db_index=True, default='')
    has_attachment = models.BooleanField(default=False)
    is_downloaded = models.BooleanField(default=False, db_index=True)
    labels = models.ManyToManyField(EmailLabel, related_name='messages')
    message_id = models.CharField(max_length=50, db_index=True)
    read = models.BooleanField(default=False, db_index=True)
    received_by = models.ManyToManyField(Recipient, related_name='received_messages')
    received_by_cc = models.ManyToManyField(Recipient, related_name='received_messages_as_cc')
    sender = models.ForeignKey(Recipient, related_name='sent_messages', null=True)
    sent_date = models.DateTimeField(db_index=True)
    snippet = models.TextField(default='')
    subject = models.TextField(default='')
    thread_id = models.CharField(max_length=50, db_index=True)

    def __unicode__(self):
        return u'%s: %s' % (self.sender, self.snippet)

    class Meta:
        unique_together = ('account', 'message_id')
        ordering = ['-sent_date']


class EmailOutboxMessage(models.Model):
    bcc = models.TextField(null=True, blank=True, verbose_name=_('bcc'))
    body = models.TextField(null=True, blank=True, verbose_name=_('html body'))
    cc = models.TextField(null=True, blank=True, verbose_name=_('cc'))
    headers = models.TextField(null=True, blank=True, verbose_name=_('email headers'))
    mapped_attachments = models.IntegerField(verbose_name=_('number of mapped attachments'))
    original_attachment_ids = models.CommaSeparatedIntegerField(max_length=255, default='')
    original_message_id = models.CharField(null=True, blank=True, max_length=50, db_index=True)
    send_from = models.ForeignKey(EmailAccount, verbose_name=_('from'), related_name='outbox_messages')
    subject = models.CharField(null=True, blank=True, max_length=255, verbose_name=_('subject'))
    template_attachment_ids = models.CommaSeparatedIntegerField(max_length=255, default='')
    to = models.TextField(verbose_name=_('to'))

    def message(self):
        from .body_parser import create_email_from_emailmessage
        return create_email_from_emailmessage(self)

    def as_string(self):
        return self.message().as_string()


class EmailHeader(models.Model):
    """
    Headers for an EmailMessage
    """
    message = models.ForeignKey(EmailMessage, related_name='headers')
    name = models.CharField(max_length=100)
    value = models.TextField()
    value_hash = HashField(original='value')

    def __unicode__(self):
        return u'%s: %s' % (self.name, self.value)

    class Meta:
        unique_together = ('message', 'name', 'value_hash')


def get_attachment_upload_path(instance, filename):
    return gmail_settings.EMAIL_ATTACHMENT_UPLOAD_TO % {
        'message_id': instance.message_id,
        'filename': filename
    }


class EmailAttachment(models.Model):
    """
    Email attachment for an EmailMessage
    """
    attachment = models.FileField(upload_to=get_attachment_upload_path, max_length=255)
    cid = models.TextField(default='')
    inline = models.BooleanField(default=False)
    message = models.ForeignKey(EmailMessage, related_name='attachments')
    size = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        return self.attachment.name.split('/')[-1]

    @property
    def name(self):
        return self.attachment.name.split('/')[-1]

    @property
    def url(self):
        return reverse('gmail_attachment', kwargs={
            'message_id': self.message.id,
            'attachment_id': self.id,
            'file_name': self.name,
        })


def get_outbox_attachment_upload_path(instance, filename):
    return gmail_settings.EMAIL_ATTACHMENT_UPLOAD_TO % {
        'message_id': instance.email_outbox_message_id,
        'filename': filename
    }


class EmailOutboxAttachment(models.Model):
    """
    Attachment for EmailOutboxMessage
    """
    attachment = models.FileField(upload_to=get_outbox_attachment_upload_path, max_length=255)
    content_type = models.CharField(max_length=255, verbose_name=_('content type'))
    email_outbox_message = models.ForeignKey(EmailOutboxMessage, related_name='attachments')
    inline = models.BooleanField(default=False)
    size = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        return self.attachment.name


class EmailTemplate(TimeStampedModel):
    """
    Emails can be composed using templates.

    A template is a predefined email in which parameters can be dynamically inserted.
    """
    body_html = models.TextField(verbose_name=_('html part'), blank=True)
    default_for = models.ManyToManyField(EmailAccount, through='DefaultEmailTemplate')
    name = models.CharField(verbose_name=_('template name'), max_length=255)
    subject = models.CharField(verbose_name=_('message subject'), max_length=255, blank=True)

    def __unicode__(self):
        return self.name


class DefaultEmailTemplate(models.Model):
    """
    Define a default template for a user.
    """
    account = models.ForeignKey(EmailAccount, related_name='default_templates')
    template = models.ForeignKey(EmailTemplate, related_name='default_templates')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='default_templates')

    def __unicode__(self):
        return u'%s - %s' % (self.account, self.template)


class TemplateVariable(models.Model):
    """
    Template variables can be used to insert default text into EmailTemplates
    """
    NO_YES_CHOICES = (
        (False, _('No')),
        (True, _('Yes')),
    )

    is_public = models.BooleanField(
        default=False,
        choices=NO_YES_CHOICES,
        help_text='A public template variable is available to everyone in your organisation'
    )
    name = models.CharField(verbose_name=_('variable name'), max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='template_variable')
    text = models.TextField(verbose_name='variable text')


def get_template_attachment_upload_path(instance, filename):
    return settings.EMAIL_TEMPLATE_ATTACHMENT_UPLOAD_TO % {
        'template_id': instance.template_id,
        'filename': filename
    }


class EmailTemplateAttachment(models.Model):
    """
    Default attachments that are added to templates.
    """
    attachment = models.FileField(
        verbose_name=_('template attachment'),
        upload_to=get_template_attachment_upload_path,
        max_length=255
    )
    content_type = models.CharField(max_length=255, verbose_name=_('content type'))
    size = models.PositiveIntegerField(default=0)
    template = models.ForeignKey(EmailTemplate, verbose_name=_(''), related_name='attachments')

    def save(self):
        if isinstance(self.attachment.file, (TemporaryUploadedFile, InMemoryUploadedFile)):
            # FieldFile object doesn't have the content_type attribute, so only set it if we're uploading new files
            self.content_type = self.attachment.file.content_type
            self.size = self.attachment.file.size

        super(EmailTemplateAttachment, self).save()

    def __unicode__(self):
        return u'%s: %s' % (_('attachment of'), self.template)


class EmailDraft(TimeStampedModel):
    body_html = models.TextField(null=True, blank=True, verbose_name=_('html body'))
    send_from = models.ForeignKey(EmailAccount, verbose_name=_('From'), related_name='drafts')
    send_to_bcc = models.TextField(null=True, blank=True, verbose_name=_('bcc'))
    send_to_cc = models.TextField(null=True, blank=True, verbose_name=_('cc'))
    send_to_normal = models.TextField(null=True, blank=True, verbose_name=_('to'))
    subject = models.CharField(null=True, blank=True, max_length=255, verbose_name=_('subject'))

    def __unicode__(self):
        return u'%s - %s' % (self.send_from, self.subject)


class GmailCredentialsModel(models.Model):
    """
    OAuth2 credentials for gmail api
    """
    id = models.OneToOneField(EmailAccount, primary_key=True)
    credentials = CredentialsField()
