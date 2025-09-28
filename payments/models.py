import uuid
from django.db import models
from django.conf import settings


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