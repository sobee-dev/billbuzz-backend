from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'business', 'unit_price', 'quantity_on_hand', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'business']
    search_fields = ['name', 'sku', 'business__name']
    ordering = ['name']
    raw_id_fields = ['business']
    readonly_fields = ['id', 'created_at', 'updated_at']
