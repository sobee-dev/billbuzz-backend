from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from business.models import Business
from documents.models import Document
from products.models import Product


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    if request.user.role != 'owner':
        return Response(
            {'error': 'Only business owners can access reports.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return Response(
            {'error': 'No business found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    today = timezone.localdate()
    month_start = today.replace(day=1)

    # ── This month's revenue ──────────────────────────────────────────────────
    # Confirmed or delivered sales_invoices and receipts from this month.
    this_month_revenue = Document.objects.filter(
        business=business,
        document_type__in=[
            Document.DocumentType.SALES_INVOICE,
            Document.DocumentType.RECEIPT,
        ],
        status__in=[Document.Status.CONFIRMED, Document.Status.DELIVERED],
        document_date__gte=month_start,
        deleted_at__isnull=True,
    ).aggregate(
        total=Sum('grand_total')
    )['total'] or Decimal('0.00')

    # ── Outstanding receivables ───────────────────────────────────────────────
    outstanding_receivables = Document.objects.filter(
        business=business,
        payment_status__in=[
            Document.PaymentStatus.UNPAID,
            Document.PaymentStatus.PARTIAL,
        ],
        deleted_at__isnull=True,
    ).aggregate(
        total=Sum('grand_total')
    )['total'] or Decimal('0.00')

    # ── Inventory value ───────────────────────────────────────────────────────
    # Sum of (quantity_on_hand * unit_price) for active products — computed
    # entirely in the DB with ExpressionWrapper to avoid Python loops.
    inventory_value = Product.objects.filter(
        business=business,
        is_active=True,
    ).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity_on_hand') * F('unit_price'),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')

    # ── Low stock count ───────────────────────────────────────────────────────
    # Active products where a reorder_level is set and stock is below it.
    low_stock_count = Product.objects.filter(
        business=business,
        is_active=True,
        reorder_level__isnull=False,
        quantity_on_hand__lt=F('reorder_level'),
    ).count()

    return Response({
        'this_month_revenue':     this_month_revenue,
        'outstanding_receivables': outstanding_receivables,
        'inventory_value':         inventory_value,
        'low_stock_count':         low_stock_count,
    })
