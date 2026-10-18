"""Routes for place order and order tracking (3.3).

Kept separate from orders/urls.py so this feature doesn't collide with
other open pull requests that edit that file.
"""

from django.urls import path

from . import tracking_views

urlpatterns = [
    path("api/orders/", tracking_views.place_order_view, name="place-order"),
    path(
        "api/orders/track/<str:tracking_code>/",
        tracking_views.order_tracking_api,
        name="order-tracking",
    ),
    path(
        "orders/track/<str:tracking_code>/",
        tracking_views.order_tracking_page,
        name="order-tracking-page",
    ),
]
