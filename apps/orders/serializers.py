from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem
from apps.products.models import Product
from apps.products.serializers import ProductListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order items.
    """
    product_details = ProductListSerializer(source='product', read_only=True)
    savings = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_details', 'product_name',
            'product_sku', 'unit_price', 'quantity', 'total_price', 'savings'
        ]
        read_only_fields = ['product_name', 'product_sku', 'unit_price', 'total_price']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for order status history.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'status', 'status_display', 'comment',
            'created_by_name', 'created_at'
        ]
        read_only_fields = ['created_by_name', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for order listings.
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'status', 'status_display',
            'payment_status', 'payment_status_display', 'total_amount',
            'item_count', 'created_at', 'updated_at'
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for individual order views.
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    full_billing_address = serializers.ReadOnlyField(source='get_full_billing_address')
    full_shipping_address = serializers.ReadOnlyField(source='get_full_shipping_address')

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer', 'customer_name', 'customer_email',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'subtotal', 'tax_amount', 'shipping_cost', 'discount_amount', 'total_amount',
            'billing_first_name', 'billing_last_name', 'billing_email', 'billing_phone',
            'billing_address', 'billing_city', 'billing_country',
            'shipping_first_name', 'shipping_last_name', 'shipping_phone',
            'shipping_address', 'shipping_city', 'shipping_country',
            'full_billing_address', 'full_shipping_address',
            'notes', 'tracking_number', 'items', 'status_history',
            'item_count', 'can_be_cancelled', 'is_paid',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for cart items.
    """
    product_details = ProductListSerializer(source='product', read_only=True)
    total_price = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_details', 'quantity',
            'total_price', 'is_available', 'added_at'
        ]

    def validate_quantity(self, value):
        """Validate quantity against stock."""
        if self.instance:
            product = self.instance.product
        else:
            product = self.initial_data.get('product')
            if isinstance(product, int):
                try:
                    product = Product.objects.get(id=product)
                except Product.DoesNotExist:
                    raise serializers.ValidationError("Invalid product.")
        
        if product and value > product.stock_quantity:
            raise serializers.ValidationError(
                f"Only {product.stock_quantity} items available in stock."
            )
        
        return value


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for shopping cart.
    """
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()
    total_amount = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = [
            'id', 'customer', 'items', 'item_count',
            'total_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['customer', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.Serializer):
    """
    Serializer for creating orders from cart or direct items.
    """
    items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="List of items with product_id and quantity"
    )
    use_cart = serializers.BooleanField(
        default=True,
        help_text="Create order from current cart items"
    )
    shipping_address = serializers.DictField(required=False)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, data):
        """Validate order creation data."""
        use_cart = data.get('use_cart', True)
        items = data.get('items', [])

        if not use_cart and not items:
            raise serializers.ValidationError(
                "Either use_cart must be True or items must be provided."
            )

        if not use_cart:
            # Validate items format
            for item in items:
                if 'product_id' not in item or 'quantity' not in item:
                    raise serializers.ValidationError(
                        "Each item must have product_id and quantity."
                    )
                
                try:
                    product = Product.objects.get(
                        id=item['product_id'],
                        status='active'
                    )
                    if item['quantity'] > product.stock_quantity:
                        raise serializers.ValidationError(
                            f"Product {product.name}: Only {product.stock_quantity} items available."
                        )
                except Product.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Product with ID {item['product_id']} not found or inactive."
                    )

        return data

    def create(self, validated_data):
        """Create order from validated data."""
        customer = self.context['request'].user
        use_cart = validated_data.get('use_cart', True)
        items_data = validated_data.get('items', [])
        shipping_address = validated_data.get('shipping_address', {})
        notes = validated_data.get('notes', '')

        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                customer=customer,
                notes=notes
            )

            # Handle shipping address if provided
            if shipping_address:
                for field, value in shipping_address.items():
                    if hasattr(order, f'shipping_{field}'):
                        setattr(order, f'shipping_{field}', value)

            if use_cart:
                # Create order from cart
                try:
                    cart = Cart.objects.get(customer=customer)
                    cart_items = cart.items.all()
                    
                    if not cart_items.exists():
                        raise serializers.ValidationError("Cart is empty.")
                    
                    # Create order items from cart
                    for cart_item in cart_items:
                        if not cart_item.is_available:
                            raise serializers.ValidationError(
                                f"Product {cart_item.product.name} is not available in requested quantity."
                            )
                        
                        OrderItem.objects.create(
                            order=order,
                            product=cart_item.product,
                            quantity=cart_item.quantity
                        )
                        
                        # Reduce stock
                        cart_item.product.reduce_stock(cart_item.quantity)
                    
                    # Clear cart
                    cart.clear()
                    
                except Cart.DoesNotExist:
                    raise serializers.ValidationError("Cart not found.")
            else:
                # Create order from provided items
                for item_data in items_data:
                    product = Product.objects.get(id=item_data['product_id'])
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item_data['quantity']
                    )
                    
                    # Reduce stock
                    product.reduce_stock(item_data['quantity'])

            # Recalculate order totals
            order.calculate_totals()
            order.save()

            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                status='pending',
                comment='Order created',
                created_by=customer
            )

        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating order status and details.
    """
    status_comment = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        write_only=True
    )

    class Meta:
        model = Order
        fields = [
            'status', 'payment_status', 'tracking_number',
            'notes', 'status_comment'
        ]

    def update(self, instance, validated_data):
        """Update order and create status history."""
        status_comment = validated_data.pop('status_comment', '')
        old_status = instance.status
        
        # Update order
        updated_order = super().update(instance, validated_data)
        
        # Create status history if status changed
        if 'status' in validated_data and validated_data['status'] != old_status:
            OrderStatusHistory.objects.create(
                order=updated_order,
                status=validated_data['status'],
                comment=status_comment or f'Status changed to {updated_order.get_status_display()}',
                created_by=self.context['request'].user
            )
            
            # Update timestamp fields based on status
            if validated_data['status'] == 'confirmed':
                updated_order.confirmed_at = timezone.now()
            elif validated_data['status'] == 'shipped':
                updated_order.shipped_at = timezone.now()
            elif validated_data['status'] == 'delivered':
                updated_order.delivered_at = timezone.now()
            
            updated_order.save()

        return updated_order


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for adding items to cart.
    """
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        """Validate product exists and is active."""
        try:
            product = Product.objects.get(id=value, status='active')
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive.")

    def validate(self, data):
        """Validate quantity against stock."""
        try:
            product = Product.objects.get(id=data['product_id'])
            if data['quantity'] > product.stock_quantity:
                raise serializers.ValidationError(
                    f"Only {product.stock_quantity} items available in stock."
                )
        except Product.DoesNotExist:
            pass  # Will be caught by product_id validation
        
        return data