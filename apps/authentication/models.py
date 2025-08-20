from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Customer(AbstractUser):
    """
    Extended User model for customers with additional fields
    """
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(
        _('phone number'), 
        max_length=15, 
        blank=True,
        help_text=_('Phone number for SMS notifications')
    )
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    address = models.TextField(_('address'), blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True)
    country = models.CharField(_('country'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    is_verified = models.BooleanField(_('is verified'), default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = _('Customer')
        verbose_name_plural = _('Customers')
        db_table = 'customers'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_full_name(self):
        """Return the full name of the customer."""
        return f"{self.first_name} {self.last_name}".strip()

    def has_complete_profile(self):
        """Check if customer has completed their profile."""
        return all([
            self.first_name,
            self.last_name,
            self.email,
            self.phone_number,
            self.address
        ])


class CustomerProfile(models.Model):
    """
    Additional profile information for customers
    """
    customer = models.OneToOneField(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    avatar = models.ImageField(
        _('avatar'), 
        upload_to='avatars/', 
        blank=True, 
        null=True
    )
    bio = models.TextField(_('bio'), blank=True, max_length=500)
    newsletter_subscription = models.BooleanField(
        _('newsletter subscription'), 
        default=False
    )
    sms_notifications = models.BooleanField(
        _('SMS notifications'), 
        default=True
    )
    email_notifications = models.BooleanField(
        _('email notifications'), 
        default=True
    )
    preferred_language = models.CharField(
        _('preferred language'),
        max_length=10,
        choices=[
            ('en', _('English')),
            ('sw', _('Swahili')),
        ],
        default='en'
    )

    class Meta:
        verbose_name = _('Customer Profile')
        verbose_name_plural = _('Customer Profiles')
        db_table = 'customer_profiles'

    def __str__(self):
        return f"{self.customer.get_full_name()}'s Profile"