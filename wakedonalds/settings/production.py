"""
Production / cloud settings, intended for AWS Elastic Beanstalk.
Every value here is read from environment variables (set via EB
environment properties / AWS Systems Manager Parameter Store) —
nothing sensitive is committed to GitHub.

NOTE: This environment currently runs as a free-tier "Single instance"
EB environment with no load balancer, so there is no HTTPS listener.
SECURE_SSL_REDIRECT / SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE are
gated behind USE_HTTPS (default False) to match that. Once a load
balancer + ACM certificate are added (future sprint), set
USE_HTTPS=True in EB environment properties to re-enable them.
"""

from .base import *  # noqa
from decouple import config, Csv

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default=''),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {'ssl': {'ssl_mode': 'REQUIRED'}},
    }
}

# This environment has no HTTPS listener yet (free-tier single-instance
# EB, no load balancer/ACM cert). These default to False so the app is
# actually usable over plain HTTP right now. Flip USE_HTTPS=True in EB
# env vars once HTTPS is added.
USE_HTTPS = config('USE_HTTPS', default=False, cast=bool)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS

CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = True