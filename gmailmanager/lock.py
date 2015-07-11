import logging
from urlparse import urlparse

from redis import Redis

from .settings import gmail_settings


logger = logging.getLogger(__name__)


class EmailSyncLock(object):
    """
    Class to create locks that expire in redis with key as lock id.

    key: Name of the lock
    value: Extra information about the lock
    expires: Lifetime of task in seconds (default 300sec)
    prefix: Prefix for the key
    """

    DEFAULT_PREFIX = 'SYNC_'
    FIRST_SYNC_PREFIX = 'FIRST_SYNC_'

    def __init__(self, key, value=None, expires=gmail_settings.SYNC_LOCK_LIFETIME, prefix=DEFAULT_PREFIX):
        self.key = prefix + str(key)
        self.value = value
        self.expires = expires
        self.connection = self.get_connection()

    def get_connection(self):
        """
        Setup Redis connection

        Returns:
            redis instance with connection
        """
        redis_path = urlparse(gmail_settings.REDISTOGO_URL)
        return Redis(redis_path.hostname, port=redis_path.port, password=redis_path.password)

    def get(self):
        """
        Get value of current key

        Returns:
            current value of key
        """
        return self.connection.get(self.key)

    def acquire(self):
        """
        Create or update a lock for current key and update expire time of key
        """
        self.connection.set(self.key, self.value)
        self.connection.expire(self.key, self.expires)

    def release(self):
        """
        Remove lock for given key
        """
        self.connection.delete(self.key)

    def is_set(self):
        """
        Check if there is a value set for current key

        Returns:
            boolean True if lock is set
        """
        return bool(self.get())
