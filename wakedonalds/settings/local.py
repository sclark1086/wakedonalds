"""
Local development settings.
Run with: DJANGO_SETTINGS_MODULE=wakedonalds.settings.local
(this is the default set in manage.py for now)
Uses SQLite so every teammate can run the project with zero setup —
no AWS credentials or MySQL instance needed for day-to-day feature work.
"""

from .base import *  # noqa
from decouple import config

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
