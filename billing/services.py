# billing/services.py
import logging
import stripe
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Subscription

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


def get_or_create_stripe_customer(business) -> str:
    """Business owner is the billing contact. Reuses an existing Stripe
    customer if we already made one — never create duplicates."""
    sub, _ = Subscription.objects.get_or_create(business=business)
    if sub.stripe_customer_id:
        return sub.stripe_customer_id

    owner = business.owner  # ⚠ verify this is the actual field name — same
                             # open gap flagged for push/services.py earlier
    customer = stripe.Customer.create(
        email=owner.email,
        name=business.name,
        metadata={'business_id': str(business.id)},
    )
    sub.stripe_customer_id = customer.id
    sub.save(update_fields=['stripe_customer_id', 'updated_at'])
    return customer.id


def create_checkout_session(business, price_id: str, success_url: str, cancel_url: str) -> str:
    customer_id = get_or_create_stripe_customer(business)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data={'metadata': {'business_id': str(business.id)}},
        allow_promotion_codes=True,
    )
    return session.url


def create_billing_portal_session(business, return_url: str) -> str:
    customer_id = get_or_create_stripe_customer(business)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


# ── Webhook handling ──────────────────────────────────────────────────────

_PLAN_TIER_BY_PRICE = {}  # populated below from settings


def _price_to_plan_tier(price_id: str) -> str:
    global _PLAN_TIER_BY_PRICE
    if not _PLAN_TIER_BY_PRICE:
        _PLAN_TIER_BY_PRICE = {v: k for k, v in settings.STRIPE_PRICE_IDS.items()}
    return _PLAN_TIER_BY_PRICE.get(price_id, Subscription.PlanTier.BASIC)


def handle_stripe_event(event: dict) -> None:
    """Dispatches by event type. Every handler is idempotent — Stripe
    retries webhooks, so re-processing the same event must be a no-op."""
    event_type = event['type']
    handler = _HANDLERS.get(event_type)
    if handler is None:
        logger.info(f"Unhandled Stripe event type: {event_type}")
        return
    handler(event['data']['object'])


def _handle_checkout_completed(session: dict) -> None:
    business_id = session.get('metadata', {}).get('business_id') \
        or session.get('subscription_data', {}).get('metadata', {}).get('business_id')
    if not business_id:
        logger.error(f"checkout.session.completed with no business_id metadata: {session.get('id')}")
        return
    _sync_subscription_from_stripe_id(business_id, session.get('subscription'))


def _handle_subscription_updated(subscription: dict) -> None:
    business_id = subscription.get('metadata', {}).get('business_id')
    if not business_id:
        # Fall back to looking up by stripe_subscription_id if metadata is missing
        sub = Subscription.objects.filter(stripe_subscription_id=subscription['id']).first()
        if sub is None:
            logger.error(f"subscription.updated for unknown business: {subscription['id']}")
            return
        _apply_stripe_subscription(sub, subscription)
        return
    _sync_subscription_from_stripe_id(business_id, subscription['id'])


def _handle_subscription_deleted(subscription: dict) -> None:
    sub = Subscription.objects.filter(stripe_subscription_id=subscription['id']).first()
    if sub is None:
        return
    sub.status = Subscription.Status.CANCELED
    sub.save(update_fields=['status', 'updated_at'])


def _sync_subscription_from_stripe_id(business_id: str, stripe_subscription_id: str) -> None:
    from business.models import Business
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        logger.error(f"Stripe webhook referenced unknown business_id={business_id}")
        return

    sub, _ = Subscription.objects.get_or_create(business=business)
    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
    _apply_stripe_subscription(sub, stripe_sub)


def _apply_stripe_subscription(sub: Subscription, stripe_sub: dict) -> None:
    price_id = stripe_sub['items']['data'][0]['price']['id']
    sub.stripe_subscription_id = stripe_sub['id']
    sub.stripe_price_id = price_id
    sub.plan_tier = _price_to_plan_tier(price_id)
    sub.status = stripe_sub['status']
    sub.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
    period_end = stripe_sub.get('current_period_end')
    if period_end:
        sub.current_period_end = timezone.datetime.fromtimestamp(period_end, tz=timezone.utc)
    sub.save()


_HANDLERS = {
    'checkout.session.completed': _handle_checkout_completed,
    'customer.subscription.updated': _handle_subscription_updated,
    'customer.subscription.deleted': _handle_subscription_deleted,
}