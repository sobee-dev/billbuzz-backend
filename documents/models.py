import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
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

    def mark_delivered(self):
        self.is_delivered = True
        self.delivered_at = timezone.now()
        self.status = self.Status.DELIVERED
        self.save(update_fields=['is_delivered', 'delivered_at', 'status', 'updated_at'])

    def __str__(self):
        return f"{self.get_document_type_display()} #{self.document_number}"
