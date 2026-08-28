from django.db import models

# billing/models.py
import uuid
from django.db import models


class Subscription(models.Model):
    """One subscription per business. Lives outside the Business model
    itself (same reasoning as push/ being its own app) — billing has its
    own lifecycle, its own webhook-driven writes, and shouldn't bloat
    the core Business model."""

    class PlanTier(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        BASIC = 'basic', 'Basic'
        PRO   = 'pro', 'Pro'

    class Status(models.TextChoices):
        TRIALING          = 'trialing', 'Trialing'
        ACTIVE            = 'active', 'Active'
        PAST_DUE          = 'past_due', 'Past Due'
        CANCELED          = 'canceled', 'Canceled'
        INCOMPLETE        = 'incomplete', 'Incomplete'
        INCOMPLETE_EXPIRED = 'incomplete_expired', 'Incomplete Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='subscription',
    )

    plan_tier = models.CharField(max_length=20, choices=PlanTier.choices, default=PlanTier.TRIAL)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.TRIALING)

    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)

    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['stripe_subscription_id']),
        ]

    def __str__(self):
        return f"{self.business.name} — {self.plan_tier} ({self.status})"

    @property
    def is_active(self) -> bool:
        """Single source of truth for 'does this business get to use paid
        features'. Trialing counts as active; past_due gets a short grace
        window handled by whoever calls this (see is_active_or_grace)."""
        return self.status in (self.Status.TRIALING, self.Status.ACTIVE)

    @property
    def is_active_or_grace(self) -> bool:
        from django.utils import timezone
        if self.is_active:
            return True
        if self.status == self.Status.PAST_DUE and self.current_period_end:
            # 3-day grace period past the period end before hard-locking —
            # avoids punishing a business for a card that just needs retrying.
            grace_until = self.current_period_end + timezone.timedelta(days=3)
            return timezone.now() < grace_until
        return False
