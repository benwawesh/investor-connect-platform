import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.cache import cache


class PlatformSettings(models.Model):
    """
    Singleton model for platform-wide settings.
    Only one instance should exist.
    """
    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(1.00)],
        help_text="Registration fee in KES (minimum 1.00)"
    )
    subscription_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(1.00)],
        help_text="Monthly subscription fee in KES (minimum 1.00)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only one settings instance can be active"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return f"Platform Settings (Registration: KES {self.registration_fee}, Subscription: KES {self.subscription_fee})"

    def save(self, *args, **kwargs):
        """Ensure only one active settings instance exists"""
        if self.is_active:
            # Deactivate all other instances
            PlatformSettings.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
        # Clear cache when settings are updated
        cache.delete('platform_settings')

    @classmethod
    def get_settings(cls):
        """Get active settings with caching"""
        settings = cache.get('platform_settings')
        if settings is None:
            settings = cls.objects.filter(is_active=True).first()
            if not settings:
                # Create default settings if none exist
                settings = cls.objects.create(
                    registration_fee=1.00,
                    subscription_fee=100.00,
                    is_active=True
                )
            cache.set('platform_settings', settings, 3600)  # Cache for 1 hour
        return settings

    @classmethod
    def get_registration_fee(cls):
        """Quick method to get just the registration fee"""
        return cls.get_settings().registration_fee

    @classmethod
    def get_subscription_fee(cls):
        """Quick method to get just the subscription fee"""
        return cls.get_settings().subscription_fee


class SubscriptionPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    TRANSACTION_TYPES = [
        ('REGISTRATION', 'Registration Fee'),
        ('SUBSCRIPTION', 'Monthly Subscription'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True  # Allow null for registration payments before user creation
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # M-Pesa specific fields
    phone_number = models.CharField(max_length=15)
    mpesa_transaction_id = models.CharField(max_length=200, blank=True)
    mpesa_receipt_number = models.CharField(max_length=200, blank=True)
    checkout_request_id = models.CharField(max_length=200, blank=True)

    # Additional fields for STK push implementation
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='SUBSCRIPTION')
    account_reference = models.CharField(max_length=50, blank=True)
    transaction_desc = models.CharField(max_length=100, blank=True)
    failure_reason = models.TextField(blank=True)

    # Pre-registration data (for registration payments before user creation)
    temp_email = models.EmailField(blank=True, help_text="Email for registration before user creation")
    temp_username = models.CharField(max_length=150, blank=True,
                                     help_text="Username for registration before user creation")
    temp_password = models.CharField(max_length=128, blank=True, null=True,
                                     help_text="Temporary password for registration before user creation")
    temp_user_type = models.CharField(max_length=20, blank=True,
                                      help_text="User type for registration before user creation")

    payment_date = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['status', 'transaction_type']),
            models.Index(fields=['payment_date']),
        ]

    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.transaction_type} - KES {self.amount} ({self.status})"
        else:
            return f"{self.temp_username} - {self.transaction_type} - KES {self.amount} ({self.status})"

    def get_display_name(self):
        """Get display name for the payment (user or temp_username)"""
        return self.user.username if self.user else self.temp_username

    def is_registration_payment(self):
        """Check if this is a registration payment"""
        return self.transaction_type == 'REGISTRATION'

    def is_completed(self):
        """Check if payment is completed"""
        return self.status == 'completed'

    def mark_as_completed(self, receipt_number=None):
        """Mark payment as completed with optional receipt number"""
        self.status = 'completed'
        if receipt_number:
            self.mpesa_receipt_number = receipt_number
        self.save()

    def mark_as_failed(self, reason=None):
        """Mark payment as failed with optional reason"""
        self.status = 'failed'
        if reason:
            self.failure_reason = reason
        self.save()
