"""
Django settings for the Fuel Route Optimizer project.

Loads configuration from environment variables (.env) and defines
fuel-routing constants, external API URLs, and database connection.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load variables from .env file in project root
load_dotenv()

# Detect when running tests so we can use SQLite in-memory instead of PostgreSQL
TESTING = "test" in sys.argv

# Project root directory (parent of config/)
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core Django settings ---

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",  # Django REST Framework for JSON API
    "routing",         # Our fuel routing application
]

MIDDLEWARE = [
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database configuration ---

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://fuel_router:fuel_router@localhost:5432/fuel_router"
)

if TESTING:
    # Tests use in-memory SQLite — no PostgreSQL required
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
elif DATABASE_URL.startswith("postgres://"):
    import urllib.parse

    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or 5432,
            "CONN_MAX_AGE": 60,  # Reuse DB connections for 60 seconds
        }
    }
else:
    # Fallback to SQLite file if DATABASE_URL is not postgres
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
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
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# --- Fuel routing business constants ---

MAX_RANGE_MILES = 500   # Vehicle can drive at most 500 miles between fuel stops
MPG = 10                # Vehicle fuel economy: 10 miles per gallon
CORRIDOR_MILES = 25     # Stations within this distance of route are candidates

# --- External geocoding and routing API endpoints ---

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"  # Address → lat/lon
OSRM_BASE_URL = "http://router.project-osrm.org"            # Driving route geometry

# --- USA bounding box for location validation (includes AK/HI margins) ---

USA_LAT_MIN = 18.0
USA_LAT_MAX = 72.0
USA_LON_MIN = -180.0
USA_LON_MAX = -66.0
