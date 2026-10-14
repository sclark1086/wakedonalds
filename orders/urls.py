from django.urls import path

from . import views

urlpatterns = [
    path("api/fulfillment/options/", views.fulfillment_options, name="fulfillment-options"),
    path("api/fulfillment/quote/", views.fulfillment_quote, name="fulfillment-quote"),
    path("api/orders/<int:order_id>/status/", views.update_order_status, name="order-status"),
    path("checkout/", views.checkout_view, name="checkout"),
]
