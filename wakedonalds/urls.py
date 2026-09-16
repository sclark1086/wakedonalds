# wakedonalds/urls.py

from django.contrib import admin
from django.urls import path
from core.views import health_check, menu_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
]
