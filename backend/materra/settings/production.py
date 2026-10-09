from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = False

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        'SECRET_KEY environment variable is required with production settings.'
    )
