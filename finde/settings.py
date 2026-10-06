"""
Django settings for the Finde project.

Configuration is read from environment variables (see .env.example).
"""
import logging
import os
import sys
from pathlib import Path

from decouple import config
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


class MediaRequestFilter(logging.Filter):
    def filter(self, record):
        # Ignore log entries that contain '/media/'
        return '/media/' not in record.getMessage()


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        # Suppress per-request access logs (including media requests)
        'django.server': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # App logs: set LOG_LEVEL=DEBUG to see size-parsing and search diagnostics
        'core': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'finde': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}


# Load .env before reading any other configuration
load_dotenv(BASE_DIR / '.env', override=True)

# eBay API credentials ("sandbox" or "production")
EBAY_ENV = os.getenv("EBAY_ENV")

if any(cmd in sys.argv for cmd in ['collectstatic', 'migrate', 'makemigrations', 'findstatic']):
    # Management commands that don't call eBay don't need real credentials
    EBAY_CREDENTIALS = {k: "dummy_value" for k in ["appid", "certid", "devid", "redirecturi"]}
else:
    prefix = "EBAY_SANDBOX_" if EBAY_ENV == "sandbox" else "EBAY_PROD_"
    EBAY_CREDENTIALS = {
        "appid": os.getenv(f"{prefix}APP_ID"),
        "certid": os.getenv(f"{prefix}CERT_ID"),
        "devid": os.getenv(f"{prefix}DEV_ID"),
        "redirecturi": os.getenv(f"{prefix}REDIRECT_URI"),
    }
    missing = [k for k, v in EBAY_CREDENTIALS.items() if not v]
    if missing:
        raise ValueError(f"Missing eBay credentials for {EBAY_ENV}: {missing}")


from core.opensearch_dsl import AOSSConnection  # noqa: E402  (AWS SigV4-signed connection)

# AWS-managed OpenSearch uses HTTPS + SigV4 signing; set OPENSEARCH_USE_AWS=False for a local node
OPENSEARCH_USE_AWS = config('OPENSEARCH_USE_AWS', default=True, cast=bool)

OPENSEARCH_DSL = {
    'default': {
        'hosts': [{
            'host': os.getenv('OPENSEARCH_HOST'),
            'port': int(os.getenv('OPENSEARCH_PORT', '443' if OPENSEARCH_USE_AWS else '9200')),
        }],
        'use_ssl': OPENSEARCH_USE_AWS,
        'verify_certs': OPENSEARCH_USE_AWS,
        'timeout': 60,
        **({'connection_class': AOSSConnection} if OPENSEARCH_USE_AWS else {}),
        'bulk': {
            'refresh': False,
        },
    }
}

SECRET_KEY = config('DJANGO_SECRET_KEY')
RECAPTCHA_SECRET_KEY = config('RECAPTCHA_SECRET_KEY')
ADMIN_USERNAME = config('ADMIN_USERNAME') 

# Must be False in production and when collecting static files
DEBUG = config('DEBUG', default=False, cast=bool)

# Trust Railway's reverse proxy headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Force HTTPS
USE_X_FORWARDED_HOST = True  # Respect Host header from proxy
MY_DEV_IP = config('MY_DEV_IP', default='')

ALLOWED_HOSTS = [
    'site.finde.clothing', # production via squarespace + railway
    'flamingo.finde.clothing',
    'www.finde.clothing',
    *os.getenv('RAILWAY_PUBLIC_DOMAIN', '').split(','),  # Auto-add Railway domain if detected. Railway injects this
]

# Add local dev IP only if not in production
if not os.getenv('RAILWAY_ENVIRONMENT'):
    ALLOWED_HOSTS += ['localhost', '127.0.0.1']
    if MY_DEV_IP:
        ALLOWED_HOSTS.append(MY_DEV_IP)

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME': config('DB_NAME', default='mydatabase'),
        'USER': config('DB_USER', default='user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='db'),  # Docker service name
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'ssl': {
                'ssl_ca': config('RDS_CA_CERT'),  # Path to the .pem certificate file (region: US East (Ohio), us-east-2) https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html#UsingWithRDS.SSL.CertificatesAllRegions
            } if os.getenv('RAILWAY_ENVIRONMENT') else {},  # Only enable SSL for Railway environment
        },
    }
}

# Override with Railway's DATABASE_URL if available
if os.getenv('DATABASE_URL'):
    db_url = os.getenv('DATABASE_URL')
    # Parse DATABASE_URL (format: postgres://user:pass@host:port/dbname)
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed.path[1:],  # Remove leading '/'
        'USER': parsed.username,
        'PASSWORD': parsed.password,
        'HOST': parsed.hostname,
        'PORT': parsed.port,
        'OPTIONS': {'sslmode': 'require'},
    }

