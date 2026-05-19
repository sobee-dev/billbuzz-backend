from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User
from business.models import Business, StaffMember
from products.models import Product
from documents.models import Document


def make_user(email, role='owner'):
    return User.objects.create_user(email=email, password='testpass123', role=role)


def make_business(owner):
    return Business.objects.create(
        owner=owner,
        name='Test Business',
        address_one='123 Main St',
        phone='1234567890',
        email='biz@test.com',
        currency='$',
        selected_template_id='default',
        signature_type='none',
    )


class StaffMemberModelTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.staff_user = make_user('staff@test.com', role='staff')

    def test_create_staff_member_successfully(self):
        staff = StaffMember.objects.create(
            user=self.staff_user,
            business=self.business,
            department='Sales',
            permission_level='full_access',
        )
        self.assertEqual(staff.user, self.staff_user)
        self.assertEqual(staff.business, self.business)
        self.assertEqual(staff.department, 'Sales')
        self.assertEqual(staff.permission_level, 'full_access')
        self.assertEqual(staff.status, 'active')

    def test_deactivate_staff_member(self):
        staff = StaffMember.objects.create(
            user=self.staff_user,
            business=self.business,
        )
        staff.status = 'inactive'
        staff.save()

        staff.refresh_from_db()
        self.assertEqual(staff.status, 'inactive')

    def test_unique_together_raises_integrity_error(self):
        StaffMember.objects.create(user=self.staff_user, business=self.business)
        with self.assertRaises(IntegrityError):
            StaffMember.objects.create(user=self.staff_user, business=self.business)


# ── Helpers shared by RBAC tests ─────────────────────────────────────────────

def make_product(business):
    return Product.objects.create(
        business=business,
        name='Widget',
        sku='WGT-001',
        unit_price='9.99',
    )


def make_document(business, created_by, number='DOC-001', doc_status=Document.Status.DRAFT):
    return Document.objects.create(
        business=business,
        created_by=created_by,
        document_type=Document.DocumentType.RECEIPT,
        document_number=number,
        document_date=date.today(),
        customer_name='Test Customer',
        subtotal='100.00',
        tax_rate='0.1500',
        tax_amount='15.00',
        discount='0.00',
        grand_total='115.00',
        status=doc_status,
    )


# ── RBAC tests ────────────────────────────────────────────────────────────────

class RBACDocumentFilterTest(TestCase):
    """Tests for role-based document visibility in DocumentViewSet."""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)

        self.staff_user = make_user('staff@test.com', role='staff')
        StaffMember.objects.create(user=self.staff_user, business=self.business, status='active')

        self.other_staff = make_user('other@test.com', role='staff')
        StaffMember.objects.create(user=self.other_staff, business=self.business, status='active')

        # Two docs: one created by staff, one by owner
        self.staff_doc  = make_document(self.business, self.staff_user, number='S-001')
        self.owner_doc  = make_document(self.business, self.owner,      number='O-001')

    def test_staff_sees_only_own_documents(self):
        client = APIClient()
        client.force_authenticate(user=self.staff_user)
        response = client.get('/api/documents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data['results']]
        self.assertIn(str(self.staff_doc.id), ids)
        self.assertNotIn(str(self.owner_doc.id), ids)

    def test_owner_sees_all_business_documents(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get('/api/documents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data['results']]
        self.assertIn(str(self.staff_doc.id), ids)
        self.assertIn(str(self.owner_doc.id), ids)


class RBACProductDeactivateTest(TestCase):
    """Staff cannot deactivate products — owner role required."""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)
        self.product = make_product(self.business)

        self.staff_user = make_user('staff@test.com', role='staff')
        StaffMember.objects.create(user=self.staff_user, business=self.business, status='active')

    def test_staff_gets_403_on_deactivate(self):
        client = APIClient()
        client.force_authenticate(user=self.staff_user)
        response = client.post(f'/api/products/{self.product.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StaffDashboardTest(TestCase):
    """Staff dashboard returns correct counts and revenue."""

    def setUp(self):
        self.owner = make_user('owner@test.com', role='owner')
        self.business = make_business(self.owner)

        self.staff_user = make_user('staff@test.com', role='staff')
        StaffMember.objects.create(user=self.staff_user, business=self.business, status='active')

        # 2 confirmed docs by staff (count toward revenue), 1 draft (does not)
        make_document(self.business, self.staff_user, number='S-001', doc_status=Document.Status.CONFIRMED)
        make_document(self.business, self.staff_user, number='S-002', doc_status=Document.Status.CONFIRMED)
        make_document(self.business, self.staff_user, number='S-003', doc_status=Document.Status.DRAFT)

    def test_staff_dashboard_returns_correct_counts_and_revenue(self):
        client = APIClient()
        client.force_authenticate(user=self.staff_user)
        response = client.get('/api/staff/me/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['documents_created'], 3)
        # 2 confirmed × 115.00 grand_total
        self.assertEqual(Decimal(str(response.data['revenue_generated'])), Decimal('230.00'))
        self.assertEqual(Decimal(str(response.data['avg_transaction_value'])), Decimal('230.00') / 3)

    def test_owner_gets_403_on_staff_dashboard(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get('/api/staff/me/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
