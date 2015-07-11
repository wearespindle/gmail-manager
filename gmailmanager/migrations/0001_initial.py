# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import gmailmanager.models
import gmailmanager.fields
import oauth2client.django_orm
import django.utils.timezone
from django.conf import settings
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultEmailTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            name='EmailAccount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('deleted', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='deleted', editable=False, blank=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('email_address', models.EmailField(max_length=254)),
                ('from_name', models.CharField(default=b'', max_length=254)),
                ('label', models.CharField(default=b'', max_length=254)),
                ('is_authorized', models.BooleanField(default=False)),
                ('history_id', models.BigIntegerField(null=True)),
                ('complete_download', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='EmailAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment', models.FileField(max_length=255, upload_to=gmailmanager.models.get_attachment_upload_path)),
                ('cid', models.TextField(default=b'')),
                ('inline', models.BooleanField(default=False)),
                ('size', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='EmailDraft',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('body_html', models.TextField(null=True, verbose_name='html body', blank=True)),
                ('send_to_bcc', models.TextField(null=True, verbose_name='bcc', blank=True)),
                ('send_to_cc', models.TextField(null=True, verbose_name='cc', blank=True)),
                ('send_to_normal', models.TextField(null=True, verbose_name='to', blank=True)),
                ('subject', models.CharField(max_length=255, null=True, verbose_name='subject', blank=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='EmailHeader',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('value', models.TextField()),
                ('value_hash', gmailmanager.fields.HashField()),
            ],
        ),
        migrations.CreateModel(
            name='EmailLabel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('label_type', models.IntegerField(default=0, choices=[(0, 'System'), (1, 'User')])),
                ('label_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('unread', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='EmailMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('deleted', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='deleted', editable=False, blank=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('body_html', models.TextField(default=b'')),
                ('body_text', models.TextField(default=b'')),
                ('draft_id', models.CharField(default=b'', max_length=50, db_index=True)),
                ('has_attachment', models.BooleanField(default=False)),
                ('is_downloaded', models.BooleanField(default=False, db_index=True)),
                ('message_id', models.CharField(max_length=50, db_index=True)),
                ('read', models.BooleanField(default=False, db_index=True)),
                ('sent_date', models.DateTimeField(db_index=True)),
                ('snippet', models.TextField(default=b'')),
                ('subject', models.TextField(default=b'')),
                ('thread_id', models.CharField(max_length=50, db_index=True)),
            ],
            options={
                'ordering': ['-sent_date'],
            },
        ),
        migrations.CreateModel(
            name='EmailOutboxAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment', models.FileField(max_length=255, upload_to=gmailmanager.models.get_outbox_attachment_upload_path)),
                ('content_type', models.CharField(max_length=255, verbose_name='content type')),
                ('inline', models.BooleanField(default=False)),
                ('size', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='EmailOutboxMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bcc', models.TextField(null=True, verbose_name='bcc', blank=True)),
                ('body', models.TextField(null=True, verbose_name='html body', blank=True)),
                ('cc', models.TextField(null=True, verbose_name='cc', blank=True)),
                ('headers', models.TextField(null=True, verbose_name='email headers', blank=True)),
                ('mapped_attachments', models.IntegerField(verbose_name='number of mapped attachments')),
                ('original_attachment_ids', models.CommaSeparatedIntegerField(default=b'', max_length=255)),
                ('original_message_id', models.CharField(db_index=True, max_length=50, null=True, blank=True)),
                ('subject', models.CharField(max_length=255, null=True, verbose_name='subject', blank=True)),
                ('template_attachment_ids', models.CommaSeparatedIntegerField(default=b'', max_length=255)),
                ('to', models.TextField(verbose_name='to')),
            ],
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('body_html', models.TextField(verbose_name='html part', blank=True)),
                ('name', models.CharField(max_length=255, verbose_name='template name')),
                ('subject', models.CharField(max_length=255, verbose_name='message subject', blank=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='EmailTemplateAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment', models.FileField(upload_to=gmailmanager.models.get_template_attachment_upload_path, max_length=255, verbose_name='template attachment')),
                ('content_type', models.CharField(max_length=255, verbose_name='content type')),
                ('size', models.PositiveIntegerField(default=0)),
                ('template', models.ForeignKey(related_name='attachments', verbose_name='', to='gmailmanager.EmailTemplate')),
            ],
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=1000, null=True)),
                ('email_address', models.CharField(max_length=1000, null=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='TemplateVariable',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_public', models.BooleanField(default=False, help_text=b'A public template variable is available to everyone in your organisation', choices=[(False, 'No'), (True, 'Yes')])),
                ('name', models.CharField(max_length=255, verbose_name='variable name')),
                ('text', models.TextField(verbose_name=b'variable text')),
                ('owner', models.ForeignKey(related_name='template_variable', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='GmailCredentialsModel',
            fields=[
                ('id', models.OneToOneField(primary_key=True, serialize=False, to='gmailmanager.EmailAccount')),
                ('credentials', oauth2client.django_orm.CredentialsField(null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('name', 'email_address')]),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='default_for',
            field=models.ManyToManyField(to='gmailmanager.EmailAccount', through='gmailmanager.DefaultEmailTemplate'),
        ),
        migrations.AddField(
            model_name='emailoutboxmessage',
            name='send_from',
            field=models.ForeignKey(related_name='outbox_messages', verbose_name='from', to='gmailmanager.EmailAccount'),
        ),
        migrations.AddField(
            model_name='emailoutboxattachment',
            name='email_outbox_message',
            field=models.ForeignKey(related_name='attachments', to='gmailmanager.EmailOutboxMessage'),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='account',
            field=models.ForeignKey(related_name='messages', to='gmailmanager.EmailAccount'),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='labels',
            field=models.ManyToManyField(related_name='messages', to='gmailmanager.EmailLabel'),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='received_by',
            field=models.ManyToManyField(related_name='received_messages', to='gmailmanager.Recipient'),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='received_by_cc',
            field=models.ManyToManyField(related_name='received_messages_as_cc', to='gmailmanager.Recipient'),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='sender',
            field=models.ForeignKey(related_name='sent_messages', to='gmailmanager.Recipient', null=True),
        ),
        migrations.AddField(
            model_name='emaillabel',
            name='account',
            field=models.ForeignKey(related_name='labels', to='gmailmanager.EmailAccount'),
        ),
        migrations.AddField(
            model_name='emailheader',
            name='message',
            field=models.ForeignKey(related_name='headers', to='gmailmanager.EmailMessage'),
        ),
        migrations.AddField(
            model_name='emaildraft',
            name='send_from',
            field=models.ForeignKey(related_name='drafts', verbose_name='From', to='gmailmanager.EmailAccount'),
        ),
        migrations.AddField(
            model_name='emailattachment',
            name='message',
            field=models.ForeignKey(related_name='attachments', to='gmailmanager.EmailMessage'),
        ),
        migrations.AddField(
            model_name='emailaccount',
            name='owner',
            field=models.ForeignKey(related_name='email_accounts_owned', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='defaultemailtemplate',
            name='account',
            field=models.ForeignKey(related_name='default_templates', to='gmailmanager.EmailAccount'),
        ),
        migrations.AddField(
            model_name='defaultemailtemplate',
            name='template',
            field=models.ForeignKey(related_name='default_templates', to='gmailmanager.EmailTemplate'),
        ),
        migrations.AddField(
            model_name='defaultemailtemplate',
            name='user',
            field=models.ForeignKey(related_name='default_templates', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='emailmessage',
            unique_together=set([('account', 'message_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='emaillabel',
            unique_together=set([('account', 'label_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='emailheader',
            unique_together=set([('message', 'name', 'value_hash')]),
        ),
    ]
