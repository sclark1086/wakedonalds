from django.urls import path
from .views import (
    CartView,
    AddToCartView,
    UpdateCartItemView,
)


urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("items/", AddToCartView.as_view(), name="add-to-cart"),
    path(
        "items/<int:item_id>/",
        UpdateCartItemView.as_view(),
        name="cart-item"
    ),
]