"""
WSGI config for Fuel Route Optimizer.

Exposes the WSGI callable as ``application`` for production servers
(e.g. gunicorn, uWSGI).
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
