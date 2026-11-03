from django import forms
from django.contrib import admin

from products.models import Product

from .models import RewardOption, RewardsSettings


@admin.register(RewardsSettings)
class RewardsSettingsAdmin(admin.ModelAdmin):
    """One row only: admins edit it, but can't add a second or delete it."""

    list_display = (
        "__str__", "program_enabled", "points_per_dollar", "point_value",
        "minimum_redemption_points", "updated_at",
    )

    def has_add_permission(self, request):
        return not RewardsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class ProductChoiceField(forms.ModelChoiceField):
    """Show menu items by name and price instead of 'Product object (1)'."""

    def label_from_instance(self, obj):
        return f"{obj.name} (${obj.price})"


@admin.register(RewardOption)
class RewardOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "points_cost", "product_name", "discount_amount", "active", "sort_order")
    list_editable = ("points_cost", "active", "sort_order")
    list_filter = ("kind", "active")
    search_fields = ("name", "description")

    @admin.display(description="Product")
    def product_name(self, obj):
        return obj.product.name if obj.product else "—"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.order_by("name")
            kwargs["form_class"] = ProductChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
