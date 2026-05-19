from rest_framework import serializers
from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id', 'business', 'customer', 'created_by',
            'document_type', 'status', 'document_number', 'document_date',
            'customer_name', 'customer_email', 'customer_phone',
            'supplier_name',
            'subtotal', 'tax_rate', 'tax_amount', 'discount', 'grand_total',
            'payment_status', 'amount_paid', 'paid_at',
            'is_delivered', 'delivered_at',
            'sync_status', 'deleted_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'business', 'created_by', 'created_at', 'updated_at']
        # Unique-together is enforced per business; suppress default DRF validator
        # so bulk-sync can upsert without fighting the constraint.
        validators = []


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for paginated list views."""
    class Meta:
        model = Document
        fields = [
            'id', 'document_type', 'status', 'document_number', 'document_date',
            'customer_name', 'supplier_name',
            'grand_total', 'payment_status', 'amount_paid',
            'is_delivered', 'sync_status',
        ]
