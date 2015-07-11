"""
Original code from Mimino666.

https://github.com/Mimino666/django-hash-field
"""

import hashlib

from django.db import models

_hash_it = lambda s: hashlib.sha1(s.encode('utf-8')).hexdigest()


class HashField(models.CharField):
    description = ('HashField is related to some other field in a model and'
                   'stores its hashed value for better indexing performance.')

    def __init__(self, original=None, *args, **kwargs):
        """
        :param original: name of the field storing the value to be hashed
        """
        self.original = original
        kwargs['max_length'] = 40
        super(HashField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(HashField, self).deconstruct()
        del kwargs['max_length']
        return name, path, args, kwargs

    def calculate_hash(self, model_instance):
        original_value = getattr(model_instance, self.original)
        setattr(model_instance, self.attname, _hash_it(original_value))

    def pre_save(self, model_instance, add):
        self.calculate_hash(model_instance)
        return super(HashField, self).pre_save(model_instance, add)
