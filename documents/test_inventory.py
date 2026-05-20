"""
Integration tests for manual inventory actions.

Covers:
  - POST /api/documents/{id}/deduct-inventory/  (sales invoices)
  - POST /api/documents/{id}/add-to-inventory/  (purchase invoices)
  - Document lifecycle (confirm / cancel / deliver) with no automatic inventory side-effects
  - Access control (unauthenticated, wrong document type)
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from business.models import Business, StaffMember
from documents.models import Document, DocumentItem
from inventory.models import InventoryTransaction
from products.models import Product


# ─────────────────────────── shared helpers ───────────────────────────────────

def make_user(email, role='owner'):
    return User.objects.create_user(email=email, password='testpass123', role=role)


def make_business(owner):
    return Business.objects.create(
        owner=owner,
        name='Test Business',
        address_one='1 Test St',
        phone='1234567890',
        email='biz@test.com',
        currency='$',
        selected_template_id='default',
        signature_type='none',
    )


def make_product(business, qty_on_hand=Decimal('100.000'), qty_reserved=Decimal('0.000')):
    count = Product.objects.count()
    return Product.objects.create(
        business=business,
        name=f'Product {count}',
        sku=f'SKU-{count}',
        unit_price=Decimal('10.00'),
        quantity_on_hand=qty_on_hand,
        quantity_reserved=qty_reserved,
    )


def make_document(business, doc_type, owner=None, number=None):
    count = Document.objects.count()
    return Document.objects.create(
        business=business,
        created_by=owner,
        document_type=doc_type,
        document_number=number or f'DOC-{count + 1}',
        document_date=date.today(),
        customer_name='Test Customer',
        grand_total=Decimal('0.00'),
    )


def add_item(document, product, quantity):
    qty = Decimal(str(quantity))
    return DocumentItem.objects.create(
        document=document,
        product=product,
        description=product.name,
        quantity=qty,
        unit_price=product.unit_price,
        total=qty * product.unit_price,
    )


# ─────────────── Model / lifecycle tests (TestCase) ───────────────────────────

class ConfirmDoesNotTouchInventoryTest(TestCase):
    """confirm() only changes status — no inventory side-effects."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 10)

    def test_confirm_leaves_inventory_unchanged(self):
        self.doc.confirm()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('50.000'))
        self.assertEqual(self.product.quantity_reserved, Decimal('0.000'))
        self.assertFalse(InventoryTransaction.objects.exists())

    def test_confirm_changes_status_to_confirmed(self):
        self.doc.confirm()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.CONFIRMED)


class DoubleConfirmRaisesValidationErrorTest(TestCase):
    """confirm() on an already-confirmed document must raise ValidationError."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        self.doc.confirm()

    def test_double_confirm_raises(self):
        with self.assertRaises(ValidationError):
            self.doc.confirm()


class DeliverDoesNotTouchInventoryTest(TestCase):
    """mark_delivered() only updates status/delivery fields — no inventory side-effects."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 10)
        self.doc.confirm()

    def test_deliver_leaves_inventory_unchanged(self):
        self.doc.mark_delivered()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('50.000'))
        self.assertFalse(InventoryTransaction.objects.exists())

    def test_deliver_marks_document_delivered(self):
        self.doc.mark_delivered()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.DELIVERED)
        self.assertTrue(self.doc.is_delivered)