LOGIN_URL = '/account/login/'
LOGIN_REDIRECT_URL = '/browse/'
LOGOUT_REDIRECT_URL = '/browse/'
ACCOUNT_LOGOUT_ON_GET = True # Logout immediately without showing confirmation page

# bypasses intermediary login and logout pages
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
# Django-allauth account settings
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False  # bypasses username requirement because username is auto generated

# Enhanced account settings
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""  # Remove default prefix from email subjects
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3  # Number of days email confirmation link is valid
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True  # Automatically log in users after confirming email
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "/"  # Where to redirect after confirmation if already logged in
ACCOUNT_CONFIRM_EMAIL_ON_GET = True  # Allow confirmation on GET request (better UX than requiring POST)
ACCOUNT_MAX_EMAIL_ADDRESSES = 1  # Limit number of email addresses per user if you want

# Custom adapter for better control over email sending
ACCOUNT_ADAPTER = 'core.adapters.CustomAccountAdapter'  # Point to your custom adapter

# Email backend configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')

# Add a display name to your from email (helps deliverability)
DEFAULT_FROM_EMAIL_NAME = "Finde"  # Email display name
DEFAULT_FROM_EMAIL_WITH_NAME = f"{DEFAULT_FROM_EMAIL_NAME} <{DEFAULT_FROM_EMAIL}>"

# Email sending settings
EMAIL_TIMEOUT = 30  # Timeout in seconds
EMAIL_USE_LOCALTIME = True  # Use local timezone for email timestamps

# Authentication backends
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend'
)

# Custom forms
ACCOUNT_FORMS = {
    'signup': 'core.forms.SignupForm',
}

# Set to empty string to prevent duplicate file extensions
ACCOUNT_EMAIL_CONFIRMATION_TEMPLATE = None  # We'll use the default allauth template path structure instead

SITE_ID = 1  # 'finde.clothing' in the Sites admin

INSTALLED_APPS = [
    'rest_framework',
    'django.contrib.admin',
    'django_cron',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'core.apps.CoreConfig',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django.contrib.humanize',
    'django_opensearch_dsl',
    'storages',
]

SOCIALACCOUNT_PROVIDERS = {
	"google": {
		"SCOPE": [
			"profile",
			"email"
		],
		"AUTH_PARAMS": {"access_type": "online"}
	}
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # for railway to recognize static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'core.middleware.CacheControlMiddleware',
]

CRON_CLASSES = [
    'core.cron.MoveOutOfStockItemsCronJob',
]

ROOT_URLCONF = 'finde.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'core/templates')],
        'APP_DIRS': True, # Automatically include app templates
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'finde.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'

if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / 'core/static'] # source folder(s) where your static files live

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Add these Whitenoise settings to fix 401 errors
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']
WHITENOISE_MAX_AGE = 86400  # 1 day (24 hours * 60 minutes * 60 seconds)

# Storage configuration
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "core.storage.StrictManifestStaticFilesStorage",  
    },
}

# AWS S3 settings
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')  
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY') 
AWS_STORAGE_BUCKET_NAME = 'finde-media' 
AWS_S3_REGION_NAME = 'us-east-2'  
AWS_S3_SIGNATURE_VERSION = 's3v4'  # This might be needed depending on your region
AWS_DEFAULT_ACL = None  # Default ACL for new files, can set to None for private uploads
AWS_QUERYSTRING_AUTH = False  # Set to False if you want media URLs to be public
AWS_S3_FILE_OVERWRITE = False  # Prevent overwriting files with the same name
AWS_DEFAULT_STORAGE_CLASS = 'STANDARD'  # Use standard storage class
MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# allow larger image uploads for profile pictures
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB


# Fashion Detection Settings
SMART_FASHION_DETECTION = {
    'MODEL_NAME': 'valentinafeve/yolos-fashionpedia',
    'CONFIDENCE_THRESHOLD': 0.5,
    'MAX_IMAGES_PER_ITEM': 9,
    'SUPPORTED_IMAGE_FORMATS': ['JPEG', 'PNG', 'WebP'],
    'MAX_IMAGE_SIZE': 10 * 1024 * 1024,  # 10MB
    'IMAGE_QUALITY': 85,  # JPEG quality for processed images
    'AUTO_CROP_PADDING': 20,  # Pixels of padding when auto-cropping
}

# Cache (Redis): rate limiting and cached eBay tokens
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'TIMEOUT': 300,  # 5 minutes default timeout
    }
}

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

# Anthropic Claude Vision, used for garment classification
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_VISION_RATE_LIMIT = 20  # requests per minute
