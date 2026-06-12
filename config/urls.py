"""
Root URL configuration for the Fuel Route Optimizer project.

Maps top-level URL paths to included app URL modules.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),           # Django admin interface
    path("api/v1/", include("routing.urls")),  # Fuel routing API endpoints
]
