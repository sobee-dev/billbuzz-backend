"""
Data migration: copy all Receipt rows into the Document table.

Forward:  Receipt → Document (document_type='receipt')
Reverse:  delete every Document row whose document_type='receipt'
          that was originally a Receipt (matched by id).
"""
from decimal import Decimal
from django.db import migrations


def copy_receipts_forward(apps, schema_editor):
    Receipt  = apps.get_model('receipts',  'Receipt')
    Document = apps.get_model('documents', 'Document')

    docs_to_create = []

    for receipt in Receipt.objects.select_related('business').iterator():
        is_paid = receipt.is_paid

        docs_to_create.append(Document(
            # ── Identity — keep the same UUID so FKs can follow ──────────────
            id=receipt.id,

            # ── Relations ─────────────────────────────────────────────────────
            business=receipt.business,
            customer=None,
            created_by=None,

            # ── Classification ────────────────────────────────────────────────
            document_type='receipt',
            document_number=receipt.receipt_number,
            document_date=receipt.receipt_date,
            status='confirmed' if is_paid else 'draft',

            # ── Denormalised contact snapshot ─────────────────────────────────
            customer_name=receipt.customer_name or '',
            customer_email=getattr(receipt, 'customer_email', '') or '',
            customer_phone=getattr(receipt, 'customer_phone', '') or '',
            supplier_name='',

            # ── Financials ────────────────────────────────────────────────────
            subtotal=receipt.subtotal,
            tax_rate=receipt.tax_rate,
            tax_amount=receipt.tax_amount,
            discount=receipt.discount,
            grand_total=receipt.grand_total,

            # ── Payment ───────────────────────────────────────────────────────
            payment_status='paid' if is_paid else 'unpaid',
            amount_paid=receipt.grand_total if is_paid else Decimal('0.00'),
            paid_at=receipt.paid_at,

            # ── Delivery (receipts are point-of-sale; treat as delivered) ─────
            is_delivered=is_paid,
            delivered_at=receipt.paid_at if is_paid else None,

            # ── Sync & audit ──────────────────────────────────────────────────
            sync_status=receipt.sync_status,
            deleted_at=receipt.deleted_at,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at,
        ))

    # bulk_create with ignore_conflicts=False so any duplicate UUID surfaces
    # immediately rather than silently corrupting data.
    Document.objects.bulk_create(docs_to_create, batch_size=500)


def copy_receipts_reverse(apps, schema_editor):
    """
    Remove every Document that was migrated from a Receipt.
    Matches on id (same UUID) and document_type to avoid deleting
    any manually created receipt-type Documents.
    """
    Receipt  = apps.get_model('receipts',  'Receipt')
    Document = apps.get_model('documents', 'Document')

    receipt_ids = Receipt.objects.values_list('id', flat=True)
    Document.objects.filter(
        id__in=receipt_ids,
        document_type='receipt',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        # Must run after both the Document table is created
        # and the latest Receipt migration is applied.
        ('documents', '0001_create_document_model'),
        ('receipts',  '0002_remove_receipt_receipts_server__4702da_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(
            copy_receipts_forward,
            reverse_code=copy_receipts_reverse,
        ),
    ]
