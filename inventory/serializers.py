from rest_framework import serializers
from .models import InventoryTransaction


class InventoryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'business', 'product',
            'quantity_change', 'transaction_type',
            'reference_document_id',
            'initiated_by', 'reason', 'created_at',
        ]
        read_only_fields = fields
