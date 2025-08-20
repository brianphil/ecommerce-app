from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Min, Max, Sum, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Category, Product, ProductReview
from .serializers import (
    CategorySerializer, CategoryTreeSerializer, CategoryStatsSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer,
    ProductReviewSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product categories with hierarchy support.
    
    Provides endpoints for:
    - CRUD operations on categories
    - Category tree structure
    - Category statistics including average prices
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

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
            queryset = queryset.filter(level=int(level))
            
        return queryset

    @swagger_auto_schema(
        operation_description="Get category tree structure",
        responses={200: CategoryTreeSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get complete category tree structure."""
        root_categories = Category.objects.filter(parent__isnull=True, is_active=True)
        serializer = CategoryTreeSerializer(root_categories, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get category statistics including average product prices",
        manual_parameters=[
            openapi.Parameter(
                'include_descendants',
                openapi.IN_QUERY,
                description="Include descendant categories in calculations",
                type=openapi.TYPE_BOOLEAN,
                default=True
            )
        ],
        responses={200: CategoryStatsSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get statistics for all categories including average prices."""
        include_descendants = request.query_params.get('include_descendants', 'true').lower() == 'true'
        
        stats = []
        categories = Category.objects.filter(is_active=True)
        
        for category in categories:
            if include_descendants:
                # Include products from descendant categories
                products = category.get_all_products().filter(status='active')
            else:
                # Only direct products
                products = category.products.filter(status='active')
            
            if products.exists():
                price_stats = products.aggregate(
                    avg_price=Avg('price'),
                    min_price=Min('price'),
                    max_price=Max('price'),
                    total_stock=Sum('stock_quantity')
                )
                
                stats.append({
                    'category_id': category.id,
                    'category_name': category.name,
                    'category_slug': category.slug,
                    'product_count': products.count(),
                    'average_price': price_stats['avg_price'] or 0,
                    'min_price': price_stats['min_price'] or 0,
                    'max_price': price_stats['max_price'] or 0,
                    'total_stock': price_stats['total_stock'] or 0,
                })
        
        serializer = CategoryStatsSerializer(stats, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get average product price for a specific category",
        manual_parameters=[
            openapi.Parameter(
                'include_descendants',
                openapi.IN_QUERY,
                description="Include descendant categories in calculation",
                type=openapi.TYPE_BOOLEAN,
                default=True
            )
        ]
    )
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
                'average_price': round(float(avg_price), 2),
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
    
    Provides endpoints for:
    - CRUD operations on products
    - Product search and filtering
    - Bulk operations
    """
    queryset = Product.objects.filter(status__in=['active', 'inactive'])
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'created_at', 'stock_quantity']
    ordering = ['-created_at']
    
    filterset_fields = {
        'categories': ['exact', 'in'],
        'price': ['gte', 'lte', 'exact'],
        'stock_quantity': ['gte', 'lte', 'exact'],
        'status': ['exact', 'in'],
        'is_featured': ['exact'],
    }

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
            queryset = queryset.filter(stock_quantity__lte=models.F('minimum_stock'))
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
            
        return queryset.select_related().prefetch_related('categories', 'images', 'reviews')

    @swagger_auto_schema(
        operation_description="Bulk upload products with categories",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'products': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_OBJECT)
                )
            }
        )
    )
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create products."""
        products_data = request.data.get('products', [])
        
        if not products_data:
            return Response(
                {'error': 'No products data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_products = []
        errors = []
        
        for i, product_data in enumerate(products_data):
            serializer = ProductCreateSerializer(data=product_data)
            if serializer.is_valid():
                try:
                    product = serializer.save()
                    created_products.append(ProductListSerializer(product).data)
                except Exception as e:
                    errors.append(f"Product {i+1}: {str(e)}")
            else:
                errors.append(f"Product {i+1}: {serializer.errors}")
        
        response_data = {
            'created_count': len(created_products),
            'error_count': len(errors),
            'created_products': created_products
        }
        
        if errors:
            response_data['errors'] = errors
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="Get featured products"
    )
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

    @swagger_auto_schema(
        operation_description="Search products across multiple fields"
    )
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
    """
    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter reviews by product if specified."""
        queryset = ProductReview.objects.filter(is_approved=True)
        
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
            
        return queryset.select_related('customer', 'product').order_by('-created_at')

    def perform_create(self, serializer):
        """Set the customer as the current user."""
        serializer.save(customer=self.request.user)