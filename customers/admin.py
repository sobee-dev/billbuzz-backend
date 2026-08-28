from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'business', 'outstanding_balance', 'status', 'created_at']
    list_filter = ['status', 'payment_method_preference', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'business__name']
    ordering = [ 'full_name']
    raw_id_fields = ['business']
    readonly_fields = ['id', 'created_at']
