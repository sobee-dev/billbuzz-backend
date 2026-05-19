import uuid
from decimal import Decimal
from django.db import models


class Customer(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='customers'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    business_name = models.CharField(max_length=255, blank=True)
    payment_method_preference = models.CharField(max_length=20, default='cash')
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    outstanding_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['status']),
            models.Index(fields=['email']),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def lifetime_value(self):
        # Will aggregate paid documents once the Document model exists.
        # Returns 0 for now so the property is safe to call today.
        return Decimal('0.00')

    def __str__(self):
        return self.full_name or self.email or str(self.id)
