"""
Data migration: convert any existing 'receipt' documents to 'sales_invoice'
before the RECEIPT choice is removed from Document.DocumentType.

Runs in two steps:
1. Forward: reclassify receipt → sales_invoice (preserves history).
2. Reverse: no-op — we cannot know which sales_invoices were originally receipts.
"""
from django.db import migrations


def reclassify_receipts(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    Document.objects.filter(document_type='receipt').update(document_type='sales_invoice')


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_add_documentitem_model'),
    ]

    operations = [
        migrations.RunPython(reclassify_receipts, migrations.RunPython.noop),
    ]
