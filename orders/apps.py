from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "orders"
    verbose_name = "Orders, pickup & delivery"

    def ready(self):
        from . import sms_receivers