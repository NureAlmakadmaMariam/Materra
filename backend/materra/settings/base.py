import os
from pathlib import Path

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(env_path: Path) -> None:
    """Load a .env file into os.environ without overwriting existing vars."""
    if not env_path.exists():
        return
    with open(env_path) as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(BASE_DIR.parent / '.env')

# ── Core ──────────────────────────────────────────────────────────────────────

# No fallback here: development.py supplies a local-only key and
# production.py refuses to start without one.
SECRET_KEY = os.environ.get('SECRET_KEY', '')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS: list[str] = os.environ.get(
    'ALLOWED_HOSTS', 'localhost,127.0.0.1'
).split(',')

# ── Applications ──────────────────────────────────────────────────────────────

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.analyses',
    'apps.ai',
    'apps.reports',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ── URL / WSGI ────────────────────────────────────────────────────────────────

ROOT_URLCONF = 'materra.urls'
WSGI_APPLICATION = 'materra.wsgi.application'

# ── Templates ────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ── Database ─────────────────────────────────────────────────────────────────

_db_engine = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
_db_name_raw = os.environ.get('DB_NAME', 'db.sqlite3')

# SQLite NAME must be a path; PostgreSQL NAME is a plain string.
_db_name: Path | str = (
    BASE_DIR / _db_name_raw
    if _db_engine == 'django.db.backends.sqlite3'
    else _db_name_raw
)

DATABASES: dict = {
    'default': {
        'ENGINE': _db_engine,
        'NAME': _db_name,
    }
}

if os.environ.get('DB_HOST'):
    DATABASES['default'].update(
        {
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'USER': os.environ.get('DB_USER', 'materra'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        }
    )

# Password validators are intentionally empty — validation is handled
# explicitly in form clean() methods (min_length, match check, current-pw check).
AUTH_PASSWORD_VALIDATORS: list = []

# ── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'uk'
TIME_ZONE = 'Europe/Kyiv'
USE_I18N = True
USE_TZ = True

# ── Static and media files ───────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Django REST Framework ────────────────────────────────────────────────────

REST_FRAMEWORK: dict = {
    # JWT auth (djangorestframework-simplejwt) replaces these in production.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# ── File upload constraints ───────────────────────────────────────────────────

MAX_UPLOAD_SIZE: int = int(os.environ.get('MAX_UPLOAD_SIZE', str(10 * 1024 * 1024)))
ALLOWED_IMAGE_TYPES: list[str] = ['image/jpeg', 'image/png', 'image/webp']

# ── AI / ML pipeline ─────────────────────────────────────────────────────────

MODEL_PATH: str = os.environ.get(
    'MODEL_PATH',
    str(BASE_DIR.parent / 'ml' / 'models' / 'materra_v1.onnx'),
)
MODEL_VERSION: str = os.environ.get('MODEL_VERSION', 'materra-v1.0')
AI_CONFIDENCE_THRESHOLD: float = float(
    os.environ.get('AI_CONFIDENCE_THRESHOLD', '0.60')
)
ANALYSIS_IMAGE_RETENTION_DAYS: int = int(
    os.environ.get('ANALYSIS_IMAGE_RETENTION_DAYS', '90')
)

# ── Misc ──────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Authentication ────────────────────────────────────────────────────────────

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'
