import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    "messenger",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

if os.getenv("USE_POSTGRES", "0") == "1":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "secure_messenger"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = os.getenv("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "0") == "1"
_cors_allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
if DEBUG and not CORS_ALLOW_ALL_ORIGINS and not _cors_allowed_origins:
    # Keep local development simple unless explicitly overridden.
    CORS_ALLOW_ALL_ORIGINS = True
elif not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = _cors_allowed_origins

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Stage 0 test-lab foundations/guardrails placeholders.
# These values establish explicit vocabulary and policy hooks; deeper enforcement
# will be layered in subsequent stages.
TEST_LAB_ENV = os.getenv("TEST_LAB_ENV", "local").strip().lower()
TEST_LAB_ALLOWED_ENVIRONMENTS = [
    value.strip().lower()
    for value in os.getenv("TEST_LAB_ALLOWED_ENVIRONMENTS", "local,sandbox,staging").split(",")
    if value.strip()
]
TEST_LAB_FEATURE_FLAGS = {
    "test_menu_enabled": os.getenv("TEST_LAB_TEST_MENU_ENABLED", "1") == "1",
    "synthetic_scenarios_enabled": os.getenv("TEST_LAB_SYNTHETIC_SCENARIOS_ENABLED", "1") == "1",
    "verbose_diagnostics_enabled": os.getenv("TEST_LAB_VERBOSE_DIAGNOSTICS_ENABLED", "0") == "1",
    "group_testing_enabled": os.getenv("TEST_LAB_GROUP_TESTING_ENABLED", "0") == "1",
}
TEST_LAB_ADMIN_USERNAMES = [
    value.strip()
    for value in os.getenv("TEST_LAB_ADMIN_USERNAMES", "").split(",")
    if value.strip()
]
TEST_LAB_TEST_USER_USERNAMES = [
    value.strip()
    for value in os.getenv("TEST_LAB_TEST_USER_USERNAMES", "").split(",")
    if value.strip()
]
TEST_LAB_POLICY_LIMITS = {
    "max_active_admins": 1,
    "max_active_test_users_default": 2,
    "max_active_test_users_group_enabled": 3,
}

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
if os.getenv("USE_REDIS", "0") == "1":
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
