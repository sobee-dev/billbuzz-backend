# documents/services.py
from django.db.models import Sum
from django.utils import timezone
from .models import Document
from .serializers import DocumentSerializer, RecentActivitySerializer

def get_invoice_stats(business_id):
    now = timezone.now()
    today = now.date()
    start_of_week = today - timezone.timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    invoices = Document.objects.filter(business_id=business_id).select_related('created_by')

    paid_sales = invoices.filter(
        document_type=Document.DocumentType.SALES_INVOICE,
        status=Document.Status.PAID,
    )

    return {
        "revenue": {
            "total_year": paid_sales.filter(document_date__year=now.year).aggregate(Sum('grand_total'))['grand_total__sum'] or 0,
            "all_time": paid_sales.aggregate(Sum('grand_total'))['grand_total__sum'] or 0,
            "monthly": paid_sales.filter(document_date__gte=start_of_month).aggregate(Sum('grand_total'))['grand_total__sum'] or 0,
        },
        "sales_invoices": {
            "today": invoices.filter(document_type=Document.DocumentType.SALES_INVOICE, created_at__date__gte=today).count(),
            "this_week": invoices.filter(document_type=Document.DocumentType.SALES_INVOICE, created_at__date__gte=start_of_week).count(),
            "this_month": invoices.filter(document_type=Document.DocumentType.SALES_INVOICE, created_at__date__gte=start_of_month).count(),
            "all_time": invoices.filter(document_type=Document.DocumentType.SALES_INVOICE).count(),
        },
        "proforma_invoices": {
            "today": invoices.filter(document_type=Document.DocumentType.PROFORMA_INVOICE, created_at__date__gte=today).count(),
            "this_week": invoices.filter(document_type=Document.DocumentType.PROFORMA_INVOICE, created_at__date__gte=start_of_week).count(),
            "this_month": invoices.filter(document_type=Document.DocumentType.PROFORMA_INVOICE, created_at__date__gte=start_of_month).count(),
            "all_time": invoices.filter(document_type=Document.DocumentType.PROFORMA_INVOICE).count(),
        },
        "drafts": invoices.filter(status=Document.Status.DRAFT).count(),
        "recent_activity": RecentActivitySerializer(invoices.order_by('-created_at')[:5], many=True).data
    }