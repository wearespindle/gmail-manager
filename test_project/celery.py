from __future__ import absolute_import
import os

from celery import Celery
from django.conf import settings

# set the default Django settings module

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')

app = Celery('gmailmanager', broker='amqp://guest@blaat:5672')
app.config_from_object(settings)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
