from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import Customer, CustomerProfile


class CustomerProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for customer profile information.
    """
    class Meta:
        model = CustomerProfile
        fields = [
            'avatar', 'bio', 'newsletter_subscription',
            'sms_notifications', 'email_notifications', 'preferred_language'
        ]


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for customer information.
    """
    profile = CustomerProfileSerializer(read_only=True)
    full_name = serializers.ReadOnlyField(source='get_full_name')
    has_complete_profile = serializers.ReadOnlyField()

    class Meta:
        model = Customer
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'date_of_birth', 'address', 'city', 'country',
            'is_verified', 'created_at', 'updated_at', 'profile',
            'full_name', 'has_complete_profile'
        ]
        read_only_fields = ['id', 'username', 'is_verified', 'created_at', 'updated_at']

    def validate_email(self, value):
        """Validate email uniqueness."""
        instance = getattr(self, 'instance', None)
        if Customer.objects.filter(email=value).exclude(id=instance.id if instance else None).exists():
            raise serializers.ValidationError("A customer with this email already exists.")
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        if value and not value.startswith('+'):
            # Add country code for Kenya if not present
            if value.startswith('0'):
                value = '+254' + value[1:]
            elif value.startswith('7') or value.startswith('1'):
                value = '+254' + value
        return value


class CustomerRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for customer registration.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Customer
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone_number', 'password', 'password_confirm'
        ]

    def validate(self, data):
        """Validate password confirmation."""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def validate_email(self, value):
        """Validate email uniqueness."""
        if Customer.objects.filter(email=value).exists():
            raise serializers.ValidationError("A customer with this email already exists.")
        return value

    def validate_username(self, value):
        """Validate username uniqueness."""
        if Customer.objects.filter(username=value).exists():
            raise serializers.ValidationError("A customer with this username already exists.")
        return value

    def validate_phone_number(self, value):
        """Validate and format phone number."""
        if value and not value.startswith('+'):
            # Add country code for Kenya if not present
            if value.startswith('0'):
                value = '+254' + value[1:]
            elif value.startswith('7') or value.startswith('1'):
                value = '+254' + value
        return value

    def create(self, validated_data):
        """Create customer with hashed password."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        customer = Customer.objects.create_user(
            password=password,
            **validated_data
        )
        return customer


class CustomerLoginSerializer(serializers.Serializer):
    """
    Serializer for customer login.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        """Validate login credentials."""
        email = data.get('email')
        password = data.get('password')

        if email and password:
            # Check if customer exists
            try:
                customer = Customer.objects.get(email=email)
                if not customer.is_active:
                    raise serializers.ValidationError("Customer account is disabled.")
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Invalid email or password.")

            # Authenticate with email as username
            customer = authenticate(username=email, password=password)
            if not customer:
                raise serializers.ValidationError("Invalid email or password.")
        else:
            raise serializers.ValidationError("Email and password are required.")

        return data


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing customer password.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        """Validate current password."""
        customer = self.context['request'].user
        if not customer.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        """Validate new password confirmation."""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError("New passwords do not match.")
        return data


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate that customer with email exists."""
        try:
            Customer.objects.get(email=value, is_active=True)
        except Customer.DoesNotExist:
            raise serializers.ValidationError("No active customer found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.
    """
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, data):
        """Validate new password confirmation."""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return data