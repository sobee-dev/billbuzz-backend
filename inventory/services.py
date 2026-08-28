# inventory/services.py
from django.db.models import F, Sum
from django.utils import timezone
from products.models import Product
from documents.models import DocumentItem


def get_inventory_stats(business_id):
    now = timezone.now()
    start_of_month = now.date().replace(day=1)

    products = Product.objects.filter(business_id=business_id, is_active=True)

    low_stock_count = products.filter(
        reorder_level__isnull=False,
        quantity_on_hand__lt=F('reorder_level'),
    ).count()

    items_sold_this_month = (
        DocumentItem.objects.filter(
            document__business_id=business_id,
            document__status='paid',
            document__created_at__date__gte=start_of_month,
        )
        .aggregate(total=Sum('quantity'))['total']
        or 0
    )

    return {
        "low_stock": low_stock_count,
        "items_sold_this_month": items_sold_this_month,
    }