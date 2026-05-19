from django.test import TestCase
from django.db import IntegrityError
from accounts.models import User
from business.models import Business, StaffMember


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
