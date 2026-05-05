import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Webhooks Alegra: usuario para `history_facturas` (opcional; si vacío se usa el primer usuario activo).
ALEGRA_WEBHOOK_HISTORY_USERNAME = os.getenv('ALEGRA_WEBHOOK_HISTORY_USERNAME', '').strip()
_ALEGRA_WH_UID = os.getenv('ALEGRA_WEBHOOK_HISTORY_USER_ID', '').strip()
ALEGRA_WEBHOOK_HISTORY_USER_ID = int(_ALEGRA_WH_UID) if _ALEGRA_WH_UID.isdigit() else None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = env_bool('DEBUG', False)
LIVE = env_bool('LIVE', False)
USE_S3_MEDIA = env_bool('USE_S3_MEDIA', False)
MAINTENANCE_MODE = env_bool('MAINTENANCE_MODE', False)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000,https://app.somosandina.co,https://andinasoft.somosandina.co'
)

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
    'storages',
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
    'alegra_integration',
]

TEMPUS_DOMINUS_LOCALIZE = True
TEMPUS_DOMINUS_INCLUDE_ASSETS = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
    'init_command': "SET NAMES utf8mb4 COLLATE utf8mb4_general_ci, sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'",
    'connect_timeout': 5,
    'read_timeout': 30,
    'write_timeout': 30,
}

# Alttum tiene sql_mode diferente al resto — respetamos el original
MYSQL_OPTIONS_ALTTUM = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    'connect_timeout': 5,
    'read_timeout': 30,
    'write_timeout': 30,
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
    'Oasis':              make_db(os.getenv('DB_OASIS',        'developer_oasis')),
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

if DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    STATICFILES_STORAGE = 'andina.staticfiles_storage.NonStrictCompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'static_media')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_PUBLIC_BUCKET_NAME = os.getenv('AWS_PUBLIC_BUCKET_NAME', AWS_STORAGE_BUCKET_NAME)
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', 'https://storages.somosandina.co')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_ADDRESSING_STYLE = os.getenv('AWS_S3_ADDRESSING_STYLE', 'path')
AWS_QUERYSTRING_AUTH = env_bool('AWS_QUERYSTRING_AUTH', True)
AWS_S3_SIGNATURE_VERSION = os.getenv('AWS_S3_SIGNATURE_VERSION', 's3v4')
AWS_QUERYSTRING_EXPIRE = int(os.getenv('AWS_QUERYSTRING_EXPIRE', 3600))
AWS_DEFAULT_ACL = None

if USE_S3_MEDIA:
    DEFAULT_FILE_STORAGE = 'andina.storage_backends.PrivateMediaStorage'

# ─── Cron ────────────────────────────────────────────────────────────────────

CRON_CLASSES = [
    'andinasoft.cron_jobs.job_cartera',
]

CRONJOBS = [
    ('*/5 * * * *', 'andinasoft.cron_jobs.ejemplo_job'),
    ('0 3 * * *', 'django.core.management.call_command', ['cleanup_tmp_files', '--hours', '24']),
]

# ─── Email ───────────────────────────────────────────────────────────────────

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = os.getenv('EMAIL_HOST')
EMAIL_PORT          = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS       = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER     = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL  = os.getenv('DEFAULT_FROM_EMAIL')
SERVER_EMAIL        = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

ADMINS = []
_admins_raw = os.getenv('ADMINS', '').strip()
if _admins_raw:
    for admin in _admins_raw.split(','):
        admin = admin.strip()
        if not admin:
            continue
        if ':' in admin:
            name, email = admin.split(':', 1)
            ADMINS.append((name.strip() or email.strip(), email.strip()))
        else:
            ADMINS.append((admin, admin))

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
    DIR_DOWNLOADS = MEDIA_URL + 'tmp/'
else:
    DIR_DOCS      = MEDIA_ROOT + '/'
    DIR_EXPORT    = MEDIA_ROOT + '/'
    DIR_DOWNLOADS = '/media/'

# ─── N8N Webhooks ─────────────────────────────────────────────────────────────

_n8n_base_default = 'https://n8n.2asoft.tech' if LIVE else 'http://localhost:5678'
N8N_BASE_URL = os.getenv('N8N_BASE_URL', _n8n_base_default).rstrip('/')
N8N_WEBHOOK_UPLOAD_MOVEMENTS = os.getenv(
    'N8N_WEBHOOK_UPLOAD_MOVEMENTS',
    f'{N8N_BASE_URL}/webhook/upload-movements'
)
N8N_WEBHOOK_WOMPI_COUNT = os.getenv(
    'N8N_WEBHOOK_WOMPI_COUNT',
    f'{N8N_BASE_URL}/webhook/wompi-count'
)
N8N_WEBHOOK_PLINK_COUNT = os.getenv(
    'N8N_WEBHOOK_PLINK_COUNT',
    f'{N8N_BASE_URL}/webhook/plink-count'
)

# ─── Logging ──────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'mcp_server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
