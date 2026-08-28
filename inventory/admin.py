from django.contrib import admin
from .models import InventoryTransaction


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'transaction_type', 'quantity_change',
        'initiated_by', 'reason', 'created_at',
    ]
    list_filter = ['transaction_type', 'created_at', 'business']
    search_fields = ['product__name', 'product__sku', 'reason', 'initiated_by__email']
    ordering = ['-created_at']
    raw_id_fields = ['business', 'product', 'initiated_by']
    readonly_fields = [f.name for f in InventoryTransaction._meta.get_fields()]

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser