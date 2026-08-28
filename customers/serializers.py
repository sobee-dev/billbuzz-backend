from rest_framework import serializers
from .models import Customer
from decimal import Decimal

class CustomerSerializer(serializers.ModelSerializer):
    lifetime_value = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'business',
            'full_name', 'email', 'phone',
            'payment_method_preference', 'tags', 'notes',
            'outstanding_balance', 'lifetime_value',
            'status', 'created_at',
        ]
        read_only_fields = ['id', 'business', 'created_at']

    def get_lifetime_value(self, obj):
       
        # to avoid firing a second aggregate query via the model property.
        # Falls back to the property for instances that didn't come through
       
        annotated = getattr(obj, 'ltv', None)
        if annotated is not None:
            return annotated
        return obj.lifetime_value


class CustomerListSerializer(serializers.ModelSerializer):
    lifetime_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, default=Decimal('0.00'))

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'phone', 'lifetime_value',
            'tags', 'outstanding_balance', 'status', 'created_at',
        ]