from datetime import timedelta

from kombu import Queue

BROKER_URL = 'amqp://guest@rabbit:5672'
CELERY_RESULT_BACKEND = 'redis://redis:6379'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_ACKS_LATE = True

CELERY_QUEUES = (
    Queue('account_scheduler', routing_key='account_scheduler'),
    Queue('history', routing_key='history'),
    Queue('sync_message', routing_key='sync_message'),
    Queue('first_sync_messages', routing_key='first_sync_messages'),
    Queue('sync_account', routing_key='sync_account'),
    Queue('edit_labels', routing_key='edit_labels'),
    Queue('trash_message', routing_key='trash_message'),
    Queue('delete_message', routing_key='delete_message'),
    Queue('send_message', routing_key='send_message'),
)

CELERY_ROUTES = (
    {'gmailmanager.tasks.synchronize_email_account_scheduler': {
        'queue': 'account_scheduler',
    }},
    {'gmailmanager.tasks.sync_history_item': {
        'queue': 'history',
    }},
    {'gmailmanager.tasks.sync_message': {
        'queue': 'sync_message',
    }},
    {'gmailmanager.tasks.synchronize_email_account': {
        'queue': 'sync_account',
    }},
    {'gmailmanager.tasks.sync_all_messages_for_email_account': {
        'queue': 'sync_account',
    }},
    {'gmailmanager.tasks.sync_labels_for_all_messages_for_email_account': {
        'queue': 'sync_account',
    }},
    {'gmailmanager.tasks.toggle_read_email_message': {
        'queue': 'edit_labels',
    }},
    {'gmailmanager.tasks.delete_email_message': {
        'queue': 'delete_message',
    }},
    {'gmailmanager.tasks.trash_email_message': {
        'queue': 'trash_message',
    }},
    {'gmailmanager.tasks.send_message': {
        'queue': 'send_message',
    }},
)

CELERYBEAT_SCHEDULE = {
    'synchronize_email_account_scheduler': {
        'task': 'gmailmanager.tasks.synchronize_email_account_scheduler',
        'schedule': timedelta(seconds=20),
    },
}
