from rest_framework import serializers
from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    lifetime_value = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'business',
            'first_name', 'last_name', 'full_name',
            'email', 'phone', 'business_name',
            'payment_method_preference', 'tags', 'notes',
            'outstanding_balance', 'lifetime_value',
            'status', 'created_at',
        ]
        read_only_fields = ['id', 'business', 'created_at']

    def get_lifetime_value(self, obj):
        return obj.lifetime_value


class CustomerListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    lifetime_value = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'phone',
            'business_name', 'tags', 'outstanding_balance',
            'lifetime_value', 'status',
        ]

    def get_lifetime_value(self, obj):
        return obj.lifetime_value
