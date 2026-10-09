"""
Usage:
    python manage.py create_dev_superuser

Creates a superuser for local development without opening an interactive
prompt.  Credentials come from the DJANGO_SUPERUSER_EMAIL and
DJANGO_SUPERUSER_PASSWORD environment variables (e.g. set in .env).  Does
nothing when DEBUG is off or no password is set.  Safe to run multiple times —
skips creation if the email already exists.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

_DEFAULT_EMAIL = 'admin@materra.dev'


class Command(BaseCommand):
    help = 'Create a development superuser from environment variables (non-interactive).'

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            self.stdout.write(
                self.style.WARNING('DEBUG is off — dev superuser not created.')
            )
            return

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL') or _DEFAULT_EMAIL
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not password:
            self.stdout.write(
                self.style.WARNING(
                    'DJANGO_SUPERUSER_PASSWORD is not set — dev superuser not created.'
                )
            )
            return

        User = get_user_model()

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{email}" already exists — skipped.')
            )
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(
            self.style.SUCCESS(
                f'Dev superuser created.\n'
                f'  URL:   http://127.0.0.1:8000/materra-admin/\n'
                f'  Email: {email}'
            )
        )
