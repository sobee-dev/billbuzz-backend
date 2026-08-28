from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        'document_number', 'document_type',\
        'business', 'customer_name', 'grand_total',
        'status', 'document_date',
    ]
    list_filter = ['document_type', 'status', 'is_delivered', 'document_date']
    search_fields = [
        'document_number', 'customer_name', 'customer_email',
        'supplier_name', 'business__name',
    ]
    ordering = ['-document_date']
    raw_id_fields = ['business', 'customer', 'created_by']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']

    fieldsets = (
        ('Document Info', {'fields': (
            'id', 'business', 'created_by',
            'document_type', 'status', 'document_number', 'document_date',
        )}),
        ('Customer / Supplier', {'fields': (
            'customer', 'customer_name', 'customer_email', 'customer_phone',
            'supplier_name',
        )}),
        ('Financials', {'fields': (
            'subtotal', 'tax_rate', 'tax_amount', 'discount', 'grand_total',
        )}),
        ('Payment', {'fields': (
             'amount_paid', 'paid_at',
        )}),
        ('Delivery', {'fields': (
            'is_delivered', 'delivered_at',
        )}),
        ('Sync & Audit', {'fields': (
            'sync_status', 'deleted_at', 'created_at', 'updated_at',
        )}),
    )
