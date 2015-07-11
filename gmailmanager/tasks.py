import logging

from celery.task import task

from .manager import Manager
from .models import EmailAccount, EmailMessage, EmailOutboxMessage

logger = logging.getLogger(__name__)


######################################################################################################################
# SCHEDULED/SYNC TASKS                                                                                               #
######################################################################################################################


@task(ignore_result=True)
def synchronize_email_account_scheduler():
    """
    Start new tasks for every active mailbox to start synchronizing.
    """
    for email_account in EmailAccount.objects.filter(is_authorized=True, is_deleted=False):
        synchronize_email_account.delay(email_account.id)


@task(bind=True, ignore_result=True)
def synchronize_email_account(self, email_account_id):
    """
    Start new tasks for every active mailbox to start synchronizing.
    """
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_authorized=True, is_deleted=False)
    except EmailAccount.DoesNotExist:
        pass
    else:
        try:
            m = Manager(email_account)
            m.synchronize()
        except Exception as exc:
            logger.exception('Sync account failed: %s' % email_account)
            self.retry(exc=exc)


@task(bind=True, ignore_result=True)
def sync_all_messages_for_email_account(self, email_account_id):
    """
    Start new tasks for every active mailbox to start synchronizing.
    """
    logger.debug('no labels')
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_authorized=True, is_deleted=False)
    except EmailAccount.DoesNotExist:
        pass
    else:
        try:
            m = Manager(email_account)
            m.sync_all_messages()
        except Exception as exc:
            logger.exception('Sync account failed: %s' % email_account)
            self.retry(exc=exc)


@task(bind=True, ignore_result=True)
def sync_labels_for_all_messages_for_email_account(self, email_account_id):
    """
    Start new tasks for every active mailbox to start synchronizing.
    """
    logger.debug('with labels')
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_authorized=True, is_deleted=False)
    except EmailAccount.DoesNotExist:
        pass
    else:
        try:
            m = Manager(email_account)
            m.sync_all_labels_for_all_messages()
        except Exception as exc:
            logger.exception('Sync account failed: %s' % email_account)
            self.retry(exc=exc)


@task(bind=True, default_retry_delay=30)
def finish_sync_all_messages(self, results, email_account_id):
    """
    """
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_deleted=False)
    except EmailAccount.DoesNotExist:
        return True

    try:
        manager = Manager(email_account)
        manager.sync_all_messages()
    except Exception as exc:
        logger.exception('Finish sync all messages failed: %s' % email_account)
        raise self.retry(exc=exc)

    return True


@task(bind=True, default_retry_delay=30)
def sync_message(self, email_account_id, message_id):
    """

    :param int email_account_id: EmailAccount id
    :param str message_id: messageId used by Google

    :return: True if task successfull
    """
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_deleted=False)
    except EmailAccount.DoesNotExist:
        return True

    try:
        manager = Manager(email_account)
        manager.sync_message(message_id)
    except Exception as exc:
        logger.exception('Sync message failed: %s %s' % (email_account, message_id))
        raise self.retry(exc=exc)

    return True


@task(bind=True, default_retry_delay=30, ignore_result=True)
def sync_history_item(self, email_account_id, history_item):
    """
    """
    try:
        email_account = EmailAccount.objects.get(id=email_account_id, is_deleted=False)
    except EmailAccount.DoesNotExist:
        return True

    try:
        manager = Manager(email_account)
        manager.sync_history_item(history_item)
    except Exception as exc:
        logger.exception('Sync history_item failed: %s %s' % (email_account, history_item))
        raise self.retry(exc=exc)

    return True


######################################################################################################################
# ASYNC/USER ACTIVATED TASKS                                                                                         #
######################################################################################################################


@task(bind=True, default_retry_delay=30, ignore_result=True)
def toggle_read_email_message(self, email_id, read=True):
    """
    Mark message as read or unread.

    Args:
        email_id (int): id of the EmailMessage
        read (boolean, optional): if True, message will be marked as read
    """
    try:
        email_message = EmailMessage.objects.get(pk=email_id)
        email_message.read = read
        email_message.save()
    except EmailMessage.DoesNotExist:
        logger.warning('EmailMessage no longer exists: %s', email_id)
    else:
        manager = Manager(email_message.account)
        try:
            logger.debug('Toggle read: %s', email_message)
            manager.toggle_read_email_message(email_message, read=read)
        except Exception as exc:
            logger.exception('Toggle read emailmessage failed: %s %s' % (email_message.account, email_message.id))
            raise self.retry(exc=exc)


@task(bind=True, default_retry_delay=30, ignore_result=True)
def archive_email_message(self, email_id):
    """
    Archive message.

    Args:
        email_id (int): id of the EmailMessage
    """
    try:
        email_message = EmailMessage.objects.get(pk=email_id)
    except EmailMessage.DoesNotExist:
        logger.warning('EmailMessage no longer exists: %s', email_id)
    else:
        manager = Manager(email_message.account)
        try:
            logger.debug('Archiving: %s', email_message)
            manager.archive_email_message(email_message)
        except Exception as exc:
            logger.exception('Archiving emailmessage failed: %s %s' % (email_message.account, email_message.id))
            raise self.retry(exc=exc)


@task(bind=True, default_retry_delay=30, ignore_result=True)
def trash_email_message(self, email_id):
    """
    Trash message.

    Args:
        email_id (int): id of the EmailMessage
    """
    try:
        email_message = EmailMessage.objects.get(pk=email_id)
    except EmailMessage.DoesNotExist:
        logger.warning('EmailMessage no longer exists: %s', email_id)
    else:
        manager = Manager(email_message.account)
        try:
            logger.debug('Trashing: %s', email_message)
            manager.trash_email_message(email_message)
        except Exception as exc:
            logger.exception('Trashing emailmessage failed: %s %s' % (email_message.account, email_message.id))
            raise self.retry(exc=exc)


@task(bind=True, default_retry_delay=30, ignore_result=True)
def delete_email_message(self, email_id):
    """
    Trash message.

    Args:
        email_id (int): id of the EmailMessage
    """
    try:
        email_message = EmailMessage.objects.get(pk=email_id)
    except EmailMessage.DoesNotExist:
        logger.warning('EmailMessage no longer exists: %s', email_id)
    else:
        manager = Manager(email_message.account)
        try:
            logger.debug('Deleting: %s', email_message)
            manager.delete_email_message(email_message)
        except Exception as exc:
            logger.exception('Deleting emailmessage failed: %s %s' % (email_message.account, email_message.id))
            raise self.retry(exc=exc)


@task(bind=True, default_retry_delay=30, ignore_result=True)
def send_message(self, email_outbox_message_id):
    """
    Send EmailOutboxMessage.

    Args:
        email_outbox_message_id (int): id of the EmailOutboxMessage
    """
    email_outbox_message = EmailOutboxMessage.objects.get(pk=email_outbox_message_id)

    email_account = email_outbox_message.send_from

    if not email_account.is_authorized:
        logger.error('EmailAccount not authorized: %s, message %s not sent' % (email_account, email_outbox_message))
    else:
        manager = Manager(email_account)
        try:
            manager.send_email_message(email_outbox_message)
            logger.debug('Message sent from: %s', email_account)
            # Seems like everything went right, so the EmailOutboxMessage object isn't needed any more
            email_outbox_message.delete()
        except Exception as exc:
            logger.exception(
                'Sending emailmessage failed: %s %s' % (email_account, email_outbox_message.id)
            )
            raise self.retry(exc=exc)
