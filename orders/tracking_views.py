"""
Place order (SRS UC1) and real-time order status tracking (3.3, UC3, FR4).

"Real time" here means the tracking page asks the server for the latest
status every few seconds. That works on our current hosting with no extra
services; WebSockets would need Django Channels and Redis.
"""

from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import FulfillmentSettings, Order
from .placement import (
    EmptyCartError,
    OutOfStockError,
    cart_items_for,
    cart_subtotal,
    place_order,
)
from .serializers import FulfillmentSerializer
from .tracking_serializers import OrderReceiptSerializer, OrderTrackingSerializer

EMPTY_CART = {"errors": {"cart": "Your cart is empty."}}


def _order_with_details(**lookup):
    queryset = Order.objects.prefetch_related("items", "status_events")
    return get_object_or_404(queryset, **lookup)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def place_order_view(request):
    """
    Turn the logged-in customer's cart into an order.

    Body: the same pickup/delivery fields as the checkout page sends,
    e.g. {"fulfillment_type": "pickup", "contact_phone": "9195551234"}.
    Any subtotal sent by the browser is ignored; totals use database prices.
    """
    store = FulfillmentSettings.load()
    items = cart_items_for(request.user)
    if not items:
        return Response(EMPTY_CART, status=status.HTTP_400_BAD_REQUEST)

    serializer = FulfillmentSerializer(
        data=request.data,
        context={"store_settings": store, "subtotal": cart_subtotal(items)},
    )
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        order = place_order(request.user, serializer.to_order_fields(), store)
    except EmptyCartError:
        return Response(EMPTY_CART, status=status.HTTP_400_BAD_REQUEST)
    except OutOfStockError as exc:
        names = ", ".join(p["name"] for p in exc.problems)
        return Response(
            {
                "errors": {"cart": f"Not enough stock for: {names}. Update your cart and try again."},
                "out_of_stock": exc.problems,
            },
            status=status.HTTP_409_CONFLICT,
        )

    order = _order_with_details(pk=order.pk)
    return Response(
        OrderReceiptSerializer(order, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def order_tracking_api(request, tracking_code):
    """Current status of an order. The tracking code acts as the password."""
    order = _order_with_details(tracking_code=tracking_code)
    return Response(OrderTrackingSerializer(order).data)


@never_cache
def order_tracking_page(request, tracking_code):
    """Confirmation and live tracking page the customer lands on after ordering."""
    order = _order_with_details(tracking_code=tracking_code)
    return render(request, "orders/order_status.html", {
        "order": order,
        "initial_data": OrderTrackingSerializer(order).data,
    })
