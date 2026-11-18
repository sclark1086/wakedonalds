from django.utils.translation import gettext as _
from django.db import connection
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

from products.models import Product


@api_view(['GET'])
def health_check(request):
    """
    Basic health-check endpoint for the Wakedonalds backend.
    """
    db_status = "unknown"

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        db_status = "connected"

    except Exception as e:
        db_status = f"error: {e}"

    return Response({
        "status": "ok",
        "service": "wakedonalds-backend",
        "database": db_status,
    })


def menu_view(request):
    categories = {
        _("Burgers"): [
            {
                "name": _("Classic Burger"),
                "price": 5.99,
                "description": _(
                    "Beef patty with lettuce, tomato, "
                    "pickles, and house sauce."
                ),
            },
            {
                "name": _("Cheeseburger"),
                "price": 6.49,
                "description": _(
                    "Beef patty with American cheese, "
                    "lettuce, tomato, and pickles."
                ),
            },
        ],

        _("Sides"): [
            {
                "name": _("French Fries"),
                "price": 2.49,
                "description": _("Crispy golden fries."),
            },
            {
                "name": _("Onion Rings"),
                "price": 3.49,
                "description": _("Crispy battered onion rings."),
            },
        ],

        _("Drinks"): [
            {
                "name": _("Soft Drink"),
                "price": 1.99,
                "description": _("Choice of fountain drink."),
            },
            {
                "name": _("Iced Tea"),
                "price": 1.99,
                "description": _("Freshly brewed iced tea."),
            },
        ],

        _("Desserts"): [
            {
                "name": _("Apple Pie"),
                "price": 2.99,
                "description": _("Warm apple pie."),
            },
        ],
    }

    # Get the current products and their stock quantities
    # from the database.
    products = {
        product.name: product
        for product in Product.objects.all()
    }

    # Add availability information to each menu item.
    for items in categories.values():
        for item in items:
            product = products.get(item["name"])

            if product:
                item["product_id"] = product.id
                item["stock"] = product.stock
                item["available"] = product.stock > 0
            else:
                item["product_id"] = None
                item["stock"] = 0
                item["available"] = False

    return render(
        request,
        "menu.html",
        {
            "categories": categories,
        },
    )