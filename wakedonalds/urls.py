# wakedonalds/urls.py


from django.contrib import admin
from django.urls import include, path
from core.views import health_check, menu_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/health/', health_check, name='health-check'),
    path('api/cart/', include('cart.urls')),
    path('', include('orders.tracking_urls')),
    path('', include('orders.urls')),
    path('menu/', menu_view, name='menu'),
    path('api/accounts/', include('accounts.urls')),
]
