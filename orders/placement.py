"""
Place order: turns the customer's cart into a saved order (SRS UC1, FR2, DF1).

Prices always come from the database, never from the browser. Everything
happens in one transaction, so an order is never half-saved: if any item
is out of stock, nothing is created and the cart is left alone.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from cart.models import CartItem
from products.models import Product

from .models import Order, OrderItem
from .services import calculate_totals, money
from accounts.models import RewardAccount
from .rewards import calculate_redemption_discount

class EmptyCartError(Exception):
    """The customer tried to check out with nothing in their cart."""


class OutOfStockError(Exception):
    """One or more cart items don't have enough stock left."""

    def __init__(self, problems):
        super().__init__("Some items don't have enough stock.")
        # [{"product_id", "name", "requested", "available"}, ...]
        self.problems = problems

class InsufficientPointsError(Exception):
    """Customer does not have enough reward points."""
    pass

def cart_items_for(user):
    return list(
        CartItem.objects.select_related("product")
        .filter(cart__user=user)
        .order_by("id")
    )


def cart_subtotal(items):
    return money(sum((i.product.price * i.quantity for i in items), Decimal("0")))


def place_order(user,fulfillment_fields,store_settings,points_to_redeem=0,):
    """
    Create an Order with its items from the user's cart, take the items out
    of stock and empty the cart. `fulfillment_fields` comes from
    FulfillmentSerializer.to_order_fields().
    """
    with transaction.atomic():
        items = cart_items_for(user)

        if (
            isinstance(points_to_redeem, bool)
            or not isinstance(points_to_redeem, int)
            or points_to_redeem < 0
        ):
            raise ValueError("Points must be a non-negative whole number.")

        reward_account = None
        redemption_discount = Decimal("0.00")

        if points_to_redeem > 0:
            try:
                reward_account = RewardAccount.objects.select_for_update().get(
                    user=user
                )
            except RewardAccount.DoesNotExist:
                raise InsufficientPointsError(
                    "You don't have enough reward points."
                )

            if reward_account.points_balance < points_to_redeem:
                raise InsufficientPointsError(
                    "You don't have enough reward points."
                )

            redemption_discount = calculate_redemption_discount(
                points_to_redeem
            )

        if not items:
            raise EmptyCartError()

        # Lock the products so two orders can't both take the last item.
        products = Product.objects.select_for_update().in_bulk(
            [i.product_id for i in items]
        )

        # The same product could sit in two carts if a user has more than one,
        # so add up quantities per product before checking stock.
        wanted = {}
        for item in items:
            wanted[item.product_id] = wanted.get(item.product_id, 0) + item.quantity

        problems = [
            {
                "product_id": pid,
                "name": products[pid].name,
                "requested": qty,
                "available": products[pid].stock,
            }
            for pid, qty in wanted.items()
            if qty > products[pid].stock
        ]
        if problems:
            raise OutOfStockError(problems)

        subtotal = money(sum(
            (products[pid].price * qty for pid, qty in wanted.items()), Decimal("0")
        ))

        if redemption_discount > subtotal:
            raise ValueError(
                "Reward discount cannot exceed the order subtotal."
            )

        totals = calculate_totals(
            subtotal,
            fulfillment_fields["fulfillment_type"],
            store_settings,
            redemption_discount=redemption_discount,
        )


        order = Order.objects.create(
            user=user,
            points_redeemed=points_to_redeem,
            redemption_discount=redemption_discount,
            **fulfillment_fields,
            **totals,
            estimated_ready_at=Order.estimate_ready_at(
                fulfillment_fields["fulfillment_type"], store_settings,
            ),
        )

        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=products[pid],
                name=products[pid].name,
                unit_price=products[pid].price,
                quantity=qty,
            )
            for pid, qty in wanted.items()
        ])

        for pid, qty in wanted.items():
            product = products[pid]
            product.stock -= qty
            product.save(update_fields=["stock"])

        if points_to_redeem > 0:
            updated = RewardAccount.objects.filter(
                pk=reward_account.pk,
                points_balance__gte=points_to_redeem,
            ).update(
                points_balance=F("points_balance") - points_to_redeem
            )

            if updated != 1:
                raise InsufficientPointsError(
                    "You don't have enough reward points."
                )

        CartItem.objects.filter(id__in=[i.id for i in items]).delete()

    return order
