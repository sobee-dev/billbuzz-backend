from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    available_to_sell = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True
    )
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'business', 'name', 'description', 'sku',
            'unit_price', 'image_url',
            'quantity_on_hand', 'quantity_reserved', 'reorder_level',
            'available_to_sell', 'is_low_stock',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'business', 'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    available_to_sell = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True
    )
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'unit_price', 'image_url',
            'quantity_on_hand', 'available_to_sell', 'is_low_stock',
            'is_active',
        ]
