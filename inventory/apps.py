from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
    verbose_name = "Inventory thresholds"

    def ready(self):
        from . import signals  # noqa: F401  (connects the stock-check receivers)
