from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Order, Cart, CartItem
from apps.products.models import Product
from .serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderCreateSerializer,
    OrderUpdateSerializer, CartSerializer, CartItemSerializer, AddToCartSerializer
)

# Import the simplified notification function
from apps.notifications.sms import send_order_confirmation_sms
from apps.notifications.email import send_order_notification_email, send_customer_order_confirmation_email


def send_order_notifications(order_id):
    """
    Send notifications when an order is placed.
    Simplified version without Celery for Windows development.
    """
    try:
        order = Order.objects.select_related('customer').prefetch_related(
            'items__product'
        ).get(id=order_id)
        
        # Prepare order data
        order_data = {
            'order_number': order.order_number,
            'customer_id': order.customer.id,
            'subtotal': str(order.subtotal),
            'tax_amount': str(order.tax_amount),
            'shipping_cost': str(order.shipping_cost),
            'total_amount': str(order.total_amount),
            'status': order.status,
            'billing_first_name': order.billing_first_name,
            'billing_last_name': order.billing_last_name,
            'billing_email': order.billing_email,
            'billing_phone': order.billing_phone,
            'billing_address': order.billing_address,
            'billing_city': order.billing_city,
            'billing_country': order.billing_country,
            'items': []
        }
        
        # Add order items
        for item in order.items.all():
            order_data['items'].append({
                'product_name': item.product_name,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price)
            })
        
        # Send SMS notification (mock)
        if order.customer.phone_number:
            sms_result = send_order_confirmation_sms(
                phone_number=order.customer.phone_number,
                order_number=order.order_number,
                total_amount=str(order.total_amount)
            )
            print(f"SMS Result: {sms_result}")
        
        # Send email notifications (console)
        send_customer_order_confirmation_email(order_data, order.customer.email)
        send_order_notification_email(order_data, 'admin@localhost')
        
        print(f"Order notifications processed for order {order.order_number}")
        
    except Exception as e:
        print(f"Error sending notifications for order {order_id}: {str(e)}")


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customer orders.
    
    Provides endpoints for:
    - Creating orders from cart or direct items
    - Viewing order history
    - Updating order status
    - Order tracking
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    ordering_fields = ['created_at', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return orders for the current user."""
        return Order.objects.filter(customer=self.request.user).select_related(
            'customer'
        ).prefetch_related('items__product', 'status_history')

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return OrderListSerializer
        elif self.action == 'create':
            return OrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        else:
            return OrderDetailSerializer

    @swagger_auto_schema(
        operation_description="Create a new order from cart or provided items",
        request_body=OrderCreateSerializer,
        responses={201: OrderDetailSerializer}
    )
    def create(self, request, *args, **kwargs):
        """Create a new order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = serializer.save()
            
            # Send notifications immediately (no Celery for Windows)
            send_order_notifications(order.id)
            
            response_serializer = OrderDetailSerializer(order, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description="Cancel an order (if eligible)",
        responses={200: "Order cancelled successfully"}
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order if it's eligible for cancellation."""
        order = self.get_object()
        
        if not order.can_be_cancelled:
            return Response(
                {'error': 'Order cannot be cancelled at this stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Restore stock for all items
            for item in order.items.all():
                item.product.increase_stock(item.quantity)
            
            # Update order status
            order.status = 'cancelled'
            order.save()
            
            # Create status history
            from .models import OrderStatusHistory
            OrderStatusHistory.objects.create(
                order=order,
                status='cancelled',
                comment='Order cancelled by customer',
                created_by=request.user
            )
        
        return Response({'message': 'Order cancelled successfully'})

    @swagger_auto_schema(
        operation_description="Get order tracking information",
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'order_number': openapi.Schema(type=openapi.TYPE_STRING),
                'status': openapi.Schema(type=openapi.TYPE_STRING),
                'tracking_number': openapi.Schema(type=openapi.TYPE_STRING),
                'status_history': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'status_display': openapi.Schema(type=openapi.TYPE_STRING),
                            'comment': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING)
                        }
                    )
                )
            }
        )}
    )
    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        """Get order tracking information."""
        order = self.get_object()
        
        tracking_info = {
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.get_status_display(),
            'tracking_number': order.tracking_number,
            'created_at': order.created_at,
            'confirmed_at': order.confirmed_at,
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'status_history': [
                {
                    'status': history.status,
                    'status_display': history.get_status_display(),
                    'comment': history.comment,
                    'created_at': history.created_at
                }
                for history in order.status_history.all()
            ]
        }
        
        return Response(tracking_info)


class CartViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing shopping cart.
    
    Provides endpoints for:
    - Viewing cart contents
    - Adding/removing items
    - Updating quantities
    - Clearing cart
    """
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return cart for the current user."""
        return Cart.objects.filter(customer=self.request.user).prefetch_related(
            'items__product'
        )

    def get_object(self):
        """Get or create cart for the current user."""
        cart, created = Cart.objects.get_or_create(customer=self.request.user)
        return cart

    def list(self, request):
        """Get current user's cart."""
        cart = self.get_object()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Add item to cart",
        request_body=AddToCartSerializer,
        responses={200: CartSerializer}
    )
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Add an item to the cart."""
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart = self.get_object()
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']
        
        try:
            product = Product.objects.get(id=product_id, status='active')
            
            # Check if item already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': quantity}
            )
            
            if not created:
                # Update quantity if item already exists
                new_quantity = cart_item.quantity + quantity
                
                # Validate against stock
                if new_quantity > product.stock_quantity:
                    return Response(
                        {'error': f'Only {product.stock_quantity} items available in stock'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cart_item.quantity = new_quantity
                cart_item.save()
            
            cart_serializer = CartSerializer(cart, context={'request': request})
            return Response(cart_serializer.data)
            
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found or inactive'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description="Remove item from cart",
        manual_parameters=[
            openapi.Parameter(
                'product_id',
                openapi.IN_QUERY,
                description="Product ID to remove",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ]
    )
    @action(detail=False, methods=['delete'])
    def remove_item(self, request):
        """Remove an item from the cart."""
        product_id = request.query_params.get('product_id')
        
        if not product_id:
            return Response(
                {'error': 'product_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart = self.get_object()
        
        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            cart_item.delete()
            
            cart_serializer = CartSerializer(cart, context={'request': request})
            return Response(cart_serializer.data)
            
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Item not found in cart'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description="Update item quantity in cart",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1)
            },
            required=['product_id', 'quantity']
        )
    )
    @action(detail=False, methods=['patch'])
    def update_quantity(self, request):
        """Update quantity of an item in the cart."""
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity')
        
        if not product_id or not quantity:
            return Response(
                {'error': 'product_id and quantity are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if quantity < 1:
            return Response(
                {'error': 'Quantity must be at least 1'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart = self.get_object()
        
        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
            
            # Validate against stock
            if quantity > cart_item.product.stock_quantity:
                return Response(
                    {'error': f'Only {cart_item.product.stock_quantity} items available in stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            cart_item.quantity = quantity
            cart_item.save()
            
            cart_serializer = CartSerializer(cart, context={'request': request})
            return Response(cart_serializer.data)
            
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Item not found in cart'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description="Clear all items from cart"
    )
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all items from the cart."""
        cart = self.get_object()
        cart.clear()
        
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response(cart_serializer.data)