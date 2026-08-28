# customers/services.py
from django.utils import timezone
from .models import Customer

def get_client_stats(business_id):
    now = timezone.now()
    today = now.date()
    start_of_week = today - timezone.timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    clients = Customer.objects.filter(business_id=business_id)

    return {
        "new_this_week": clients.filter(created_at__date__gte=start_of_week).count(),
        "new_this_month": clients.filter(created_at__date__gte=start_of_month).count(),
        "total": clients.count(),
    }
    
    
def get_or_create_customer(business, name=None, email=None, phone=None):
    """
    Matches an existing customer by email first (most reliable identifier),
    falling back to exact name match, else creates a new one.
    Deliberately does NOT match on name alone across different customers —
    Customer is a standalone, independently-manageable resource, so a
    document snapshot shouldn't silently attach itself to the wrong person.
    """
    if email:
        existing = Customer.objects.filter(business=business, email__iexact=email).first()
        if existing:
            return existing

    if name:
        existing = Customer.objects.filter(business=business, full_name__iexact=name).first()
        if existing:
            return existing

    return Customer.objects.create(
        business=business,
        full_name=name or '',
        email=email or '',
        phone=phone or '',
    )    
    