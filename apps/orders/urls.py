# apps/orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CartViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'cart', CartViewSet, basename='cart')

urlpatterns = [
    path('', include(router.urls)),
]