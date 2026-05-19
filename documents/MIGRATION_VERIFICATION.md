# Receipt → Document Migration Verification Guide

Run these steps whenever you apply `0002_copy_receipts_to_documents` on a new environment.

---

## Step 1 — Backup (production only, run BEFORE deploying)

```bash
pg_dump \
  --host=<DB_HOST> \
  --port=5432 \
  --username=<DB_USER> \
  --dbname=<DB_NAME> \
  --format=custom \
  --compress=9 \
  --file="backup_pre_document_migration_$(date +%Y%m%d_%H%M%S).dump"
```

If your DATABASE_URL is in `.env`:

```bash
pg_dump "$(grep DATABASE_URL .env | cut -d= -f2-)" \
  --format=custom \
  --compress=9 \
  --file="backup_pre_document_migration_$(date +%Y%m%d_%H%M%S).dump"
```

---

## Step 2 — Safe Local Test (run before touching production)

```bash
# Roll back to before the data migration
python manage.py migrate documents 0001_create_document_model

# Confirm the Document table is empty
python manage.py shell -c "from documents.models import Document; print(Document.objects.count())"

# Run the forward migration
python manage.py migrate documents 0002_copy_receipts_to_documents

# Count check — both numbers must match
python manage.py shell -c "
from receipts.models import Receipt
from documents.models import Document
r = Receipt.objects.count()
d = Document.objects.filter(document_type='receipt').count()
print(f'Receipts: {r}  |  Documents(receipt): {d}  |  Match: {r == d}')
"

# Test the reverse — confirms you can undo if production goes wrong
python manage.py migrate documents 0001_create_document_model
python manage.py shell -c "from documents.models import Document; print(Document.objects.count())"
# Expected: 0

# Re-apply forward for normal development
python manage.py migrate documents
```

---

## Step 3 — SQL Verification (run in psql after migration)

```sql
-- 1. Row counts must match
SELECT COUNT(*) FROM receipts_receipt;
SELECT COUNT(*) FROM documents_document
  WHERE document_type = 'receipt';

-- 2. Every receipt UUID exists in documents (must be 0)
SELECT COUNT(*) FROM receipts_receipt r
  LEFT JOIN documents_document d ON d.id = r.id
  WHERE d.id IS NULL;

-- 3. Financial fields are identical (must be 0)
SELECT COUNT(*) FROM receipts_receipt r
  JOIN documents_document d ON d.id = r.id
  WHERE r.grand_total <> d.grand_total
     OR r.subtotal    <> d.subtotal
     OR r.tax_amount  <> d.tax_amount
     OR r.discount    <> d.discount;

-- 4. Paid status mapped correctly (both must be 0)
SELECT COUNT(*) FROM receipts_receipt r
  JOIN documents_document d ON d.id = r.id
  WHERE r.is_paid = TRUE AND d.payment_status <> 'paid';

SELECT COUNT(*) FROM receipts_receipt r
  JOIN documents_document d ON d.id = r.id
  WHERE r.is_paid = FALSE AND d.payment_status <> 'unpaid';

-- 5. No orphaned documents (must be 0)
SELECT COUNT(*) FROM documents_document d
  LEFT JOIN receipts_receipt r ON r.id = d.id
  WHERE d.document_type = 'receipt'
    AND r.id IS NULL;
```

---

## Step 4 — Django Shell Verification (run after production migration)

```bash
python manage.py shell
```

```python
from receipts.models import Receipt
from documents.models import Document
from django.db.models import Q

# Count match
r_count = Receipt.objects.count()
d_count = Document.objects.filter(document_type='receipt').count()
print(f"Receipts: {r_count} | Docs: {d_count} | OK: {r_count == d_count}")

# Spot-check one record
r = Receipt.objects.first()
d = Document.objects.get(id=r.id)
print(d.document_number, d.document_type, d.payment_status)
print(d.grand_total == r.grand_total)   # True
print(d.business_id == r.business_id)  # True

# Confirm no contradictory payment states (must be 0)
bad = Document.objects.filter(
    document_type='receipt'
).filter(
    Q(payment_status='paid',   amount_paid=0) |
    Q(payment_status='unpaid', amount_paid__gt=0)
).count()
print(f"Bad payment mappings: {bad}")
```

---

## Expected Results Summary

| Check | Expected |
|---|---|
| Receipt count == Document(receipt) count | True |
| Receipts missing from documents | 0 |
| Financial field mismatches | 0 |
| Bad paid mapping | 0 |
| Bad unpaid mapping | 0 |
| Orphaned documents | 0 |
| Bad payment states | 0 |
