import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'False') == 'True'
LIVE = os.getenv('LIVE', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'material',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'registration',
    'crispy_forms',
    'tempus_dominus',
    'django_cron',
    'django_crontab',
    'mathfilters',
    'andinasoft',
    'buildingcontrol',
    'crm',
    'accounting',
    'finance',
    'api_auth',
    'mcp_server',
]

TEMPUS_DOMINUS_LOCALIZE = True
TEMPUS_DOMINUS_INCLUDE_ASSETS = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'andina.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'andina.wsgi.application'

# ─── Database ────────────────────────────────────────────────────────────────

DB_HOST     = os.getenv('DB_HOST')
DB_USER     = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT     = os.getenv('DB_PORT', '3306')

MYSQL_OPTIONS = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
}

# Alttum tiene sql_mode diferente al resto — respetamos el original
MYSQL_OPTIONS_ALTTUM = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
}

def make_db(name, options=None):
    return {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': name,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'OPTIONS': options or MYSQL_OPTIONS,
    }

if LIVE:
    DATABASES = {
        'default':            make_db(os.getenv('DB_NAME',         'developer_web')),
        'Sandville Beach':    make_db(os.getenv('DB_SANDVILLE',    'developer_sandville')),
        'Perla del Mar':      make_db(os.getenv('DB_PERLA',        'developer_sandvilledelmar')),
        'Sandville del Sol':  make_db(os.getenv('DB_SANDVILLESOL', 'developer_sandvilledelsol')),
        'Vegas de Venecia':   make_db(os.getenv('DB_VENECIA',      'developer_venecia')),
        'Tesoro Escondido':   make_db(os.getenv('DB_TESORO',       'developer_tesoro_escondido')),
        'Sotavento':          make_db(os.getenv('DB_SOTAVENTO',    'developer_sotavento')),
        'Carmelo Reservado':  make_db(os.getenv('DB_CARMELO',      'developer_carmeloreservado')),
        'Fractal':            make_db(os.getenv('DB_FRACTAL',      'developer_fractal')),
        'Alttum':             make_db(os.getenv('DB_ALTTUM',       'developer_alttum'), MYSQL_OPTIONS_ALTTUM),
        'Casas de Verano':    make_db(os.getenv('DB_CASASVERANO',  'developer_casasdeverano')),
    }
else:
    # Fractal, Alttum y Casas de Verano no existen en el entorno local
    DATABASES = {
        'default':            make_db(os.getenv('DB_NAME',         'andinaso_web')),
        'Sandville Beach':    make_db(os.getenv('DB_SANDVILLE',    'andinaso_sandville')),
        'Perla del Mar':      make_db(os.getenv('DB_PERLA',        'andinaso_sandvilledelmar')),
        'Sandville del Sol':  make_db(os.getenv('DB_SANDVILLESOL', 'andinaso_sandvilledelsol')),
        'Vegas de Venecia':   make_db(os.getenv('DB_VENECIA',      'andinaso_venecia')),
        'Tesoro Escondido':   make_db(os.getenv('DB_TESORO',       'andinaso_tesoro_escondido')),
        'Sotavento':          make_db(os.getenv('DB_SOTAVENTO',    'andinaso_sotavento')),
        'Carmelo Reservado':  make_db(os.getenv('DB_CARMELO',      'andinaso_carmeloreservado')),
    }

# ─── Auth ────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internacionalización ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# ─── Static & Media ───────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_files')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static_pro', 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'static_media')

# ─── Cron ────────────────────────────────────────────────────────────────────

CRON_CLASSES = [
    'andinasoft.cron_jobs.job_cartera',
]

CRONJOBS = [
    ('*/5 * * * *', 'andinasoft.cron_jobs.ejemplo_job'),
]

# ─── Email ───────────────────────────────────────────────────────────────────

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = os.getenv('EMAIL_HOST')
EMAIL_PORT          = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS       = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER     = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL  = os.getenv('DEFAULT_FROM_EMAIL')

# ─── Auth / Registration ──────────────────────────────────────────────────────

LOGIN_REDIRECT_URL = '/welcome'
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap4'
CRISPY_TEMPLATE_PACK = 'bootstrap4'
ACCOUNT_ACTIVATION_DAYS = 7
REGISTRATION_AUTO_LOGIN = True
SITE_ID = 1

# ─── Directorios ─────────────────────────────────────────────────────────────

if LIVE:
    DIR_DOCS      = MEDIA_ROOT + '/docs_andinasoft'
    DIR_EXPORT    = MEDIA_ROOT + '/tmp/'
    DIR_DOWNLOADS = 'https://app.somosandina.co/media/tmp/'
else:
    DIR_DOCS      = MEDIA_ROOT + '/'
    DIR_EXPORT    = MEDIA_ROOT + '/'
    DIR_DOWNLOADS = '/media/'

# ─── N8N Webhooks ─────────────────────────────────────────────────────────────

N8N_WEBHOOK_UPLOAD_MOVEMENTS = os.getenv('N8N_WEBHOOK_UPLOAD_MOVEMENTS', 'http://localhost:5678/webhook/upload-movements')
N8N_WEBHOOK_WOMPI_COUNT      = os.getenv('N8N_WEBHOOK_WOMPI_COUNT',      'http://localhost:5678/webhook/wompi-count')
N8N_WEBHOOK_PLINK_COUNT      = os.getenv('N8N_WEBHOOK_PLINK_COUNT',      'http://localhost:5678/webhook/plink-count')