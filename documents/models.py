import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Document(models.Model):

    class DocumentType(models.TextChoices):
        PURCHASE_INVOICE = 'purchase_invoice', 'Purchase Invoice'
        PROFORMA_INVOICE = 'proforma_invoice', 'Proforma Invoice'
        SALES_INVOICE    = 'sales_invoice',    'Sales Invoice'
        RECEIPT          = 'receipt',          'Receipt'

    class Status(models.TextChoices):
        DRAFT     = 'draft',      'Draft'
        CONFIRMED = 'confirmed',  'Confirmed'
        DELIVERED = 'delivered',  'Delivered'
        CANCELLED = 'cancelled',  'Cancelled'

    class PaymentStatus(models.TextChoices):
        UNPAID         = 'unpaid',          'Unpaid'
        PARTIAL        = 'partial',         'Partial'
        PAID           = 'paid',            'Paid'
        OVERPAID       = 'overpaid',        'Overpaid'

    class SyncStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SYNCED  = 'synced',  'Synced'
        ERROR   = 'error',   'Error'
        DELETED = 'deleted', 'Deleted'

    # ── Identity ──────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_documents',
    )

    # ── Classification ────────────────────────────────────────────────────────
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    document_number = models.CharField(max_length=50)
    document_date   = models.DateField()

    # ── Denormalised contact info (snapshot at time of creation) ──────────────
    customer_name  = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)

    # ── Supplier info (purchase invoices) ─────────────────────────────────────
    supplier_name = models.CharField(max_length=255, blank=True)

    # ── Financials ────────────────────────────────────────────────────────────
    subtotal    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_rate    = models.DecimalField(max_digits=5,  decimal_places=4, default=Decimal('0.1500'))
    tax_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # ── Payment ───────────────────────────────────────────────────────────────
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_at     = models.DateTimeField(null=True, blank=True)

    # ── Delivery ──────────────────────────────────────────────────────────────
    is_delivered  = models.BooleanField(default=False)
    delivered_at  = models.DateTimeField(null=True, blank=True)

    # ── Sync & soft-delete ────────────────────────────────────────────────────
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['business', 'document_number', 'document_type']]
        ordering = ['-document_date', '-created_at']
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['document_type']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['sync_status']),
            models.Index(fields=['-document_date']),
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.sync_status = self.SyncStatus.DELETED
        self.save(update_fields=['deleted_at', 'sync_status', 'updated_at'])

    def mark_paid(self):
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['payment_status', 'paid_at', 'updated_at'])

    # ── Inventory state machine ───────────────────────────────────────────────

    def _inventory_items(self):
        """Items that have a linked catalog product (inventory-tracked)."""
        return self.items.filter(product__isnull=False).select_related('product')

    @transaction.atomic
    def confirm(self):
        from inventory.models import InventoryTransaction

        if self.status != self.Status.DRAFT:
            raise ValidationError(
                f"Cannot confirm a document that is already '{self.status}'."
            )

        if self.document_type == self.DocumentType.RECEIPT:
            # Check stock for all linked products before touching anything.
            for item in self._inventory_items():
                if item.product.quantity_on_hand < item.quantity:
                    raise ValidationError(
                        f"Insufficient stock for '{item.product.name}'. "
                        f"Available: {item.product.quantity_on_hand}, "
                        f"Required: {item.quantity}."
                    )
            # Deduct immediately — receipts have no reservation step.
            for item in self._inventory_items():
                item.product.quantity_on_hand -= item.quantity
                item.product.save(update_fields=['quantity_on_hand', 'updated_at'])
                InventoryTransaction.objects.create(
                    business=self.business,
                    product=item.product,
                    quantity_change=-item.quantity,
                    transaction_type=InventoryTransaction.TransactionType.SALE_DELIVERED,
                    reference_document_id=self.id,
                    initiated_by=self.created_by,
                )

        elif self.document_type == self.DocumentType.SALES_INVOICE:
            # Reserve inventory — actual deduction happens on deliver().
            for item in self._inventory_items():
                item.product.quantity_reserved += item.quantity
                item.product.save(update_fields=['quantity_reserved', 'updated_at'])
                InventoryTransaction.objects.create(
                    business=self.business,
                    product=item.product,
                    quantity_change=item.quantity,
                    transaction_type=InventoryTransaction.TransactionType.SALE_CONFIRMED,
                    reference_document_id=self.id,
                    initiated_by=self.created_by,
                )

        # Purchase invoices and proforma invoices: no inventory change at confirm.

        self.status = self.Status.CONFIRMED
        self.save(update_fields=['status', 'updated_at'])

    @transaction.atomic
    def mark_delivered(self):
        from inventory.models import InventoryTransaction

        if self.document_type == self.DocumentType.SALES_INVOICE:
            # Deduct on_hand and release the reservation made at confirm().
            for item in self._inventory_items():
                item.product.quantity_on_hand -= item.quantity
                item.product.quantity_reserved -= item.quantity
                item.product.save(
                    update_fields=['quantity_on_hand', 'quantity_reserved', 'updated_at']
                )
                InventoryTransaction.objects.create(
                    business=self.business,
                    product=item.product,
                    quantity_change=-item.quantity,
                    transaction_type=InventoryTransaction.TransactionType.SALE_DELIVERED,
                    reference_document_id=self.id,
                    initiated_by=self.created_by,
                )

        elif self.document_type == self.DocumentType.PURCHASE_INVOICE:
            # Add received stock to on_hand.
            for item in self._inventory_items():
                item.product.quantity_on_hand += item.quantity
                item.product.save(update_fields=['quantity_on_hand', 'updated_at'])
                InventoryTransaction.objects.create(
                    business=self.business,
                    product=item.product,
                    quantity_change=item.quantity,
                    transaction_type=InventoryTransaction.TransactionType.PURCHASE_RECEIVED,
                    reference_document_id=self.id,
                    initiated_by=self.created_by,
                )

        self.is_delivered = True
        self.delivered_at = timezone.now()
        self.status = self.Status.DELIVERED
        self.save(update_fields=['is_delivered', 'delivered_at', 'status', 'updated_at'])

    @transaction.atomic
    def cancel(self):
        from inventory.models import InventoryTransaction

        if self.status == self.Status.CANCELLED:
            raise ValidationError('Document is already cancelled.')

        # Only confirmed sales invoices have reserved stock to release.
        if (self.status == self.Status.CONFIRMED
                and self.document_type == self.DocumentType.SALES_INVOICE):
            for item in self._inventory_items():
                item.product.quantity_reserved -= item.quantity
                item.product.save(update_fields=['quantity_reserved', 'updated_at'])
                InventoryTransaction.objects.create(
                    business=self.business,
                    product=item.product,
                    quantity_change=-item.quantity,
                    transaction_type=InventoryTransaction.TransactionType.SALE_CANCELLED,
                    reference_document_id=self.id,
                    initiated_by=self.created_by,
                )

        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def __str__(self):
        return f"{self.get_document_type_display()} #{self.document_number}"


class DocumentItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_items',
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        indexes = [models.Index(fields=['document'])]

    def save(self, *args, **kwargs):
        if not self.total:
            self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} × {self.quantity}"
