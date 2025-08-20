from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from mptt.models import MPTTModel, TreeForeignKey
from decimal import Decimal


class Category(MPTTModel):
    """
    Hierarchical category model using MPTT for efficient tree operations.
    Supports arbitrary depth category hierarchy.
    """
    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('parent category')
    )
    image = models.ImageField(
        _('category image'),
        upload_to='categories/',
        blank=True,
        null=True
    )
    is_active = models.BooleanField(_('is active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        db_table = 'product_categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/categories/{self.slug}/"

    def get_all_products(self):
        """Get all products in this category and its descendants."""
        descendant_categories = self.get_descendants(include_self=True)
        return Product.objects.filter(categories__in=descendant_categories).distinct()

    def get_product_count(self):
        """Get count of products in this category and its descendants."""
        return self.get_all_products().count()

    def get_average_price(self):
        """Get average price of products in this category and its descendants."""
        products = self.get_all_products()
        if products.exists():
            prices = products.aggregate(avg_price=models.Avg('price'))
            return prices['avg_price'] or Decimal('0.00')
        return Decimal('0.00')


class Product(models.Model):
    """
    Product model with support for multiple categories and variants.
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('discontinued', _('Discontinued')),
    ]

    name = models.CharField(_('name'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True)
    description = models.TextField(_('description'))
    short_description = models.CharField(
        _('short description'), 
        max_length=300, 
        blank=True
    )
    categories = models.ManyToManyField(
        Category,
        related_name='products',
        verbose_name=_('categories')
    )
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cost_price = models.DecimalField(
        _('cost price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True
    )
    sku = models.CharField(
        _('SKU'),
        max_length=100,
        unique=True,
        help_text=_('Stock Keeping Unit')
    )
    barcode = models.CharField(
        _('barcode'), 
        max_length=100, 
        blank=True, 
        unique=True, 
        null=True
    )
    weight = models.DecimalField(
        _('weight (kg)'),
        max_digits=8,
        decimal_places=3,
        blank=True,
        null=True
    )
    dimensions = models.CharField(
        _('dimensions (L x W x H)'),
        max_length=100,
        blank=True,
        help_text=_('Format: Length x Width x Height in cm')
    )
    stock_quantity = models.PositiveIntegerField(
        _('stock quantity'),
        default=0
    )
    minimum_stock = models.PositiveIntegerField(
        _('minimum stock level'),
        default=0
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    is_featured = models.BooleanField(_('is featured'), default=False)
    meta_title = models.CharField(_('meta title'), max_length=60, blank=True)
    meta_description = models.CharField(
        _('meta description'), 
        max_length=160, 
        blank=True
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['sku']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/products/{self.slug}/"

    @property
    def is_in_stock(self):
        """Check if product is in stock."""
        return self.stock_quantity > 0

    @property
    def is_low_stock(self):
        """Check if product stock is below minimum level."""
        return self.stock_quantity <= self.minimum_stock

    def get_main_category(self):
        """Get the first category (main category) of the product."""
        return self.categories.first()

    def get_category_hierarchy(self):
        """Get all category hierarchies this product belongs to."""
        categories = []
        for category in self.categories.all():
            ancestors = category.get_ancestors(include_self=True)
            categories.append(' > '.join([cat.name for cat in ancestors]))
        return categories

    def reduce_stock(self, quantity):
        """Reduce stock quantity by specified amount."""
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            self.save(update_fields=['stock_quantity'])
            return True
        return False

    def increase_stock(self, quantity):
        """Increase stock quantity by specified amount."""
        self.stock_quantity += quantity
        self.save(update_fields=['stock_quantity'])


class ProductImage(models.Model):
    """
    Product images with support for multiple images per product.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        _('product image'),
        upload_to='products/'
    )
    alt_text = models.CharField(
        _('alt text'),
        max_length=100,
        blank=True,
        help_text=_('Alternative text for accessibility')
    )
    is_primary = models.BooleanField(_('is primary'), default=False)
    order = models.PositiveIntegerField(_('display order'), default=0)

    class Meta:
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')
        db_table = 'product_images'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.product.name} - Image {self.id}"

    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, 
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductReview(models.Model):
    """
    Product reviews and ratings from customers.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    customer = models.ForeignKey(
        'authentication.Customer',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(_('review title'), max_length=100)
    comment = models.TextField(_('comment'))
    is_approved = models.BooleanField(_('is approved'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Product Review')
        verbose_name_plural = _('Product Reviews')
        db_table = 'product_reviews'
        unique_together = ['product', 'customer']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.rating} stars by {self.customer.get_full_name()}"