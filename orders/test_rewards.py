
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import RewardAccount
from orders.models import Order
from orders.rewards import award_reward_points


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
