from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class Order(models.Model):
    """
    Customer orders with comprehensive tracking and status management.
    """
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('processing', _('Processing')),
        ('shipped', _('Shipped')),
        ('delivered', _('Delivered')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('paid', _('Paid')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
    ]

    # Order identification
    order_number = models.CharField(
        _('order number'),
        max_length=50,
        unique=True,
        editable=False
    )
    customer = models.ForeignKey(
        'authentication.Customer',
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name=_('customer')
    )
    
    # Order status and tracking
    status = models.CharField(
        _('order status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    
    # Pricing information
    subtotal = models.DecimalField(
        _('subtotal'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        _('tax amount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    shipping_cost = models.DecimalField(
        _('shipping cost'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        _('discount amount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        _('total amount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Customer information (snapshot at order time)
    billing_first_name = models.CharField(_('billing first name'), max_length=150)
    billing_last_name = models.CharField(_('billing last name'), max_length=150)
    billing_email = models.EmailField(_('billing email'))
    billing_phone = models.CharField(_('billing phone'), max_length=15)
    billing_address = models.TextField(_('billing address'))
    billing_city = models.CharField(_('billing city'), max_length=100)
    billing_country = models.CharField(_('billing country'), max_length=100)
    
    shipping_first_name = models.CharField(_('shipping first name'), max_length=150)
    shipping_last_name = models.CharField(_('shipping last name'), max_length=150)
    shipping_phone = models.CharField(_('shipping phone'), max_length=15)
    shipping_address = models.TextField(_('shipping address'))
    shipping_city = models.CharField(_('shipping city'), max_length=100)
    shipping_country = models.CharField(_('shipping country'), max_length=100)
    
    # Additional information
    notes = models.TextField(_('order notes'), blank=True)
    tracking_number = models.CharField(
        _('tracking number'),
        max_length=100,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    confirmed_at = models.DateTimeField(_('confirmed at'), null=True, blank=True)
    shipped_at = models.DateTimeField(_('shipped at'), null=True, blank=True)
    delivered_at = models.DateTimeField(_('delivered at'), null=True, blank=True)

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.get_full_name()}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Copy customer information if not already set
        if not self.billing_first_name:
            self.copy_customer_info()
            
        # Calculate totals
        self.calculate_totals()
        
        super().save(*args, **kwargs)

    def generate_order_number(self):
        """Generate unique order number."""
        import time
        timestamp = str(int(time.time()))
        random_part = str(uuid.uuid4())[:8].upper()
        return f"ORD-{timestamp}-{random_part}"

    def copy_customer_info(self):
        """Copy customer information to billing fields."""
        self.billing_first_name = self.customer.first_name
        self.billing_last_name = self.customer.last_name
        self.billing_email = self.customer.email
        self.billing_phone = self.customer.phone_number
        self.billing_address = self.customer.address
        self.billing_city = self.customer.city
        self.billing_country = self.customer.country
        
        # Copy to shipping if not different
        if not self.shipping_first_name:
            self.shipping_first_name = self.billing_first_name
            self.shipping_last_name = self.billing_last_name
            self.shipping_phone = self.billing_phone
            self.shipping_address = self.billing_address
            self.shipping_city = self.billing_city
            self.shipping_country = self.billing_country

    def calculate_totals(self):
        """Calculate order totals based on items."""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        
        # Simple tax calculation (16% VAT for Kenya)
        tax_rate = Decimal('0.16')
        self.tax_amount = self.subtotal * tax_rate
        
        # Calculate total
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount

    @property
    def item_count(self):
        """Get total number of items in the order."""
        return sum(item.quantity for item in self.items.all())

    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in ['pending', 'confirmed']

    @property
    def is_paid(self):
        """Check if order is paid."""
        return self.payment_status == 'paid'

    def get_full_billing_address(self):
        """Get formatted billing address."""
        return f"{self.billing_address}, {self.billing_city}, {self.billing_country}"

    def get_full_shipping_address(self):
        """Get formatted shipping address."""
        return f"{self.shipping_address}, {self.shipping_city}, {self.shipping_country}"


class OrderItem(models.Model):
    """
    Individual items within an order.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('order')
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name=_('product')
    )
    
    # Product information snapshot at order time
    product_name = models.CharField(_('product name'), max_length=200)
    product_sku = models.CharField(_('product SKU'), max_length=100)
    unit_price = models.DecimalField(
        _('unit price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        validators=[MinValueValidator(1)]
    )
    total_price = models.DecimalField(
        _('total price'),
        max_digits=10,
        decimal_places=2,
        editable=False
    )

    class Meta:
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')
        db_table = 'order_items'
        unique_together = ['order', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product_name} (Order: {self.order.order_number})"

    def save(self, *args, **kwargs):
        # Capture product information snapshot
        if not self.product_name:
            self.product_name = self.product.name
            self.product_sku = self.product.sku
            self.unit_price = self.product.price
            
        # Calculate total price
        self.total_price = self.unit_price * self.quantity
        
        super().save(*args, **kwargs)

    @property
    def savings(self):
        """Calculate savings if product price has changed."""
        current_price = self.product.price
        if current_price > self.unit_price:
            return (current_price - self.unit_price) * self.quantity
        return Decimal('0.00')


class OrderStatusHistory(models.Model):
    """
    Track order status changes for audit trail.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Order.STATUS_CHOICES
    )
    comment = models.TextField(_('comment'), blank=True)
    created_by = models.ForeignKey(
        'authentication.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('Order Status History')
        verbose_name_plural = _('Order Status Histories')
        db_table = 'order_status_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order.order_number} - {self.get_status_display()}"


class Cart(models.Model):
    """
    Shopping cart for customers before order placement.
    """
    customer = models.OneToOneField(
        'authentication.Customer',
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Shopping Cart')
        verbose_name_plural = _('Shopping Carts')
        db_table = 'shopping_carts'

    def __str__(self):
        return f"Cart for {self.customer.get_full_name()}"

    @property
    def item_count(self):
        """Get total number of items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        """Calculate total cart amount."""
        return sum(item.total_price for item in self.items.all())

    def clear(self):
        """Remove all items from cart."""
        self.items.all().delete()


class CartItem(models.Model):
    """
    Individual items in shopping cart.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        validators=[MinValueValidator(1)]
    )
    added_at = models.DateTimeField(_('added at'), auto_now_add=True)

    class Meta:
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        db_table = 'cart_items'
        unique_together = ['cart', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def total_price(self):
        """Calculate total price for this cart item."""
        return self.product.price * self.quantity

    @property
    def is_available(self):
        """Check if product is still available in requested quantity."""
        return self.product.stock_quantity >= self.quantity