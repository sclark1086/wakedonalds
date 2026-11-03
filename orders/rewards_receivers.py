
from django.dispatch import receiver

from .signals import order_status_changed
from .rewards import award_reward_points


@receiver(order_status_changed)
def reward_when_completed(sender, order, old_status, new_status, **kwargs):

    if new_status in ["completed", "delivered"]:
        award_reward_points(order)
