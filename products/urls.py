from django.urls import path

from . import views


urlpatterns = [
    path(
        "inventory/",
        views.inventory_report,
        name="inventory-report",
    ),
]