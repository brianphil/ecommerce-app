# apps/authentication/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, CustomerProfileViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'profiles', CustomerProfileViewSet, basename='customer-profile')

urlpatterns = [
    path('', include(router.urls)),
]