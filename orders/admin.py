from django.contrib import admin

from .models import DeliveryZone, FulfillmentSettings, Order


@admin.register(FulfillmentSettings)
class FulfillmentSettingsAdmin(admin.ModelAdmin):
    """One row only: admins edit it, but can't add a second or delete it."""

    list_display = ("__str__", "pickup_enabled", "delivery_enabled", "delivery_fee", "tax_rate", "updated_at")

    def has_add_permission(self, request):
        return not FulfillmentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("zip_code", "active")
    list_editable = ("active",)
    search_fields = ("zip_code",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "fulfillment_type", "status", "total_price", "delivery_zip", "created_at")
    list_filter = ("fulfillment_type", "status")
    search_fields = ("id", "contact_phone", "delivery_street", "delivery_zip")
    readonly_fields = ("created_at", "updated_at")
