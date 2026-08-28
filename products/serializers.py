from rest_framework import serializers
from .models import Product
from decimal import Decimal

class ProductSerializer(serializers.ModelSerializer):
    available_to_sell = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True
    )
    is_low_stock = serializers.BooleanField(read_only=True)
    total_sold = serializers.DecimalField(max_digits=10, decimal_places=3, read_only=True)
    class Meta:
        model = Product
        fields = [
            'id', 'business', 'name', 'description', 'sku',
            'unit_price', 'image_url',
            'quantity_on_hand', 'quantity_reserved', 'reorder_level',
            'available_to_sell', 'total_sold', 'is_low_stock',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id','total_sold', 'business', 'created_at', 'updated_at']


class ProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'sku', 'unit_price',
            'image_url', 'reorder_level', 'is_active'
        ]

    def validate_sku(self, value):
        if not value:
            return value

        business = self.instance.business
        conflict = Product.objects.filter(
            business=business, sku=value
        ).exclude(pk=self.instance.pk)

        if conflict.exists():
            raise serializers.ValidationError('A product with this SKU already exists.')

        return value

class ProductListSerializer(serializers.ModelSerializer):
    total_sold = serializers.DecimalField(max_digits=10, decimal_places=3, source='total_sold_qty')
    available_to_sell = serializers.DecimalField(max_digits=10, decimal_places=3, source='available_stock')
    is_low_stock = serializers.BooleanField(source='low_stock_flag')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'unit_price', 'image_url',
            'quantity_on_hand', 'total_sold', 'available_to_sell', 'is_low_stock',
            'is_active','reorder_level',
        ]

class StockAdjustmentSerializer(serializers.Serializer):
    """
    Input serializer for POST /api/products/{id}/adjust-stock/.
    Not a ModelSerializer — this doesn't map 1:1 to InventoryTransaction,
    since the view derives transaction_type, business, and initiated_by itself.
    """
    quantity_change = serializers.DecimalField(max_digits=10, decimal_places=3)
    reason = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    reference_document_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate_quantity_change(self, value):
        if value == 0:
            raise serializers.ValidationError('Quantity change cannot be zero.')
        return value

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError('A reason is required for stock adjustments.')
        return value
    
    
class BulkDeductItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class BulkDeductSerializer(serializers.Serializer):
    reference_document_id = serializers.UUIDField(required=False, allow_null=True)
    items = BulkDeductItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value    