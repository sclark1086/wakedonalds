from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import Product


@staff_member_required
def inventory_report(request):
    """
    Admin-only real-time inventory report.

    Displays current product stock levels directly from the Product table.
    """

    products = Product.objects.all().order_by("name")

    inventory = []

    for product in products:
        if product.stock == 0:
            status = "Out of Stock"
        elif product.stock <= 5:
            status = "Low Stock"
        else:
            status = "In Stock"

        inventory.append(
            {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "stock": product.stock,
                "status": status,
            }
        )

    return render(
        request,
        "products/inventory_report.html",
        {
            "inventory": inventory,
        },
    )