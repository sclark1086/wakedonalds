from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Cart, CartItem
from .serializers import CartSerializer
from products.models import Product


class CartView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)
        if isinstance(quantity, bool) or isinstance(quantity, float):
            return Response(
                {"error": "quantity must be a whole number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "quantity must be a whole number"},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        try:
            item = CartItem.objects.get(
                cart=cart,
                product=product
            )
            new_quantity = item.quantity + quantity

        except CartItem.DoesNotExist:
            item = None
            new_quantity = quantity

        if new_quantity > product.stock:
            return Response(
                {"error": "Not enough stock available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if item is None:
            item = CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=quantity
            )
        else:
            item.quantity = new_quantity
            item.save()

        return Response(
            {
                "message": "Item added to cart",
                "product": product.name,
                "quantity": item.quantity
            },
            status=status.HTTP_200_OK
        )


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
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

        quantity = request.data.get("quantity")

        if quantity is None:
            return Response(
                {"error": "quantity is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if isinstance(quantity, bool) or isinstance(quantity, float):
            return Response(
                {"error": "quantity must be a whole number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "quantity must be a whole number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity < 1:
            return Response(
                {"error": "quantity must be at least 1"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity > item.product.stock:
            return Response(
                {"error": "Not enough stock available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.quantity = quantity
        item.save()

        return Response(
            {
                "message": "Cart item updated",
                "product": item.product.name,
                "quantity": item.quantity
            },
            status=status.HTTP_200_OK
        )

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



