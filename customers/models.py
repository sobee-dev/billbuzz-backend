import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Sum

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
    full_name = models.CharField(max_length=100)
    
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    payment_method_preference = models.CharField(max_length=20, default='cash')
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    outstanding_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['status']),
            models.Index(fields=['email']),
        ]


    @property
    def lifetime_value(self):
        """
        Calculates the total value of all 'paid' documents.
        Returns 0.00 if no paid documents are found.
        """
        result = self.documents.filter(status='paid').aggregate(
            total=Sum('grand_total')
        )['total']
        
        return result or Decimal('0.00')

    def __str__(self):
        return self.full_name or self.email or str(self.id)
