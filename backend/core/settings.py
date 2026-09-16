import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Charger le fichier .env depuis la racine
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = 'django-insecure-jasmin-sms-gateway-key-demo-bgfi'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Applications installées
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Applications Métier
    'apps.accounts',
    'apps.jasmin_config',
    'apps.sms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
                'apps.jasmin_config.context_processors.jasmin_health',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Authentification & Redirections

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'sms:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Configuration Régionale
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Fichiers Statiques
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# CONFIGURATION PASSERELLE JASMIN SMS
# ==============================================================================
JASMIN_HOST = os.getenv('JASMIN_HOST', '192.168.1.70')
JASMIN_JCLI_PORT = int(os.getenv('JASMIN_JCLI_PORT', 8990))
JASMIN_USERNAME = os.getenv('JASMIN_USERNAME', 'jcliadmin')
JASMIN_PASSWORD = os.getenv('JASMIN_PASSWORD', 'jclipwd')
JASMIN_TIMEOUT = int(os.getenv('JASMIN_TIMEOUT', 30))
JASMIN_HTTP_PORT = int(os.getenv('JASMIN_HTTP_PORT', 1401))
JASMIN_AMQP_PORT = int(os.getenv('JASMIN_AMQP_PORT', 5672))