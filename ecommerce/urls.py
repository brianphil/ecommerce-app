from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# Import ViewSets
from apps.authentication.views import CustomerViewSet, CustomerProfileViewSet
from apps.products.views import CategoryViewSet, ProductViewSet, ProductReviewViewSet
from apps.orders.views import OrderViewSet, CartViewSet

# Schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="E-commerce Backend API",
        default_version='v1',
        description="""
        Comprehensive e-commerce backend API with hierarchical product categories,
        order management, authentication via OpenID Connect, and notification services.
        
        ## Features:
        - **Authentication**: OpenID Connect integration for secure customer login
        - **Products**: Hierarchical category management with arbitrary depth
        - **Orders**: Complete order lifecycle with status tracking
        - **Notifications**: SMS (Africa's Talking) and Email notifications
        - **Cart**: Shopping cart management
        - **Reviews**: Product rating and review system
        
        ## Authentication:
        Use the /auth/customers/login/ endpoint to get an access token,
        then include it in the Authorization header: `Bearer <token>`
        """,
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="admin@ecommerce.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# Create API router
router = DefaultRouter()

# Register ViewSets
router.register(r'auth/customers', CustomerViewSet, basename='customer')
router.register(r'auth/profiles', CustomerProfileViewSet, basename='customer-profile')
router.register(r'products/categories', CategoryViewSet, basename='category')
router.register(r'products/products', ProductViewSet, basename='product')
router.register(r'products/reviews', ProductReviewViewSet, basename='product-review')
router.register(r'orders/orders', OrderViewSet, basename='order')
router.register(r'orders/cart', CartViewSet, basename='cart')

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # OAuth2 endpoints
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    
    # API endpoints
    path('api/v1/', include(router.urls)),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # Health check endpoint
    path('health/', include('apps.core.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'