# apps/authentication/backends.py - Custom authentication backend
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

Customer = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows login with email or username.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by email or username
            user = Customer.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except Customer.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user
            Customer().set_password(password)
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None


# Update settings.py to include this backend
"""
Add to ecommerce/settings.py:

AUTHENTICATION_BACKENDS = [
    'apps.authentication.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]
"""