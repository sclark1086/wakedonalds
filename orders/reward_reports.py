
from decimal import Decimal

from django.db.models import Sum, Count
from django.utils import timezone

from .models import Order


def monthly_reward_redemption_report(year=None, month=None):
    """Generate a monthly reward redemption summary."""

    today = timezone.localdate()

    if year is None:
        year = today.year

    if month is None:
        month = today.month

    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12.")

    orders = Order.objects.filter(
        created_at__year=year,
        created_at__month=month,
        points_redeemed__gt=0,
    )

    summary = orders.aggregate(
        total_points=Sum("points_redeemed"),
        total_saved=Sum("redemption_discount"),
        total_orders=Count("pk"),
    )

    return {
        "year": year,
        "month": month,
        "total_points_redeemed": summary["total_points"] or 0,
        "total_money_saved": (
            summary["total_saved"] or Decimal("0.00")
        ),
        "orders_with_redemptions": summary["total_orders"] or 0,
    }
