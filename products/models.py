import uuid
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum, Max


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='products'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=100, blank=True, null=True,)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True)
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
            models.Index(fields=['name']),
        ]

    def clean(self):
        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError({'unit_price': 'Unit price cannot be negative.'})
        if self.quantity_on_hand is not None and self.quantity_on_hand < 0:
            raise ValidationError({'quantity_on_hand': 'Quantity on hand cannot be negative.'})

    def save(self, *args, **kwargs):
        # Normalize blank SKU to NULL — unique_together treats '' as a real,
        # duplicate-checkable value but skips the check entirely when the
        # field is None. Without this, every product left with an empty
        # SKU collides with every other empty-SKU product in the business.
        if not self.sku:
            self.sku = None
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def available_to_sell(self):
        return self.quantity_on_hand - self.quantity_reserved
    
    @property
    def total_sold(self):
        # Sum the quantity of all items in documents that are  'paid'
        from documents.models import DocumentItem
        return self.document_items.filter(
            document__status__in=['paid']
        ).aggregate(Sum('quantity'))['quantity__sum'] or 0

    @property
    def is_low_stock(self):
        if self.reorder_level is None:
            return False
        return self.quantity_on_hand < self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.sku})"
