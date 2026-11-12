from rest_framework import serializers

from .models import InventoryThreshold


class InventoryThresholdSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    stock = serializers.IntegerField(source="product.stock", read_only=True)
    is_low = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    reorder_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryThreshold
        fields = [
            "product_id", "product_name", "stock", "min_level", "max_level",
            "is_low", "status", "reorder_quantity", "flagged_at", "updated_at",
        ]
        read_only_fields = ["flagged_at", "updated_at"]

    def validate(self, attrs):
        min_level = attrs.get("min_level", getattr(self.instance, "min_level", None))
        max_level = attrs.get("max_level", getattr(self.instance, "max_level", None))
        if min_level is not None and max_level is not None and min_level > max_level:
            raise serializers.ValidationError(
                {"min_level": "Minimum level can't be higher than the maximum level."}
            )
        return attrs
