# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
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
            name='EmailAccount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('deleted', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='deleted', editable=False, blank=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('email_address', models.EmailField(max_length=254)),
                ('from_name', models.CharField(default=b'', max_length=254)),
                ('label', models.CharField(default=b'', max_length=254)),
                ('is_authorized', models.BooleanField(default=False)),
                ('history_id', models.BigIntegerField(null=True)),
                ('temp_history_id', models.BigIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GmailCredentialsModel',
            fields=[
                ('id', models.OneToOneField(primary_key=True, serialize=False, to='gmail_manager.EmailAccount')),
                ('credentials', oauth2client.django_orm.CredentialsField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='emailaccount',
            name='owner',
            field=models.ForeignKey(related_name='email_accounts_owned', to=settings.AUTH_USER_MODEL),
        ),
    ]
