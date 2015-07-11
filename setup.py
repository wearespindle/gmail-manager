from setuptools import setup

import gmailmanager

version = gmailmanager.version

packages = [
    'gmailmanager',
]

install_requires = [
    'beautifulsoup4',
    'bleach',
    'celery',
    'Django',
    'django-extensions',
    'eventlet',
    'flower',
    'google-api-python-client',
    'lxml',
    'oauth2client',
    'redis',
]


setup(
    name='gmail-manager',
    version='0.1',
    description='First implementation of GMail api as a complete sync',
    url='http://github.com/wearespindle/gmail-manager',
    author='Devhouse Spindle',
    author_email='bob.voorneveld@wearespindle.com',
    license='MIT',
    packages=packages,
    install_requires=install_requires,
    zip_safe=False
)
