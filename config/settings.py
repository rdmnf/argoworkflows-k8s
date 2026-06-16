"""
Django settings for the AWF application.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)

DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

KEYCLOAK_PUBLIC_URL = os.getenv(
    "KEYCLOAK_PUBLIC_URL",
    os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
).rstrip("/")
KEYCLOAK_INTERNAL_URL = os.getenv(
    "KEYCLOAK_INTERNAL_URL",
    KEYCLOAK_PUBLIC_URL,
).rstrip("/")
# Backwards-compatible alias for existing configuration.
KEYCLOAK_URL = KEYCLOAK_PUBLIC_URL
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "awf")
PUBLIC_OIDC_BASE = (
    f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect"
)
INTERNAL_OIDC_BASE = (
    f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mozilla_django_oidc",
    "accounts",
    "core",
    "clusters",
    "resources",
    "workflows",
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

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "resources.context_processors.provisioning_ui",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication
AUTHENTICATION_BACKENDS = [
    "accounts.backends.KeycloakOIDCBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "oidc_authentication_init"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:home"

# Keycloak OIDC (via mozilla-django-oidc)
OIDC_RP_CLIENT_ID = os.getenv("OIDC_RP_CLIENT_ID", "awf-web")
OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_RP_CLIENT_SECRET", "")
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{PUBLIC_OIDC_BASE}/auth"
OIDC_OP_TOKEN_ENDPOINT = f"{INTERNAL_OIDC_BASE}/token"
OIDC_OP_USER_ENDPOINT = f"{INTERNAL_OIDC_BASE}/userinfo"
OIDC_OP_JWKS_ENDPOINT = f"{INTERNAL_OIDC_BASE}/certs"
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_CREATE_USER = True
OIDC_USERNAME_ALGO = "accounts.oidc.generate_username"
OIDC_OP_LOGOUT_ENDPOINT = f"{PUBLIC_OIDC_BASE}/logout"
OIDC_OP_LOGOUT_URL_METHOD = "accounts.oidc.provider_logout"
OIDC_STORE_ID_TOKEN = True
OIDC_STORE_ACCESS_TOKEN = True

KEYCLOAK_GROUPS_CLAIM = os.getenv("KEYCLOAK_GROUPS_CLAIM", "groups")
KEYCLOAK_ADMIN_GROUP = os.getenv("KEYCLOAK_ADMIN_GROUP", "admin")
KEYCLOAK_SYNC_DJANGO_GROUPS = os.getenv(
    "KEYCLOAK_SYNC_DJANGO_GROUPS", "true"
).lower() in ("true", "1", "yes")

# Resource provisioning
RESOURCE_PROVISION_NAMESPACE_ONLY = os.getenv(
    "RESOURCE_PROVISION_NAMESPACE_ONLY", "false"
).lower() in ("true", "1", "yes")
RESOURCE_PROVISION_CREATE_USER_TOKEN = os.getenv(
    "RESOURCE_PROVISION_CREATE_USER_TOKEN", "true"
).lower() in ("true", "1", "yes")
RESOURCE_PROVISION_SHOW_USER_TOKEN = os.getenv(
    "RESOURCE_PROVISION_SHOW_USER_TOKEN", "false"
).lower() in ("true", "1", "yes")
K8S_API_TIMEOUT_SECONDS = float(os.getenv("K8S_API_TIMEOUT_SECONDS", "30"))

# Session cookie settings for local development with Keycloak
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in (
    "true",
    "1",
    "yes",
)
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "false").lower() in (
    "true",
    "1",
    "yes",
)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
