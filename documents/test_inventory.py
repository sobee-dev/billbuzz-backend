"""
Integration tests for the Document inventory state machine.

Covers every inventory transition and the /confirm/ API endpoint.
Uses Django TestCase for model tests and DRF APITestCase for HTTP tests.
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


# ─────────────── Model / state machine tests (TestCase) ───────────────────────

class SalesInvoiceConfirmReservesInventoryTest(TestCase):
    """Scenario 1: confirming a sales invoice increases quantity_reserved."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 10)

    def test_confirm_increases_quantity_reserved(self):
        self.doc.confirm()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_reserved, Decimal('10.000'))
        # on_hand is NOT changed at confirm for sales invoices
        self.assertEqual(self.product.quantity_on_hand, Decimal('50.000'))


class SalesInvoiceDeliverDeductsInventoryTest(TestCase):
    """Scenario 2: delivering a confirmed sales invoice deducts on_hand and releases reservation."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 10)
        self.doc.confirm()
        self.product.refresh_from_db()

    def test_deliver_deducts_on_hand_and_releases_reservation(self):
        self.doc.mark_delivered()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('40.000'))
        self.assertEqual(self.product.quantity_reserved, Decimal('0.000'))


class ReceiptConfirmDeductsImmediatelyTest(TestCase):
    """Scenario 3: confirming a receipt deducts on_hand immediately (no reservation)."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('30.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.RECEIPT, owner=self.owner
        )
        add_item(self.doc, self.product, 5)

    def test_confirm_deducts_on_hand_immediately(self):
        self.doc.confirm()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('25.000'))
        # No reservation for receipts
        self.assertEqual(self.product.quantity_reserved, Decimal('0.000'))


class PurchaseInvoiceDeliverAddsStockTest(TestCase):
    """Scenario 4: delivering a purchase invoice adds to on_hand."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('10.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.PURCHASE_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 20)
        self.doc.confirm()  # purchase confirm has no inventory effect

    def test_deliver_adds_to_on_hand(self):
        self.doc.mark_delivered()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('30.000'))


class CancelConfirmedSalesInvoiceReversesReservationTest(TestCase):
    """Scenario 5: cancelling a confirmed sales invoice releases the reservation."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('50.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(self.doc, self.product, 15)
        self.doc.confirm()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_reserved, Decimal('15.000'))

    def test_cancel_reverses_reservation(self):
        self.doc.cancel()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_reserved, Decimal('0.000'))
        self.assertEqual(self.product.quantity_on_hand, Decimal('50.000'))
        self.assertEqual(self.doc.status, Document.Status.CANCELLED)


class DoubleConfirmRaisesValidationErrorTest(TestCase):
    """Scenario 6: confirming an already-confirmed document raises ValidationError."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        self.doc.confirm()

    def test_double_confirm_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.doc.confirm()


class InsufficientStockRaisesValidationErrorTest(TestCase):
    """Scenario 7: confirming a receipt when stock is insufficient raises ValidationError."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('3.000'))
        self.doc = make_document(
            self.business, Document.DocumentType.RECEIPT, owner=self.owner
        )
        add_item(self.doc, self.product, 10)  # 10 > 3 on_hand

    def test_insufficient_stock_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.doc.confirm()
        # Document must remain draft — no partial state changes
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.DRAFT)
        # Product stock must be untouched
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, Decimal('3.000'))


class InventoryTransactionRecordsTest(TestCase):
    """Scenario 8: correct InventoryTransaction records are created for each transition."""

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business, qty_on_hand=Decimal('100.000'))

    def _make_sales_doc(self, qty):
        doc = make_document(
            self.business, Document.DocumentType.SALES_INVOICE, owner=self.owner
        )
        add_item(doc, self.product, qty)
        return doc

    def test_sales_confirm_creates_sale_confirmed_transaction(self):
        doc = self._make_sales_doc(10)
        doc.confirm()
        tx = InventoryTransaction.objects.get(reference_document_id=doc.id)
        self.assertEqual(tx.transaction_type, InventoryTransaction.TransactionType.SALE_CONFIRMED)
        self.assertEqual(tx.quantity_change, Decimal('10.000'))

    def test_sales_deliver_creates_sale_delivered_transaction(self):
        doc = self._make_sales_doc(10)
        doc.confirm()
        doc.mark_delivered()
        txs = InventoryTransaction.objects.filter(
            reference_document_id=doc.id,
            transaction_type=InventoryTransaction.TransactionType.SALE_DELIVERED,
        )
        self.assertEqual(txs.count(), 1)
        self.assertEqual(txs.first().quantity_change, Decimal('-10.000'))

    def test_sales_cancel_creates_sale_cancelled_transaction(self):
        doc = self._make_sales_doc(10)
        doc.confirm()
        doc.cancel()
        tx = InventoryTransaction.objects.get(
            reference_document_id=doc.id,
            transaction_type=InventoryTransaction.TransactionType.SALE_CANCELLED,
        )
        self.assertEqual(tx.quantity_change, Decimal('-10.000'))

    def test_receipt_confirm_creates_sale_delivered_transaction(self):
        doc = make_document(self.business, Document.DocumentType.RECEIPT, owner=self.owner)
        add_item(doc, self.product, 7)
        doc.confirm()
        tx = InventoryTransaction.objects.get(reference_document_id=doc.id)
        self.assertEqual(tx.transaction_type, InventoryTransaction.TransactionType.SALE_DELIVERED)
        self.assertEqual(tx.quantity_change, Decimal('-7.000'))

    def test_purchase_deliver_creates_purchase_received_transaction(self):
        doc = make_document(
            self.business, Document.DocumentType.PURCHASE_INVOICE, owner=self.owner
        )
        add_item(doc, self.product, 25)
        doc.confirm()
        doc.mark_delivered()
        tx = InventoryTransaction.objects.get(
            reference_document_id=doc.id,
            transaction_type=InventoryTransaction.TransactionType.PURCHASE_RECEIVED,
        )
        self.assertEqual(tx.quantity_change, Decimal('25.000'))


# ─────────────────── API tests (APITestCase) ──────────────────────────────────

class ConfirmEndpointTest(APITestCase):
    """API tests for POST /api/documents/{id}/confirm/"""

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
        """
        Staff A's queryset is scoped to created_by=staff_a.
        Staff B's document is not in Staff A's queryset, so DRF
        returns 404 (the secure choice — does not reveal the document exists).
        """
        staff_a = make_user('staff_a@test.com', role='staff')
        staff_b = make_user('staff_b@test.com', role='staff')
        StaffMember.objects.create(user=staff_a, business=self.business, status='active')
        StaffMember.objects.create(user=staff_b, business=self.business, status='active')

        # Document created by staff_b
        doc_b = make_document(
            self.business, Document.DocumentType.SALES_INVOICE,
            owner=staff_b, number='STAFF-B-001',
        )

        self.client.force_authenticate(user=staff_a)
        response = self.client.post(self._url(doc_b.id))
        # 404 — not in staff_a's queryset (intentionally not 403 to avoid info leak)
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ])
        # Document must remain draft regardless
        doc_b.refresh_from_db()
        self.assertEqual(doc_b.status, Document.Status.DRAFT)
