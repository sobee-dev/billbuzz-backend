# billing/serializers.py
from rest_framework import serializers
from .models import Subscription


class SubscriptionStatusSerializer(serializers.ModelSerializer):
    """Read-only — this is all the mobile app ever sees. No pricing,
    no purchase fields, no Stripe IDs (those stay server-side)."""
    isActiveOrGrace = serializers.BooleanField(source='is_active_or_grace', read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'plan_tier', 'status', 'trial_ends_at',
            'current_period_end', 'cancel_at_period_end', 'isActiveOrGrace',
        ]
        read_only_fields = fields