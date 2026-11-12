"""
Threshold checks and low-stock alerts.

check_stock(product) is called automatically after every Product save
(orders taking stock, admin stock edits) and after every threshold change,
so the flag always matches the current stock (SRS BR2, real-time sync).
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import InventoryThreshold, LowStockAlert

logger = logging.getLogger(__name__)


def threshold_for(product):
    threshold, _ = InventoryThreshold.objects.get_or_create(product=product)
    return threshold


def check_stock(product):
    """
    Flag/unflag the product and send an alert the moment it drops below its
    minimum. Returns the LowStockAlert if a new one was raised, else None.
    """
    threshold = threshold_for(product)
    now = timezone.now()

    if product.stock < threshold.min_level:
        # Conditional update: only one caller can flip False -> True, so
        # two orders finishing together can't send two alerts.
        flipped = InventoryThreshold.objects.filter(
            pk=threshold.pk, low_stock_flag=False
        ).update(low_stock_flag=True, flagged_at=now)
        if not flipped:
            return None
        alert = LowStockAlert.objects.create(
            product=product,
            stock_at_alert=product.stock,
            min_level_at_alert=threshold.min_level,
        )
        transaction.on_commit(lambda: send_low_stock_email(alert.pk))
        return alert

    cleared = InventoryThreshold.objects.filter(
        pk=threshold.pk, low_stock_flag=True
    ).update(low_stock_flag=False, flagged_at=None)
    if cleared:
        LowStockAlert.objects.filter(product=product, resolved_at__isnull=True).update(
            resolved_at=now
        )
    return None


def alert_recipients():
    """LOW_STOCK_ALERT_EMAILS setting if set, otherwise every active staff email."""
    configured = getattr(settings, "LOW_STOCK_ALERT_EMAILS", None)
    if configured:
        return list(configured)
    return list(
        get_user_model()
        .objects.filter(is_staff=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def send_low_stock_email(alert_id):
    """Runs after the order/edit commits. A mail failure never breaks the order."""
    alert = LowStockAlert.objects.select_related("product").filter(pk=alert_id).first()
    if alert is None:
        return
    recipients = alert_recipients()
    if not recipients:
        logger.warning("Low stock on %s but no admin email to alert.", alert.product.name)
        return

    product = alert.product
    threshold = threshold_for(product)
    subject = f"Wakedonalds low stock: {product.name}"
    message = (
        f"{product.name} is low on inventory.\n\n"
        f"Current stock: {product.stock}\n"
        f"Minimum level: {threshold.min_level}\n"
        f"Maximum level: {threshold.max_level}\n"
        f"Suggested reorder: {threshold.reorder_quantity}\n\n"
        "Update stock or thresholds in the admin under Inventory thresholds."
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)
    except Exception:  # noqa: BLE001  (log and move on; the flag is still set)
        logger.exception("Could not send low stock email for %s", product.name)
        return
    LowStockAlert.objects.filter(pk=alert.pk).update(emailed_to=", ".join(recipients))


def stock_status(product):
    """'Out of Stock' / 'Low Stock' / 'In Stock' using the product's own minimum.
    The inventory report (REPORT1) can call this instead of a hard-coded cutoff."""
    return threshold_for(product).status


def low_stock_thresholds():
    return [t for t in InventoryThreshold.objects.select_related("product") if t.is_low]
