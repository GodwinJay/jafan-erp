import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from django.core.management.utils import get_random_secret_key

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
# Production: Reads from env. Local: Falls back to a generated key.
SECRET_KEY = os.getenv('SECRET_KEY', get_random_secret_key())

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.railway.app']

# TRUSTED ORIGINS FOR RAILWAY (Fixes CSRF 403 Errors)
CSRF_TRUSTED_ORIGINS = ['https://*.railway.app']

# Unfold Configuration
UNFOLD = {
    "SITE_TITLE": "Jafan ERP",
    "SITE_HEADER": "Jafan Standard Block Industry",
    "SITE_SYMBOL": "speed",
    "SHOW_HISTORY": True,
    "COLORS": {
        "primary": {
            "50": "250 250 250",
            "100": "244 244 245",
            "200": "228 228 231",
            "300": "212 212 216",
            "400": "161 161 170",
            "500": "113 113 122",
            "600": "82 82 91",
            "700": "63 63 70",
            "800": "39 39 42",
            "900": "24 24 27",
            "950": "9 9 11",
        },
    },
   'SIDEBAR': {
    'navigation': [
        {
            'title': 'Business Overview',
            'separator': True,
            'items': [
                {
                    'title': 'Executive Dashboard',
                    'icon': 'analytics',
                    'link': '/erp/dashboard/',
                },
                {
                    'title': 'Transport Dashboard',
                    'icon': 'local_shipping',
                    'link': '/erp/transport-dashboard/',
                },
            ],
        },
        {
            'title': 'Reports',
            'separator': True,
            'items': [
                {
                    'title': 'Profit & Loss',
                    'icon': 'trending_up',
                    'link': '/erp/pl-report/',
                },
                {
                    'title': 'Cash Flow Statement',
                    'icon': 'account_balance_wallet',
                    'link': '/erp/cash-flow/',
                },
                {
                    'title': 'Loan Report',
                    'icon': 'payments',
                    'link': '/erp/loans/report/',
                },
            ],
        },
    ],
    'show_all_applications': True,
    'show_search': True,
},
}

# Application definition
INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.humanize',  
    "erp",
    "auditlog",
    "import_export",
    "django_htmx",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Production: Use PostgreSQL (Railway)
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
        )
    }
else:
    # Local Development: Use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'erp.User'

# Auditlog
AUDITLOG_INCLUDE_ALL_MODELS = True