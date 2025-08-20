from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from oauth2_provider.models import Application, AccessToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Customer, CustomerProfile
from .serializers import (
    CustomerSerializer, CustomerProfileSerializer, CustomerRegistrationSerializer,
    CustomerLoginSerializer, PasswordChangeSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for customer management with OpenID Connect integration.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's data."""
        return Customer.objects.filter(id=self.request.user.id)

    def get_object(self):
        """Return the current user."""
        return self.request.user

    @swagger_auto_schema(
        operation_description="Register a new customer",
        request_body=CustomerRegistrationSerializer,
        responses={201: CustomerSerializer}
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """Register a new customer."""
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        customer = serializer.save()
        
        # Create customer profile
        CustomerProfile.objects.create(customer=customer)
        
        # Return customer data
        customer_serializer = CustomerSerializer(customer)
        return Response(customer_serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="Customer login",
        request_body=CustomerLoginSerializer,
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access_token': openapi.Schema(type=openapi.TYPE_STRING),
                    'refresh_token': openapi.Schema(type=openapi.TYPE_STRING),
                    'token_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'expires_in': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'customer': CustomerSerializer
                }
            )
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """Customer login with OAuth2 token generation."""
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # Authenticate user
        customer = authenticate(request, username=email, password=password)
        
        if customer and customer.is_active:
            # Get or create OAuth2 application
            try:
                application = Application.objects.get(name='E-commerce API')
            except Application.DoesNotExist:
                application = Application.objects.create(
                    name='E-commerce API',
                    client_type=Application.CLIENT_CONFIDENTIAL,
                    authorization_grant_type=Application.GRANT_PASSWORD,
                )
            
            # Create access token
            from oauth2_provider.models import AccessToken, RefreshToken
            from datetime import timedelta
            from django.utils import timezone
            
            # Delete existing tokens
            AccessToken.objects.filter(user=customer, application=application).delete()
            RefreshToken.objects.filter(user=customer, application=application).delete()
            
            # Create new tokens
            access_token = AccessToken.objects.create(
                user=customer,
                application=application,
                token=AccessToken.generate_token(),
                expires=timezone.now() + timedelta(seconds=3600),
                scope='read write'
            )
            
            refresh_token = RefreshToken.objects.create(
                user=customer,
                application=application,
                token=RefreshToken.generate_token(),
                access_token=access_token
            )
            
            # Return token response
            customer_serializer = CustomerSerializer(customer)
            return Response({
                'access_token': access_token.token,
                'refresh_token': refresh_token.token,
                'token_type': 'Bearer',
                'expires_in': 3600,
                'scope': 'read write',
                'customer': customer_serializer.data
            })
        else:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @swagger_auto_schema(
        operation_description="Customer logout (revoke tokens)"
    )
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout customer by revoking tokens."""
        try:
            # Get current access token
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                access_token = AccessToken.objects.get(token=token)
                
                # Delete associated refresh token
                if hasattr(access_token, 'refresh_token'):
                    access_token.refresh_token.delete()
                
                # Delete access token
                access_token.delete()
                
                return Response({'message': 'Successfully logged out'})
            else:
                return Response(
                    {'error': 'No valid token provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except AccessToken.DoesNotExist:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description="Get current customer profile"
    )
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current customer profile."""
        serializer = CustomerSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update customer profile",
        request_body=CustomerSerializer
    )
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update customer profile."""
        serializer = CustomerSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Change customer password",
        request_body=PasswordChangeSerializer
    )
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change customer password."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        customer = request.user
        customer.set_password(serializer.validated_data['new_password'])
        customer.save()
        
        # Revoke all existing tokens
        AccessToken.objects.filter(user=customer).delete()
        
        return Response({'message': 'Password changed successfully'})

    @swagger_auto_schema(
        operation_description="Verify customer account",
        manual_parameters=[
            openapi.Parameter(
                'verification_code',
                openapi.IN_QUERY,
                description="Email verification code",
                type=openapi.TYPE_STRING,
                required=True
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def verify_email(self, request):
        """Verify customer email address."""
        verification_code = request.query_params.get('verification_code')
        
        if not verification_code:
            return Response(
                {'error': 'Verification code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # In a real implementation, you would verify the code against
        # a stored verification token
        customer = request.user
        customer.is_verified = True
        customer.save()
        
        return Response({'message': 'Email verified successfully'})


class CustomerProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customer profiles.
    """
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's profile."""
        return CustomerProfile.objects.filter(customer=self.request.user)

    def get_object(self):
        """Get or create customer profile."""
        profile, created = CustomerProfile.objects.get_or_create(
            customer=self.request.user
        )
        return profile

    def perform_create(self, serializer):
        """Set the customer to the current user."""
        serializer.save(customer=self.request.user)

    def list(self, request):
        """Get current customer profile."""
        profile = self.get_object()
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    def create(self, request):
        """Update or create customer profile."""
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)