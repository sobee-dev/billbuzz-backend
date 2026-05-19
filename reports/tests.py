from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User
from business.models import Business, StaffMember
from documents.models import Document
from products.models import Product


DASHBOARD_URL = '/api/reports/dashboard/'


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


def make_document(business, doc_type, doc_status, payment_status, grand_total,
                  doc_date=None, created_by=None):
    today = timezone.localdate()
    return Document.objects.create(
        business=business,
        created_by=created_by,
        document_type=doc_type,
        document_number=f'DOC-{Document.objects.count() + 1}',
        document_date=doc_date or today,
        customer_name='Test Customer',
        subtotal=grand_total,
        tax_rate='0.0000',
        tax_amount='0.00',
        discount='0.00',
        grand_total=grand_total,
        status=doc_status,
        payment_status=payment_status,
    )


def make_product(business, unit_price, qty_on_hand, reorder_level=None):
    count = Product.objects.count()
    return Product.objects.create(
        business=business,
        name=f'Product {count}',
        sku=f'SKU-{count}',
        unit_price=unit_price,
        quantity_on_hand=qty_on_hand,
        reorder_level=reorder_level,
        is_active=True,
    )


class DashboardRevenueTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_this_month_revenue_is_correct(self):
        today = timezone.localdate()
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)

        # Should count — confirmed sales_invoice this month
        make_document(self.business, Document.DocumentType.SALES_INVOICE,
                      Document.Status.CONFIRMED, Document.PaymentStatus.UNPAID,
                      '200.00', doc_date=today)
        # Should count — delivered receipt this month
        make_document(self.business, Document.DocumentType.RECEIPT,
                      Document.Status.DELIVERED, Document.PaymentStatus.PAID,
                      '100.00', doc_date=today)
        # Should NOT count — draft status
        make_document(self.business, Document.DocumentType.SALES_INVOICE,
                      Document.Status.DRAFT, Document.PaymentStatus.UNPAID,
                      '500.00', doc_date=today)
        # Should NOT count — last month
        make_document(self.business, Document.DocumentType.SALES_INVOICE,
                      Document.Status.CONFIRMED, Document.PaymentStatus.PAID,
                      '999.00', doc_date=last_month)

        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(response.data['this_month_revenue'])), Decimal('300.00'))


class DashboardReceivablesTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_outstanding_receivables_is_correct(self):
        # Should count — unpaid
        make_document(self.business, Document.DocumentType.SALES_INVOICE,
                      Document.Status.CONFIRMED, Document.PaymentStatus.UNPAID,
                      '400.00')
        # Should count — partial
        make_document(self.business, Document.DocumentType.SALES_INVOICE,
                      Document.Status.CONFIRMED, Document.PaymentStatus.PARTIAL,
                      '150.00')
        # Should NOT count — already paid
        make_document(self.business, Document.DocumentType.RECEIPT,
                      Document.Status.DELIVERED, Document.PaymentStatus.PAID,
                      '250.00')

        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Decimal(str(response.data['outstanding_receivables'])), Decimal('550.00')
        )


class DashboardLowStockTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_low_stock_count_is_correct(self):
        # Low stock — qty below reorder level
        make_product(self.business, unit_price='10.00', qty_on_hand='2.000', reorder_level='5.000')
        make_product(self.business, unit_price='20.00', qty_on_hand='1.000', reorder_level='10.000')
        # Not low — qty above reorder level
        make_product(self.business, unit_price='30.00', qty_on_hand='50.000', reorder_level='5.000')
        # Not low — no reorder level set
        make_product(self.business, unit_price='5.00', qty_on_hand='0.000', reorder_level=None)

        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['low_stock_count'], 2)


class DashboardPermissionTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.staff_user = make_user('staff@test.com', role='staff')
        StaffMember.objects.create(
            user=self.staff_user, business=self.business, status='active'
        )

    def test_staff_gets_403(self):
        client = APIClient()
        client.force_authenticate(user=self.staff_user)
        response = client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
