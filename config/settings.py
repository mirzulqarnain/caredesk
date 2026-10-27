"""
CareDesk LMS settings.

Everything that changes between laptop, EC2 and Elastic Beanstalk is read from
environment variables (or a .env file next to manage.py).

Database : SQLite locally, PostgreSQL on Amazon RDS when DB_HOST (or the
           Beanstalk-provided RDS_HOSTNAME) is set.
Files    : local /media folder locally, Amazon S3 when USE_S3=True.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(os.environ.get(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", "dev-only-secret-key-change-me-in-production")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "accounts",
    "clinic",
    "appointments",
    "records",
    "billing",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.site",
            ],
        },
    },
]

# Sits behind an Nginx / load balancer on both EC2 and Elastic Beanstalk.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# --------------------------------------------------------------------------
# Database: SQLite locally, PostgreSQL on RDS
# --------------------------------------------------------------------------
DB_HOST = env("DB_HOST") or env("RDS_HOSTNAME")
if DB_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME") or env("RDS_DB_NAME", "caredesk"),
            "USER": env("DB_USER") or env("RDS_USERNAME", "postgres"),
            "PASSWORD": env("DB_PASSWORD") or env("RDS_PASSWORD", ""),
            "HOST": DB_HOST,
            "PORT": env("DB_PORT") or env("RDS_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "connect_timeout": 10,
                "sslmode": env("DB_SSLMODE", "prefer"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static and media files
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

USE_S3 = env_bool("USE_S3", False)
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "us-east-1")

if USE_S3:
    # No keys needed on AWS: boto3 picks up the IAM role of the EC2 instance or
    # the Elastic Beanstalk instance profile. Keys are only for a laptop.
    s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME,
        "signature_version": "s3v4",
        "querystring_auth": True,      # bucket stays private, links are pre-signed
        "querystring_expire": 3600,
        "file_overwrite": False,
        "default_acl": None,
    }
    if env("AWS_ACCESS_KEY_ID") and env("AWS_SECRET_ACCESS_KEY"):
        s3_options["access_key"] = env("AWS_ACCESS_KEY_ID")
        s3_options["secret_key"] = env("AWS_SECRET_ACCESS_KEY")
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": s3_options}

# Uploaded files are streamed to disk by Django, so large videos do not sit in RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MAX_FILE_MB = int(env("MAX_FILE_MB", "25"))

# Shown in the interface
CLINIC_NAME = env("CLINIC_NAME", "CareDesk Clinic")
CURRENCY = env("CURRENCY", "$")

# --------------------------------------------------------------------------
# Logging (goes to stdout: journalctl on EC2, eb-engine logs on Beanstalk)
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
