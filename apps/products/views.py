# Updated apps/products/views.py - Allow public read access
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Min, Max, Sum, Q, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Category, Product, ProductReview
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer, 
    ProductCreateSerializer, ProductReviewSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product categories with hierarchy support.
    Public read access, authentication required for write operations.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_permissions(self):
        """
        Allow public read access, require authentication for write operations.
        """
        if self.action in ['list', 'retrieve', 'tree', 'average_price']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter categories based on query parameters."""
        queryset = super().get_queryset()
        
        # Filter by parent category
        parent = self.request.query_params.get('parent')
        if parent:
            if parent == 'root':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent__slug=parent)
        
        # Filter by level
        level = self.request.query_params.get('level')
        if level:
            try:
                queryset = queryset.filter(level=int(level))
            except ValueError:
                pass
                
        return queryset

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get complete category tree structure."""
        root_categories = Category.objects.filter(parent__isnull=True, is_active=True)
        serializer = CategorySerializer(root_categories, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def average_price(self, request, slug=None):
        """Get average product price for a specific category."""
        category = self.get_object()
        include_descendants = request.query_params.get('include_descendants', 'true').lower() == 'true'
        
        if include_descendants:
            products = category.get_all_products().filter(status='active')
        else:
            products = category.products.filter(status='active')
        
        if products.exists():
            avg_price = products.aggregate(avg_price=Avg('price'))['avg_price']
            return Response({
                'category': category.name,
                'average_price': round(float(avg_price or 0), 2),
                'product_count': products.count(),
                'include_descendants': include_descendants
            })
        else:
            return Response({
                'category': category.name,
                'average_price': 0,
                'product_count': 0,
                'include_descendants': include_descendants
            })


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing products.
    Public read access, authentication required for write operations.
    """
    queryset = Product.objects.filter(status='active')  # Only show active products publicly
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'created_at', 'stock_quantity']
    ordering = ['-created_at']
    
    filterset_fields = {
        'categories': ['exact', 'in'],
        'price': ['gte', 'lte', 'exact'],
        'stock_quantity': ['gte', 'lte', 'exact'],
        'is_featured': ['exact'],
    }

    def get_permissions(self):
        """
        Allow public read access, require authentication for write operations.
        """
        if self.action in ['list', 'retrieve', 'featured', 'search']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ProductListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        else:
            return ProductDetailSerializer

    def get_queryset(self):
        """Filter products based on query parameters."""
        queryset = super().get_queryset()
        
        # Filter by category (including descendants)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug, is_active=True)
                # Get all descendant categories
                descendant_categories = category.get_descendants(include_self=True)
                queryset = queryset.filter(categories__in=descendant_categories).distinct()
            except Category.DoesNotExist:
                queryset = queryset.none()
        
        # Filter by stock status
        stock_status = self.request.query_params.get('stock_status')
        if stock_status == 'in_stock':
            queryset = queryset.filter(stock_quantity__gt=0)
        elif stock_status == 'out_of_stock':
            queryset = queryset.filter(stock_quantity=0)
        elif stock_status == 'low_stock':
            queryset = queryset.filter(stock_quantity__lte=F('minimum_stock'))
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
                
        return queryset.select_related().prefetch_related('categories', 'images', 'reviews')

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products."""
        featured_products = self.get_queryset().filter(is_featured=True)
        page = self.paginate_queryset(featured_products)
        
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(featured_products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced product search."""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({'results': []})
        
        # Search across multiple fields
        queryset = self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(sku__icontains=query) |
            Q(categories__name__icontains=query)
        ).distinct()
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(queryset, many=True, context={'request': request})
        return Response({'results': serializer.data})


class ProductReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product reviews.
    Public read access, authentication required for write operations.
    """
    serializer_class = ProductReviewSerializer
    
    def get_permissions(self):
        """
        Allow public read access, require authentication for write operations.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter reviews by product if specified."""
        queryset = ProductReview.objects.filter(is_approved=True)
        
        product_id = self.request.query_params.get('product')
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except ValueError:
                pass
            
        return queryset.select_related('customer', 'product').order_by('-created_at')

    def perform_create(self, serializer):
        """Set the customer as the current user."""
        serializer.save(customer=self.request.user)