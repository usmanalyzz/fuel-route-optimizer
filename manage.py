#!/usr/bin/env python
"""
Django command-line entry point for the Fuel Route Optimizer project.

Usage examples:
    python manage.py runserver
    python manage.py migrate
    python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv
"""
import os
import sys


def main():
    """Configure Django settings and delegate to Django's management CLI."""
    # Tell Django which settings module to load
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # Pass CLI arguments (e.g. runserver, migrate) to Django
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
