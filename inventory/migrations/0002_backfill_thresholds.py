from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    """Give every existing product default thresholds and flag the ones that
    are already low. No emails here; the admin list shows them."""
    Product = apps.get_model("products", "Product")
    InventoryThreshold = apps.get_model("inventory", "InventoryThreshold")
    now = timezone.now()
    for product in Product.objects.all():
        threshold, _ = InventoryThreshold.objects.get_or_create(product=product)
        if product.stock < threshold.min_level:
            threshold.low_stock_flag = True
            threshold.flagged_at = now
            threshold.save(update_fields=["low_stock_flag", "flagged_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        ("products", "0001_initial"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
