from django.dispatch import receiver

from .models import Order
from .signals import order_status_changed
from .views import send_ready_sms


@receiver(order_status_changed)
def send_sms_when_ready(sender, order, old_status, new_status, **kwargs):
    if (
        old_status != new_status
        and new_status == Order.Status.READY_FOR_PICKUP
        and order.fulfillment_type == Order.FulfillmentType.PICKUP
    ):
        send_ready_sms(order)