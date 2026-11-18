"""
Rewards math, kept in one place for features 4.1 (earn) and 4.2 (redeem).

Each function loads the current settings unless one is passed in, so a
change an admin saves applies to the very next call.
"""

from decimal import ROUND_DOWN, Decimal

from .models import RewardsSettings

CENT = Decimal("0.01")


def points_for_amount(amount, settings=None):
    """Whole points earned for spending `amount` dollars (partial points are dropped)."""
    settings = settings or RewardsSettings.load()
    amount = Decimal(str(amount))
    if not settings.program_enabled or amount <= 0:
        return 0
    return int((amount * settings.points_per_dollar).to_integral_value(rounding=ROUND_DOWN))


def points_value(points, settings=None):
    """Dollar value of `points` when redeemed, rounded down to the cent."""
    settings = settings or RewardsSettings.load()
    if points <= 0:
        return Decimal("0.00")
    return (Decimal(points) * settings.point_value).quantize(CENT, rounding=ROUND_DOWN)


def can_redeem(points_balance, points_cost, settings=None):
    """True when the program is on and the balance covers the cost and the minimum."""
    settings = settings or RewardsSettings.load()
    return (
        settings.program_enabled
        and points_balance >= settings.minimum_redemption_points
        and points_balance >= points_cost
    )
