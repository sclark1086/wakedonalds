from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import Product

from .models import InventoryThreshold
from .services import check_stock


@receiver(post_save, sender=Product, dispatch_uid="inventory_product_saved")
def product_saved(sender, instance, raw=False, **kwargs):
    # Covers stock taken by Place Order and stock edited in the admin.
    # (QuerySet.update() skips signals; use save() when changing stock.)
    if not raw:
        check_stock(instance)


@receiver(post_save, sender=InventoryThreshold, dispatch_uid="inventory_threshold_saved")
def threshold_saved(sender, instance, raw=False, **kwargs):
    # Raising or lowering the minimum can flag/unflag an item right away.
    if not raw:
        check_stock(instance.product)
