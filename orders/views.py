from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import FulfillmentSettings, Order
from .serializers import OrderStatusSerializer, QuoteRequestSerializer
from .services import calculate_totals


@api_view(["GET"])
@permission_classes([AllowAny])
def fulfillment_options(request):
    """What the checkout page needs to draw the pickup/delivery choice."""
    s = FulfillmentSettings.load()
    return Response({
        "pickup_enabled": s.pickup_enabled,
        "delivery_enabled": s.delivery_enabled,
        "delivery_fee": s.delivery_fee,
        "free_delivery_minimum": s.free_delivery_minimum,
        "delivery_minimum_subtotal": s.delivery_minimum_subtotal,
        "tax_rate": s.tax_rate,
        "pickup_minutes": s.pickup_prep_minutes,
        "delivery_minutes": s.pickup_prep_minutes + s.delivery_extra_minutes,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def fulfillment_quote(request):
    """Validate a pickup/delivery choice and return the price breakdown."""
    store = FulfillmentSettings.load()
    serializer = QuoteRequestSerializer(data=request.data, context={"store_settings": store})
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    kind = serializer.validated_data["fulfillment_type"]
    totals = calculate_totals(serializer.validated_data["subtotal"], kind, store)
    return Response({
        "fulfillment_type": kind,
        **totals,
        "estimated_ready_at": Order.estimate_ready_at(kind, store),
    })


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def update_order_status(request, order_id):
    """Staff move an order one step along its pickup or delivery flow."""
    order = get_object_or_404(Order, pk=order_id)
    serializer = OrderStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    new_status = serializer.validated_data["status"]

    if not order.status_matches_type():
        return Response(
            {"errors": {"status": f"This {order.get_fulfillment_type_display().lower()} order is marked "
                                  f"'{order.get_status_display()}', which doesn't fit its type. "
                                  f"Fix it in the admin first."},
             "next_status": None},
            status=status.HTTP_409_CONFLICT,
        )
    if not order.can_transition_to(new_status):
        return Response(
            {"errors": {"status": f"A {order.get_fulfillment_type_display().lower()} order can't go from "
                                  f"'{order.get_status_display()}' to '{Order.Status(new_status).label}'."},
             "next_status": order.next_status()},
            status=status.HTTP_409_CONFLICT,
        )
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    return Response({"id": order.pk, "status": order.status, "next_status": order.next_status()})


def checkout_view(request):
    """
    Checkout page with the pickup/delivery selector.

    TODO(cart merge): replace the demo subtotal with the real cart total
    once the cart branch is merged into main.
    """
    demo_subtotal = request.GET.get("subtotal", "14.97")
    return render(request, "orders/checkout.html", {"subtotal": demo_subtotal})