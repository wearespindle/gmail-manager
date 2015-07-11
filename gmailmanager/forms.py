from email.utils import parseaddr
import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _

from .models import EmailAccount, EmailAttachment, EmailOutboxMessage


class ComposeEmailForm(forms.ModelForm):
    """
    Form for writing an EmailMessage as a draft, reply or forwarded message.
    """
    send_from = forms.ChoiceField()
    to = forms.TextInput()
    cc = forms.TextInput()
    bcc = forms.TextInput()
    subject = forms.CharField(required=False)
    body = forms.TextInput()

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(ComposeEmailForm, self).__init__(*args, **kwargs)

        if 'initial' in kwargs and 'draft_pk' in kwargs['initial']:
            if self.message_type is not 'reply':
                self.initial['attachments'] = EmailAttachment.objects.filter(
                    message_id=kwargs['initial']['draft_pk'],
                    inline=False
                )

        self.email_accounts = EmailAccount.objects.filter(owner=user, is_deleted=False, is_authorized=True).distinct()

        # Only provide choices you have access to
        self.fields['send_from'].choices = [(email_account.id, email_account) for email_account in self.email_accounts]
        self.fields['send_from'].empty_label = None

    def is_multipart(self):
        """
        Return True since file uploads are possible.
        """
        return True

    def clean_to(self):
        return self.format_recipients(self.cleaned_data['to'])

    def clean_cc(self):
        return self.format_recipients(self.cleaned_data['cc'])

    def clean_bcc(self):
        return self.format_recipients(self.cleaned_data['bcc'])

    def clean(self):
        cleaned_data = super(ComposeEmailForm, self).clean()

        # Make sure at least one of the send_to_X fields is filled in when sending the email
        if not any([
            cleaned_data.get('to'),
            cleaned_data.get('cc'),
            cleaned_data.get('bcc'),
        ]):
            raise ValidationError(_('Please provide at least one recipient.'), code='invalid')

        return cleaned_data

    def format_recipients(self, recipients):
        """
        Strips newlines and trailing spaces & commas from recipients.
        Args:
            recipients (str): The string that needs cleaning up.
        Returns:
            String of comma separated email addresses.
        """
        formatted_recipients = []
        for recipient in recipients.split(','):
            # Clean each part of the string
            formatted_recipients.append(recipient.strip())

        # Create one string from the parts
        formatted_recipients = ', '.join(formatted_recipients)

        # Regex to split a string by comma while ignoring commas in between quotes
        pattern = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')

        # Split the single string into separate recipients
        formatted_recipients = pattern.split(formatted_recipients)[1::2]

        # It's possible that an extra space is added, so strip it
        cleaned_recipients = []
        for recipient in formatted_recipients:
            recipient = recipient.strip()
            email = parseaddr(recipient)[1]
            validate_email(email)
            cleaned_recipients.append(recipient)

        return cleaned_recipients

    def clean_send_from(self):
        """
        Verify send_from is a valid account the user has access to.
        """
        cleaned_data = self.cleaned_data
        send_from = cleaned_data.get('send_from')

        try:
            send_from = int(send_from)
        except ValueError:
            raise ValidationError(
                _('Invalid email account selected to use as sender.'),
                code='invalid',
            )
        try:
            send_from = self.email_accounts.get(pk=send_from)
        except EmailAccount.DoesNotExist:
            raise ValidationError(
                _('Invalid email account selected to use as sender.'),
                code='invalid',
            )

        return send_from

    class Meta:
        fields = (
            'send_from',
            'to',
            'cc',
            'bcc',
            'subject',
            'body',
        )
        model = EmailOutboxMessage

        widgets = {
            'to': forms.TextInput(),
            'cc': forms.TextInput(),
            'bcc': forms.TextInput(),
        }
