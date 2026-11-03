from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from .models import FulfillmentSettings, Order
from .serializers import (OrderHistorySerializer,OrderStatusSerializer,QuoteRequestSerializer,)
from .services import calculate_totals
from decimal import Decimal, InvalidOperation
from django.db import DatabaseError
from .placement import (
    place_order,
    EmptyCartError,
    OutOfStockError,
    InsufficientPointsError,
)
from .serializers import FulfillmentSerializer
from cart.models import CartItem
from accounts.models import RewardAccount
from django.urls import reverse
from rest_framework.test import APIClient
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
        "delivery_minutes": (
            s.pickup_prep_minutes + s.delivery_extra_minutes
        ),
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def fulfillment_quote(request):
    """Validate a pickup/delivery choice and return the price breakdown."""

    store = FulfillmentSettings.load()

    serializer = QuoteRequestSerializer(
        data=request.data,
        context={"store_settings": store},
    )

    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    kind = serializer.validated_data["fulfillment_type"]

    totals = calculate_totals(
        serializer.validated_data["subtotal"],
        kind,
        store,
    )

    return Response({
        "fulfillment_type": kind,
        **totals,
        "estimated_ready_at": Order.estimate_ready_at(
            kind,
            store,
        ),
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
            {
                "errors": {
                    "status": (
                        f"This {order.get_fulfillment_type_display().lower()} "
                        f"order is marked '{order.get_status_display()}', "
                        "which doesn't fit its type. "
                        "Fix it in the admin first."
                    )
                },
                "next_status": None,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if not order.can_transition_to(new_status):
        return Response(
            {
                "errors": {
                    "status": (
                        f"A {order.get_fulfillment_type_display().lower()} "
                        f"order can't go from "
                        f"'{order.get_status_display()}' to "
                        f"'{Order.Status(new_status).label}'."
                    )
                },
                "next_status": order.next_status(),
            },
            status=status.HTTP_409_CONFLICT,
        )

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    return Response({
        "id": order.pk,
        "status": order.status,
        "next_status": order.next_status(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_history(request):
    """
    Return previous orders for the currently logged-in customer.

    Users can only see orders connected to their own account.
    """

    orders = Order.objects.filter(
        user=request.user
    ).order_by("-created_at")

    serializer = OrderHistorySerializer(
        orders,
        many=True,
    )

    return Response(serializer.data)


def checkout_view(request):
    """
    Checkout page with the pickup/delivery selector.

    TODO(cart merge): replace the demo subtotal with the real cart total
    once the cart branch is merged into main.
    """

    demo_subtotal = request.GET.get(
        "subtotal",
        "14.97",
    )

    return render(
        request,
        "orders/checkout.html",
        {"subtotal": demo_subtotal},
    )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def place_order_view(request):
    """Place an order and optionally redeem reward points."""

    points = request.data.get("points_to_redeem", 0)

    if isinstance(points, bool) or not str(points).isdigit():
        return Response(
            {"error": "Points must be a non-negative whole number."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    points = int(points)
    store = FulfillmentSettings.load()

    items = CartItem.objects.select_related("product").filter(
        cart__user=request.user
    )

    subtotal = sum(
        (item.product.price * item.quantity for item in items),
        Decimal("0.00"),
    )

    serializer = FulfillmentSerializer(
        data=request.data,
        context={
            "store_settings": store,
            "subtotal": subtotal,
        },
    )

    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        order = place_order(
            user=request.user,
            fulfillment_fields=serializer.to_order_fields(),
            store_settings=store,
            points_to_redeem=points,
        )
    except EmptyCartError:
        return Response(
            {"error": "Your cart is empty."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except InsufficientPointsError:
        return Response(
            {"error": "You don't have enough reward points."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except OutOfStockError as exc:
        return Response(
            {"error": "Some items are out of stock.", "items": exc.problems},
            status=status.HTTP_409_CONFLICT,
        )
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reward = RewardAccount.objects.filter(user=request.user).first()

    return Response(
        {
            "order_id": order.pk,
            "subtotal": order.subtotal,
            "redemption_discount": order.redemption_discount,
            "points_redeemed": order.points_redeemed,
            "tax": order.tax,
            "delivery_fee": order.delivery_fee,
            "total_price": order.total_price,
            "remaining_points": reward.points_balance if reward else 0,
        },
        status=status.HTTP_201_CREATED,
    )



def test_api_redeems_points(self):
    response = self.client.post(
        self.url,
        {
            "fulfillment_type": "pickup",
            "points_to_redeem": 500,
        },
        format="json",
    )

    self.assertEqual(
        response.status_code,
        201,
        response.data,
    )

    self.reward.refresh_from_db()

    self.assertEqual(self.reward.points_balance, 300)
    self.assertEqual(response.data["points_redeemed"], 500)
    self.assertEqual(
        Decimal(str(response.data["redemption_discount"])),
        Decimal("5.00"),
    )
    self.assertEqual(
        Decimal(str(response.data["total_price"])),
        Decimal("21.45"),
    )

def test_api_rejects_insufficient_points(self):
    response = self.client.post(
        self.url,
        {
            "fulfillment_type": "pickup",
            "points_to_redeem": 1000,
        },
        format="json",
    )

    self.assertEqual(response.status_code, 400)

    self.reward.refresh_from_db()
    self.assertEqual(self.reward.points_balance, 800)

    self.assertFalse(
        Order.objects.filter(user=self.user).exists()
    )