class CancelDoesNotTouchInventoryTest(TestCase):
    """cancel() only changes status — no inventory side-effects."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 15)
        self.doc.confirm()

    def test_cancel_leaves_inventory_unchanged(self):
        self.doc.cancel()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('50.000'))
        self.assertFalse(InventoryTransaction.objects.exists())

    def test_cancel_changes_status(self):
        self.doc.cancel()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.CANCELLED)

    def test_double_cancel_raises(self):
        self.doc.cancel()
        with self.assertRaises(ValidationError):
            self.doc.cancel()


# ─────────────────── API tests (APITestCase) ──────────────────────────────────

class DeductInventoryEndpointTest(APITestCase):
    """POST /api/documents/{id}/deduct-inventory/"""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('100.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        self.item = add_item(self.doc, self.product, 20)
        self.doc.confirm()
        self.client.force_authenticate(user=self.owner)

    def _url(self, doc_id=None):
        return f'/api/documents/{doc_id or self.doc.id}/deduct-inventory/'

    def test_subtract_all_deducts_full_quantity(self):
        response = self.client.post(self._url(), {'subtract_all': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('80.000'))

    def test_subtract_all_creates_transaction_record(self):
        self.client.post(self._url(), {'subtract_all': True}, format='json')
        tx = InventoryTransaction.objects.get(reference_document_id=self.doc.id)
        self.assertEqual(tx.transaction_type, InventoryTransaction.TransactionType.SALE_DELIVERED)
        self.assertEqual(tx.quantity_change, Decimal('-20.000'))

    def test_partial_deduction_by_item(self):
        response = self.client.post(self._url(), {
            'items': [{'item_id': str(self.item.id), 'quantity': 7}]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('93.000'))

    def test_insufficient_stock_returns_400(self):
        # Set stock below what the item requires
        self.product.quantity_on_hand = Decimal('5.000')
        self.product.save(update_fields=['quantity_on_hand', 'updated_at'])

        response = self.client.post(self._url(), {'subtract_all': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Stock must remain untouched
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('5.000'))

    def test_missing_body_returns_400(self):
        response = self.client.post(self._url(), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self._url(), {'subtract_all': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_document_type_returns_400(self):
        purchase_doc = make_document(
            self.business, Document.DocumentType.PURCHASE_INVOICE,
            owner=self.owner, number='PO-001',
        )
        response = self.client.post(self._url(purchase_doc.id), {'subtract_all': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_item_id_returns_404(self):
        import uuid
        response = self.client.post(self._url(), {
            'items': [{'item_id': str(uuid.uuid4()), 'quantity': 5}]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AddToInventoryEndpointTest(APITestCase):
    """POST /api/documents/{id}/add-to-inventory/"""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('10.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.PURCHASE_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 25)
        self.doc.confirm()
        self.client.force_authenticate(user=self.owner)

    def _url(self, doc_id=None):
        return f'/api/documents/{doc_id or self.doc.id}/add-to-inventory/'

    def test_adds_all_items_to_stock(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('35.000'))

    def test_creates_purchase_received_transaction(self):
        self.client.post(self._url())
        tx = InventoryTransaction.objects.get(reference_document_id=self.doc.id)
        self.assertEqual(tx.transaction_type, InventoryTransaction.TransactionType.PURCHASE_RECEIVED)
        self.assertEqual(tx.quantity_change, Decimal('25.000'))

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_document_type_returns_400(self):
        sales_doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE,
            owner=self.owner, number='SI-001',
        )
        response = self.client.post(self._url(sales_doc.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ConfirmEndpointTest(APITestCase):
    """POST /api/documents/{id}/confirm/ — status only, no inventory."""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )

    def _url(self, doc_id=None):
        return f'/api/documents/{doc_id or self.doc.id}/confirm/'

    def test_authenticated_owner_confirm_returns_200(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.CONFIRMED)

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_cannot_confirm_another_staffs_document(self):
        staff_a = make_user('staff_a@test.com', role='staff')
        staff_b = make_user('staff_b@test.com', role='staff')
        StaffMember.objects.create(user=staff_a, business=self.business, status='active')
        StaffMember.objects.create(user=staff_b, business=self.business, status='active')

        doc_b = make_document(
            self.business, Document.DocumentType.SALES_INVOICE,
            owner=staff_b, number='STAFF-B-001',
        )

        self.client.force_authenticate(user=staff_a)
        response = self.client.post(self._url(doc_b.id))
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ])
        doc_b.refresh_from_db()
        self.assertEqual(doc_b.status, Document.Status.DRAFT)
