from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Cart, CartItem
from .serializers import CartSerializer
from products.models import Product


class CartView(APIView):
    def get(self, request):
        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)


class AddToCartView(APIView):
    def post(self, request):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product
        )

        if created:
            item.quantity = quantity
        else:
            item.quantity += quantity

        item.save()

        return Response(
            {
                "message": "Item added to cart",
                "product": product.name,
                "quantity": item.quantity
            },
            status=status.HTTP_200_OK
        )


class RemoveFromCartView(APIView):
    def delete(self, request, item_id):
        try:
            item = CartItem.objects.get(
                id=item_id,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        item.delete()

        return Response(
            {"message": "Item removed from cart"},
            status=status.HTTP_204_NO_CONTENT
        )