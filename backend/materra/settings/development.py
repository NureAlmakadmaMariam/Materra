from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ['*']

# Local-only fallback so the dev server runs without a .env file.
SECRET_KEY = SECRET_KEY or 'django-insecure-local-development-only'  # noqa: F405

# Enable the browsable API UI in development.
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [  # noqa: F405
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]
