# main\settings.py НОВЫЙ НОВЫЙ
from pathlib import Path
from decouple import config
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# для продакшна
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
# ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')
# Для локальной разработки в .env стоит DEBUG=True

ALLOWED_HOSTS = ['91.197.96.233', 'webtable-ja.ru', 'localhost', '127.0.0.1', 'neurostat.ru', 'www.neurostat.ru']

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Для collectstatic
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')         # Для загруженных файлов
MEDIA_URL = '/media/'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'main',
    'main.apps.MainConfig',  # ← ВАЖНО: не просто 'main', а с указанием класса - для отправки писем с оповещением для бд
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

ROOT_URLCONF = 'main.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'main' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'main.wsgi.application'

# Database
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'neurostat',
        # 'USER': 'myuser',
        # 'PASSWORD': 'mypassword',
        'USER': 'myuser',
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',  # noqa: E501
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'main' / 'static',
]

LOGIN_REDIRECT_URL = '/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')

# домен (для ссылок в письмах)
SITE_URL = 'http://127.0.0.1:8000'  # В продакшене: 'https://https://neurostat.ru'

# Prod security settings (enabled when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = False # False - временно, до настройки HTTPS
    CSRF_COOKIE_SECURE = False # False - временно, до настройки HTTPS
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

    # If behind reverse proxy (e.g., Nginx)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CSRF trusted origins (comma-separated list), e.g. https://example.com,https://www.example.com
CSRF_TRUSTED_ORIGINS = [
    origin for origin in config('CSRF_TRUSTED_ORIGINS', default='', cast=str).split(',') if origin
]


# в продакшне раскоммментировать:

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django_error.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'main': {                      # ← новый логгер для всего приложения
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'bot-cache',
    }
}

YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', '')

# --- EMAIL: уведомления об оплате ---
EMAIL_SUBJECT_PREFIX = '[Нейростат] '
DEFAULT_FROM_EMAIL = 'Нейростат <neurostat@bk.ru>'   # имя отправителя в письмах
EMAIL_TIMEOUT = 10                                   # чтобы SMTP не подвешивал вебхук
OWNER_NOTIFY_EMAIL = 'a_timof@mail.ru'               # куда слать себе уведомления
SITE_URL = 'https://neurostat.ru'                    # для ссылок в письмах

VK_BOT_LINK = 'https://vk.me/neurostat'
MAX_BOT_LINK = 'https://max.ru/id450400800854_bot'
