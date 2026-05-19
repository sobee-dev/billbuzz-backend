from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date

from accounts.models import User
from business.models import Business
from products.models import Product
from inventory.models import InventoryTransaction


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


def make_product(business):
    return Product.objects.create(
        business=business,
        name='Widget',
        sku='WGT-001',
        unit_price='9.99',
    )


class InventoryTransactionModelTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business)

    def test_transaction_created_via_model(self):
        tx = InventoryTransaction.objects.create(
            business=self.business,
            product=self.product,
            quantity_change='-5.000',
            transaction_type=InventoryTransaction.TransactionType.SALE_DELIVERED,
            initiated_by=self.owner,
            reason='Sold 5 units',
        )
        self.assertEqual(InventoryTransaction.objects.count(), 1)
        self.assertEqual(tx.transaction_type, 'sale_delivered')
        self.assertEqual(str(tx.quantity_change), '-5.000')


class InventoryTransactionAPITest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com')
        self.business = make_business(self.owner)
        self.product = make_product(self.business)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
        self.list_url = f'/api/inventory/products/{self.product.id}/history/'
        InventoryTransaction.objects.create(
            business=self.business,
            product=self.product,
            quantity_change='10.000',
            transaction_type=InventoryTransaction.TransactionType.ADJUSTMENT,
            initiated_by=self.owner,
        )

    def test_post_to_list_returns_405(self):
        response = self.client.post(self.list_url, {
            'quantity_change': '5.000',
            'transaction_type': 'adjustment',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_to_detail_returns_405(self):
        tx = InventoryTransaction.objects.first()
        detail_url = f'/api/inventory/products/{self.product.id}/history/{tx.id}/'
        response = self.client.patch(detail_url, {'reason': 'hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
