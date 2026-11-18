"""
Admin-only API so the web and mobile admin screens can read and change
thresholds (CFD2: "thresholds can be changed at any time").
"""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from products.models import Product

from .serializers import InventoryThresholdSerializer
from .services import threshold_for


def _all_thresholds():
    # Make sure every product has a row, then return them all.
    for product in Product.objects.filter(inventory_threshold__isnull=True):
        threshold_for(product)
    from .models import InventoryThreshold
    return InventoryThreshold.objects.select_related("product")


@api_view(["GET"])
@permission_classes([IsAdminUser])
def threshold_list(request):
    """All items with stock, thresholds and status. ?low=true for low stock only."""
    thresholds = list(_all_thresholds())
    if request.query_params.get("low", "").lower() in ("1", "true", "yes"):
        thresholds = [t for t in thresholds if t.is_low]
    return Response(InventoryThresholdSerializer(thresholds, many=True).data)


@api_view(["GET", "PATCH", "PUT"])
@permission_classes([IsAdminUser])
def threshold_detail(request, product_id):
    """Read or change one item's minimum/maximum levels."""
    product = get_object_or_404(Product, pk=product_id)
    threshold = threshold_for(product)
    if request.method == "GET":
        return Response(InventoryThresholdSerializer(threshold).data)

    serializer = InventoryThresholdSerializer(
        threshold, data=request.data, partial=request.method == "PATCH"
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()  # post_save re-checks stock against the new levels
    threshold.refresh_from_db()
    return Response(InventoryThresholdSerializer(threshold).data)
