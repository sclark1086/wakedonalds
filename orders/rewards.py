from decimal import Decimal, ROUND_DOWN
from django.db import transaction
from django.db.models import F

from accounts.models import RewardAccount
from .models import Order

def calculate_reward_points(order):
    """Calculate 1 point for every whole dollar spent."""

    if order.user_id is None:
        return 0

    if order.status not in [
        order.Status.COMPLETED,
        order.Status.DELIVERED,
    ]:
        return 0

    return int(
        Decimal(str(order.total_price)).to_integral_value(
            rounding=ROUND_DOWN
        )
    )

def award_reward_points(order):
    """Award points once when an order is finished."""

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.user_id is None or order.points_awarded:
            return 0

        if order.fulfillment_type == Order.FulfillmentType.PICKUP:
            if order.status != Order.Status.COMPLETED:
                return 0

        elif order.fulfillment_type == Order.FulfillmentType.DELIVERY:
            if order.status != Order.Status.DELIVERED:
                return 0

        else:
            return 0

        points = calculate_reward_points(order)

        reward_account, created = RewardAccount.objects.get_or_create(
            user_id=order.user_id
        )

        RewardAccount.objects.filter(
            pk=reward_account.pk
        ).update(
            points_balance=F("points_balance") + points
        )

        order.points_earned = points
        order.points_awarded = True
        order.save(update_fields=["points_earned", "points_awarded"])

        return points

def calculate_redemption_discount(points):
    """Convert 100 reward points into a $1 discount."""

    if isinstance(points, bool) or not isinstance(points, int):
        raise ValueError("Points must be a whole number.")

    if points < 0:
        raise ValueError("Points cannot be negative.")

    return (Decimal(points) / Decimal("100")).quantize(
        Decimal("0.01")
    )
