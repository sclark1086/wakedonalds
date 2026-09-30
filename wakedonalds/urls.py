# wakedonalds/urls.py

from django.contrib import admin
from django.urls import path, include
from core.views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    path('api/cart/', include('cart.urls')),
]