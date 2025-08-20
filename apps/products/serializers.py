from rest_framework import serializers
from django.db.models import Avg
from .models import Category, Product, ProductImage, ProductReview


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model with hierarchy support.
    """
    children = serializers.SerializerMethodField()
    product_count = serializers.ReadOnlyField(source='get_product_count')
    average_price = serializers.ReadOnlyField(source='get_average_price')
    level = serializers.ReadOnlyField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent',
            'image', 'is_active', 'created_at', 'updated_at',
            'children', 'product_count', 'average_price', 'level'
        ]
        read_only_fields = ['created_at', 'updated_at', 'level']

    def get_children(self, obj):
        """Get immediate children of this category."""
        if hasattr(obj, 'prefetched_children'):
            children = obj.prefetched_children
        else:
            children = obj.get_children()
        
        return CategorySerializer(children, many=True, context=self.context).data


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Serializer for complete category tree structure.
    """
    ancestors = serializers.SerializerMethodField()
    descendants = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent',
            'level', 'ancestors', 'descendants', 'full_path'
        ]

    def get_ancestors(self, obj):
        """Get all ancestor categories."""
        ancestors = obj.get_ancestors()
        return [{'id': cat.id, 'name': cat.name, 'slug': cat.slug} for cat in ancestors]

    def get_descendants(self, obj):
        """Get all descendant categories."""
        descendants = obj.get_descendants()
        return [{'id': cat.id, 'name': cat.name, 'slug': cat.slug} for cat in descendants]

    def get_full_path(self, obj):
        """Get full category path."""
        ancestors = obj.get_ancestors(include_self=True)
        return ' > '.join([cat.name for cat in ancestors])


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Product Images.
    """
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']


class ProductReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for Product Reviews.
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    
    class Meta:
        model = ProductReview
        fields = [
            'id', 'rating', 'title', 'comment', 'customer_name',
            'is_approved', 'created_at', 'updated_at'
        ]
        read_only_fields = ['customer', 'is_approved', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for product listings.
    """
    primary_image = serializers.SerializerMethodField()
    main_category = serializers.CharField(source='get_main_category.name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'price',
            'sku', 'stock_quantity', 'is_featured', 'status',
            'primary_image', 'main_category', 'average_rating', 'review_count'
        ]

    def get_primary_image(self, obj):
        """Get primary product image."""
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
            return primary_image.image.url
        return None

    def get_average_rating(self, obj):
        """Get average rating for the product."""
        reviews = obj.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return None

    def get_review_count(self, obj):
        """Get count of approved reviews."""
        return obj.reviews.filter(is_approved=True).count()


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for individual product views.
    """
    categories = CategorySerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    category_hierarchies = serializers.ReadOnlyField(source='get_category_hierarchy')
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'categories', 'price', 'cost_price', 'sku', 'barcode',
            'weight', 'dimensions', 'stock_quantity', 'minimum_stock',
            'status', 'is_featured', 'meta_title', 'meta_description',
            'created_at', 'updated_at', 'images', 'reviews',
            'category_hierarchies', 'average_rating', 'review_count',
            'is_in_stock', 'is_low_stock'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'is_in_stock', 'is_low_stock'
        ]

    def get_average_rating(self, obj):
        """Get average rating for the product."""
        reviews = obj.reviews.filter(is_approved=True)
        if reviews.exists():
            return round(reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'], 1)
        return None

    def get_review_count(self, obj):
        """Get count of approved reviews."""
        return obj.reviews.filter(is_approved=True).count()


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating products with category assignment.
    """
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'price', 'cost_price', 'sku', 'barcode', 'weight',
            'dimensions', 'stock_quantity', 'minimum_stock',
            'status', 'is_featured', 'meta_title', 'meta_description',
            'category_ids', 'images', 'uploaded_images'
        ]

    def validate_category_ids(self, value):
        """Validate that all category IDs exist and are active."""
        if not value:
            raise serializers.ValidationError("At least one category is required.")
        
        categories = Category.objects.filter(id__in=value, is_active=True)
        if len(categories) != len(value):
            raise serializers.ValidationError("One or more categories are invalid or inactive.")
        
        return value

    def validate_sku(self, value):
        """Validate SKU uniqueness."""
        instance = getattr(self, 'instance', None)
        if Product.objects.filter(sku=value).exclude(id=instance.id if instance else None).exists():
            raise serializers.ValidationError("Product with this SKU already exists.")
        return value

    def create(self, validated_data):
        """Create product with categories and images."""
        category_ids = validated_data.pop('category_ids')
        uploaded_images = validated_data.pop('uploaded_images', [])
        
        product = Product.objects.create(**validated_data)
        
        # Assign categories
        categories = Category.objects.filter(id__in=category_ids)
        product.categories.set(categories)
        
        # Create images
        for i, image in enumerate(uploaded_images):
            ProductImage.objects.create(
                product=product,
                image=image,
                is_primary=(i == 0),  # First image is primary
                order=i
            )
        
        return product

    def update(self, instance, validated_data):
        """Update product with categories and images."""
        category_ids = validated_data.pop('category_ids', None)
        uploaded_images = validated_data.pop('uploaded_images', [])
        
        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update categories if provided
        if category_ids is not None:
            categories = Category.objects.filter(id__in=category_ids)
            instance.categories.set(categories)
        
        # Add new images if provided
        if uploaded_images:
            for i, image in enumerate(uploaded_images):
                order = instance.images.count() + i
                ProductImage.objects.create(
                    product=instance,
                    image=image,
                    order=order
                )
        
        return instance


class CategoryStatsSerializer(serializers.Serializer):
    """
    Serializer for category statistics including average price.
    """
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    category_slug = serializers.CharField()
    product_count = serializers.IntegerField()
    average_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_stock = serializers.IntegerField()