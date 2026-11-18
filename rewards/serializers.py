from rest_framework import serializers

from .models import RewardOption, RewardsSettings


class RewardOptionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", default=None, read_only=True)
    available = serializers.BooleanField(source="is_available", read_only=True)

    class Meta:
        model = RewardOption
        fields = [
            "id", "name", "description", "kind", "points_cost",
            "product", "product_name", "discount_amount", "available",
        ]


class RewardsProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardsSettings
        fields = ["program_enabled", "points_per_dollar", "point_value", "minimum_redemption_points"]
