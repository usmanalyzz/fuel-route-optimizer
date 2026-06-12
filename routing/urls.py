"""
URL routing for the routing API app.

All endpoints are mounted under /api/v1/ by config/urls.py.
"""
from django.urls import path

from routing.views import RouteView

urlpatterns = [
    # POST /api/v1/route/ — compute route and optimal fuel stops
    path("route/", RouteView.as_view(), name="route"),
]
