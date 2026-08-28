from decimal import Decimal
from datetime import date

from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from business.models import Business
from documents.models import Document

MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _shift_month(year: int, month: int, delta: int):
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, (idx % 12) + 1


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
    sales_invoices = Document.objects.filter(
        business=business,
        document_type=Document.DocumentType.SALES_INVOICE,
        deleted_at__isnull=True,
    )

    # ── Last 6 months of paid revenue, oldest first ──────────────────────────
    monthly_revenue = []
    cursor_year, cursor_month = today.year, today.month
    months = []
    for i in range(5, -1, -1):
        y, m = _shift_month(today.year, today.month, -i)
        months.append((y, m))

    for y, m in months:
        start, end = _month_bounds(y, m)
        total = sales_invoices.filter(
            status=Document.Status.PAID,
            document_date__gte=start,
            document_date__lt=end,
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        monthly_revenue.append({
            'month': MONTH_ABBR[m - 1],
            'value': total,
            'current': (y == today.year and m == today.month),
        })

    this_month_start, this_month_end = _month_bounds(today.year, today.month)
    last_year, last_month = _shift_month(today.year, today.month, -1)
    last_month_start, last_month_end = _month_bounds(last_year, last_month)

    this_month_paid = sales_invoices.filter(
        status=Document.Status.PAID,
        document_date__gte=this_month_start,
        document_date__lt=this_month_end,
    )
    this_month_revenue = this_month_paid.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    this_month_count = this_month_paid.aggregate(count=Count('id'))['count'] or 0

    last_month_revenue = sales_invoices.filter(
        status=Document.Status.PAID,
        document_date__gte=last_month_start,
        document_date__lt=last_month_end,
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    if last_month_revenue > 0:
        growth_pct = ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100
        revenue_growth = f"{'+' if growth_pct >= 0 else ''}{growth_pct:.1f}%"
    elif this_month_revenue > 0:
        revenue_growth = '+100%'
    else:
        revenue_growth = '—'

    avg_invoice_value = (this_month_revenue / this_month_count) if this_month_count > 0 else Decimal('0.00')

    # ── Collection rate: paid vs (paid + unpaid), issued this month ─────────
    this_month_all = sales_invoices.filter(
        status__in=[Document.Status.PAID, Document.Status.UNPAID],
        document_date__gte=this_month_start,
        document_date__lt=this_month_end,
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    if this_month_all > 0:
        collection_rate = f"{(this_month_revenue / this_month_all) * 100:.0f}%"
    else:
        collection_rate = '—'

    # ── Outstanding: all unpaid sales invoices, not scoped to this month ────
    outstanding_total = sales_invoices.filter(
        status=Document.Status.UNPAID,
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    return Response({
        'monthly_revenue':    monthly_revenue,
        'revenue_total':      this_month_revenue,
        'revenue_growth':     revenue_growth,
        'avg_invoice_value':  avg_invoice_value,
        'collection_rate':    collection_rate,
        'outstanding_total':  outstanding_total,
    })