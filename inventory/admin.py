from django.contrib import admin, messages
from django.utils.html import format_html

from .models import InventoryThreshold, LowStockAlert
from .services import check_stock


class LowStockFilter(admin.SimpleListFilter):
    title = "stock level"
    parameter_name = "level"

    def lookups(self, request, model_admin):
        return [("low", "Low stock"), ("ok", "In stock")]

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.filter(low_stock_flag=True)
        if self.value() == "ok":
            return queryset.filter(low_stock_flag=False)
        return queryset


@admin.register(InventoryThreshold)
class InventoryThresholdAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "current_stock",
        "min_level",
        "max_level",
        "stock_status",
        "reorder_quantity",
        "flagged_at",
    )
    list_editable = ("min_level", "max_level")
    list_filter = (LowStockFilter,)
    search_fields = ("product__name",)
    list_select_related = ("product",)
    readonly_fields = ("current_stock", "stock_status", "reorder_quantity", "flagged_at")
    actions = ["recheck"]

    def has_add_permission(self, request):
        return False  # one row per product is created automatically

    def get_readonly_fields(self, request, obj=None):
        return ("product",) + self.readonly_fields if obj else self.readonly_fields

    @admin.display(description="Stock")
    def current_stock(self, obj):
        return obj.product.stock

    @admin.display(description="Status")
    def stock_status(self, obj):
        colors = {"Out of Stock": "#b00020", "Low Stock": "#c77700", "In Stock": "#2e7d32"}
        return format_html(
            '<strong style="color:{}">{}</strong>', colors[obj.status], obj.status
        )

    @admin.display(description="Reorder qty")
    def reorder_quantity(self, obj):
        return obj.reorder_quantity

    @admin.action(description="Re-check stock against thresholds")
    def recheck(self, request, queryset):
        raised = sum(1 for t in queryset.select_related("product") if check_stock(t.product))
        self.message_user(request, f"Checked {queryset.count()} item(s); {raised} new alert(s).",
                          messages.INFO)

    def changelist_view(self, request, extra_context=None):
        low = InventoryThreshold.objects.filter(low_stock_flag=True).count()
        if low:
            self.message_user(request, f"{low} item(s) are below their minimum level.",
                              messages.WARNING)
        return super().changelist_view(request, extra_context)


@admin.register(LowStockAlert)
class LowStockAlertAdmin(admin.ModelAdmin):
    list_display = ("product", "stock_at_alert", "min_level_at_alert", "created_at",
                    "resolved_at", "emailed_to")
    list_filter = ("resolved_at",)
    search_fields = ("product__name",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
