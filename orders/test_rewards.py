
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from cart.models import Cart, CartItem
from products.models import Product
from orders.placement import (place_order,InsufficientPointsError,OutOfStockError,)
from accounts.models import RewardAccount
from orders.models import Order, FulfillmentSettings
from orders.rewards import (award_reward_points,calculate_redemption_discount,)
from unittest.mock import patch

class RewardPointsTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rewardtest",
            password="TestPassword123!"
        )

    def create_order(self, status=Order.Status.RECEIVED, user=None):
        return Order.objects.create(
            user=self.user if user is None else user,
            fulfillment_type=Order.FulfillmentType.PICKUP,
            status=status,
            subtotal=Decimal("25.99"),
            tax=Decimal("0.00"),
            total_price=Decimal("25.99"),
        )

    def test_completed_order_earns_points(self):
        order = self.create_order()

        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.COMPLETED
            order.save()

        reward = RewardAccount.objects.get(user=self.user)

        self.assertEqual(reward.points_balance, 25)

    def test_points_are_not_awarded_twice(self):
        order = self.create_order()

        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.COMPLETED
            order.save()

        award_reward_points(order)

        reward = RewardAccount.objects.get(user=self.user)

        self.assertEqual(reward.points_balance, 25)

    def test_unfinished_order_earns_no_points(self):
        order = self.create_order()

        award_reward_points(order)

        self.assertFalse(
            RewardAccount.objects.filter(user=self.user).exists()
        )

class RewardRedemptionTests(TestCase):

    def test_points_convert_to_discount(self):
        discount = calculate_redemption_discount(500)

        self.assertEqual(discount, Decimal("5.00"))

    def test_zero_points_gives_no_discount(self):
        discount = calculate_redemption_discount(0)

        self.assertEqual(discount, Decimal("0.00"))

    def test_negative_points_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_redemption_discount(-100)

    def test_decimal_points_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_redemption_discount(Decimal("50.5"))

class RewardRedemptionIntegrationTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="redemptiontest",
            password="TestPassword123!"
        )

        self.store = FulfillmentSettings.load()

        self.reward_account = RewardAccount.objects.create(
            user=self.user,
            points_balance=800
        )

        self.product = Product.objects.create(
            name="Burger",
            price=Decimal("25.00"),
            stock=10
        )

        self.cart = Cart.objects.create(user=self.user)

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1
        )

    def test_redeeming_points_during_checkout(self):
        order = place_order(
            user=self.user,
            fulfillment_fields={
                "fulfillment_type": "pickup"
            },
            store_settings=self.store,
            points_to_redeem=500,
        )

        self.reward_account.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.reward_account.points_balance,
            300
        )

        self.assertEqual(
            order.points_redeemed,
            500
        )

        self.assertEqual(
            order.redemption_discount,
            Decimal("5.00")
        )

        self.assertEqual(
            order.total_price,
            Decimal("21.45")
        )

        self.assertEqual(self.product.stock, 9)

        self.assertFalse(
            CartItem.objects.filter(cart=self.cart).exists()
        )

    def test_insufficient_points_rejected(self):
        with self.assertRaises(InsufficientPointsError):
            place_order(
                user=self.user,
                fulfillment_fields={
                    "fulfillment_type": "pickup"
                },
                store_settings=self.store,
                points_to_redeem=1000,
            )

        self.reward_account.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.reward_account.points_balance,
            800
        )

        self.assertEqual(self.product.stock, 10)

        self.assertEqual(
            Order.objects.filter(user=self.user).count(),
            0
        )

    def test_failed_checkout_does_not_deduct_points(self):
        self.product.stock = 0
        self.product.save(update_fields=["stock"])

        with self.assertRaises(OutOfStockError):
            place_order(
                user=self.user,
                fulfillment_fields={
                    "fulfillment_type": "pickup"
                },
                store_settings=self.store,
                points_to_redeem=500,
            )

        self.reward_account.refresh_from_db()

        self.assertEqual(
            self.reward_account.points_balance,
            800
        )

        self.assertEqual(
            Order.objects.filter(user=self.user).count(),
            0
        )

        self.assertTrue(
            CartItem.objects.filter(cart=self.cart).exists()
        )

    def test_checkout_rollback_restores_points(self):
        with patch(
            "orders.placement.CartItem.objects.filter",
            side_effect=RuntimeError("Simulated checkout failure"),
        ):
            with self.assertRaises(RuntimeError):
                place_order(
                    user=self.user,
                    fulfillment_fields={
                        "fulfillment_type": "pickup"
                    },
                    store_settings=self.store,
                    points_to_redeem=500,
                )

        self.reward_account.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.reward_account.points_balance,
            800
        )

        self.assertEqual(self.product.stock, 10)

        self.assertFalse(
            Order.objects.filter(user=self.user).exists()
        )
