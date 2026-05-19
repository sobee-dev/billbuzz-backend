import uuid
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='products'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    image_url = models.URLField(blank=True)
    quantity_on_hand = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0'))
    quantity_reserved = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0'))
    reorder_level = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['business', 'sku']]
        ordering = ['name']
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sku']),
        ]

    def clean(self):
        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError({'unit_price': 'Unit price cannot be negative.'})
        if self.quantity_on_hand is not None and self.quantity_on_hand < 0:
            raise ValidationError({'quantity_on_hand': 'Quantity on hand cannot be negative.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def available_to_sell(self):
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def is_low_stock(self):
        if self.reorder_level is None:
            return False
        return self.quantity_on_hand < self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.sku})"
