from decimal import Decimal

from django.db.models import Sum

from documents.models import Document
from staff.serializers import StaffMemberSerializer


def get_full_staff_data(staff):
    docs = Document.objects.filter(
            business=staff.business,
            created_by=staff.user,
        )

    documents_created = docs.count()
    
    # Calculate revenue
    revenue_generated = docs.filter(
        status__in=[Document.Status.PAID, Document.Status.DELIVERED]
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    # Calculate average transaction value
    avg_transaction_value = (
        revenue_generated / documents_created
        if documents_created > 0 else Decimal('0.00')
    )
    return{
        'documents_created': documents_created,
        'revenue_generated': str(revenue_generated),
        'avg_transaction_value': str(avg_transaction_value),
        'staff_info': StaffMemberSerializer(staff).data
    }