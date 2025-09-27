import uuid
from django.db import models
from django.conf import settings

# Remove these lines:
# from django.contrib.auth import get_user_model
# User = get_user_model()


class SubscriptionPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')  # Changed this line
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # M-Pesa specific fields
    phone_number = models.CharField(max_length=15)
    mpesa_transaction_id = models.CharField(max_length=200, blank=True)
    mpesa_receipt_number = models.CharField(max_length=200, blank=True)
    checkout_request_id = models.CharField(max_length=200, blank=True)

    payment_date = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.user.username} - KES {self.amount} ({self.status})"