from django.urls import path

from . import views

urlpatterns = [
    path("thresholds/", views.threshold_list, name="inventory-thresholds"),
    path("thresholds/<int:product_id>/", views.threshold_detail, name="inventory-threshold-detail"),
]
