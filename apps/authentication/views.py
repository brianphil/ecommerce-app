from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from oauth2_provider.models import Application, AccessToken, RefreshToken
from django.utils import timezone
from datetime import timedelta
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

    def get_permissions(self):
        """
        Allow public access for registration and login.
        """
        if self.action in ['register', 'login']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Return only the current user's data."""
        if self.request.user.is_authenticated:
            return Customer.objects.filter(id=self.request.user.id)
        return Customer.objects.none()

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
        
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            customer = serializer.save()
            
            # Create customer profile
            CustomerProfile.objects.get_or_create(customer=customer)
            
            # Return customer data without sensitive info
            customer_serializer = CustomerSerializer(customer)
            
            return Response({
                'message': 'Registration successful',
                'customer': customer_serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Registration failed: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

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
        
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            # Find customer by email
            try:
                customer = Customer.objects.get(email=email)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Invalid email or password'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check if customer is active
            if not customer.is_active:
                return Response(
                    {'error': 'Account is disabled'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Authenticate with email as username
            authenticated_user = authenticate(
                request=request,
                username=customer.username,  # Use username for authentication
                password=password
            )
            
            if not authenticated_user:
                # Try authenticating with email directly
                authenticated_user = authenticate(
                    request=request,
                    username=email,
                    password=password
                )
            
            if not authenticated_user:
                return Response(
                    {'error': 'Invalid email or password'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get or create OAuth2 application
            application, created = Application.objects.get_or_create(
                name='E-commerce API',
                defaults={
                    'client_type': Application.CLIENT_PUBLIC,
                    'authorization_grant_type': Application.GRANT_PASSWORD,
                }
            )
            
            # Delete existing tokens for this user
            AccessToken.objects.filter(user=authenticated_user, application=application).delete()
            RefreshToken.objects.filter(user=authenticated_user, application=application).delete()
            
            # Create new access token
            expires = timezone.now() + timedelta(seconds=3600)
            access_token = AccessToken.objects.create(
                user=authenticated_user,
                application=application,
                token=AccessToken.generate_token(),
                expires=expires,
                scope='read write'
            )
            
            # Create refresh token
            refresh_token = RefreshToken.objects.create(
                user=authenticated_user,
                application=application,
                token=RefreshToken.generate_token(),
                access_token=access_token
            )
            
            # Return token response
            customer_serializer = CustomerSerializer(authenticated_user)
            return Response({
                'access_token': access_token.token,
                'refresh_token': refresh_token.token,
                'token_type': 'Bearer',
                'expires_in': 3600,
                'scope': 'read write',
                'customer': customer_serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': f'Login failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
                try:
                    access_token = AccessToken.objects.get(token=token)
                    
                    # Delete associated refresh token
                    RefreshToken.objects.filter(access_token=access_token).delete()
                    
                    # Delete access token
                    access_token.delete()
                    
                    return Response({'message': 'Successfully logged out'})
                    
                except AccessToken.DoesNotExist:
                    return Response({'message': 'Token already invalid'})
            else:
                return Response(
                    {'error': 'No valid token provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Logout failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description="Get current customer profile"
    )
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current customer profile."""
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = CustomerSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update customer profile",
        request_body=CustomerSerializer
    )
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update customer profile."""
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
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
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
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
        operation_description="Test authentication",
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'user': CustomerSerializer
            }
        )}
    )
    @action(detail=False, methods=['get'])
    def test_auth(self, request):
        """Test endpoint to verify authentication is working."""
        if request.user.is_authenticated:
            return Response({
                'message': 'Authentication working',
                'user': CustomerSerializer(request.user).data
            })
        else:
            return Response({
                'message': 'Not authenticated'
            }, status=status.HTTP_401_UNAUTHORIZED)


class CustomerProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customer profiles.
    """
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's profile."""
        if self.request.user.is_authenticated:
            return CustomerProfile.objects.filter(customer=self.request.user)
        return CustomerProfile.objects.none()

    def get_object(self):
        """Get or create customer profile."""
        if not self.request.user.is_authenticated:
            return None
        
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
        if profile:
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        """Update or create customer profile."""
        profile = self.get_object()
        if profile:
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)