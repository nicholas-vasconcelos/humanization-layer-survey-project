from pathlib import Path
import os
 
BASE_DIR = Path(__file__).resolve().parent.parent
 
# ── Security ──────────────────────────────────────────────────────────────────
# Load from environment in production; fallback only for local dev
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    ''
)
 
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
 
 
def _clean_csv_env(value):
    return [item.strip() for item in value.split(',') if item.strip()]
 
 
ALLOWED_HOSTS = _clean_csv_env(os.environ.get('ALLOWED_HOSTS', '*'))
 
 
_raw_csrf_trusted_origins = _clean_csv_env(
    os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost,http://127.0.0.1,https://*.elasticbeanstalk.com,http://*.elasticbeanstalk.com',
    )
)
 
# Deriva origens confiáveis a partir de ALLOWED_HOSTS para evitar falhas de CSRF
# em ambientes com proxy HTTPS (ex.: AWS Elastic Beanstalk/ALB).
_derived_csrf_origins = []
for host in ALLOWED_HOSTS:
    cleaned_host = host.strip()
    if not cleaned_host or cleaned_host == '*':
        continue
 
    # Remove porta e mantém wildcard no início (ex.: .elasticbeanstalk.com).
    hostname = cleaned_host.split(':', 1)[0]
    if not hostname:
        continue
 
    # Django usa ".example.com" em ALLOWED_HOSTS para subdomínios;
    # para CSRF_TRUSTED_ORIGINS o formato é "*.example.com".
    if hostname.startswith('.'):
        hostname = f'*{hostname}'
 
    _derived_csrf_origins.append(f'https://{hostname}')
    _derived_csrf_origins.append(f'http://{hostname}')
 
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_raw_csrf_trusted_origins + _derived_csrf_origins))
 
# ── Application definition ────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'produtos',
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
 
ROOT_URLCONF = 'catalogo.urls'
 
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
 
WSGI_APPLICATION = 'catalogo.wsgi.application'
 
# ── Database ──────────────────────────────────────────────────────────────────
# SQLite for local dev; swap for PostgreSQL (Supabase) via env var in production
DATABASE_URL = os.environ.get('DATABASE_URL')
 
if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
 
# ── Sessions ──────────────────────────────────────────────────────────────────
# Use database-backed sessions to persist flow data across requests
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = 3600
SESSION_COOKIE_HTTPONLY = True
 
# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
 
# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
 
# ── Static & Media files ──────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
 
MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
 
# ── External API keys (loaded from environment) ───────────────────────────────
GROQ_API_KEY      = os.environ.get('GROQ_API_KEY', '')
SUPABASE_URL      = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
 
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
 
# ── Security settings for mobile production (override in development) ─────────────────
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
 
# Em Elastic Beanstalk, o SSL costuma terminar no load balancer.
# Esses headers permitem ao Django reconhecer corretamente requisições HTTPS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
 
# In settings.py, add temporarily for debug:
import logging
logger = logging.getLogger(__name__)
logger.info(f"SUPABASE_URL configured: {bool(SUPABASE_URL)}")
logger.info(f"SUPABASE_ANON_KEY configured: {bool(SUPABASE_ANON_KEY)}")
logger.info(f"GROQ_API_KEY configured: {bool(GROQ_API_KEY)}")