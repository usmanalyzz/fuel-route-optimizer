"""Django app configuration for the routing application."""
from django.apps import AppConfig


class RoutingConfig(AppConfig):
    """Registers the routing app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "routing"
