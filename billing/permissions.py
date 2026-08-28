# billing/permissions.py
from rest_framework import permissions


class IsBusinessOwner(permissions.BasePermission):
    """Billing management (checkout/portal links, cancel) is owner-only.
    Staff can read status (needed to show 'account restricted' banners)
    but never touch billing controls — matches the rest of the app's
    'staff mirrors owner structurally, minus permission-gated actions'
    pattern."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'owner')


class HasActiveSubscription(permissions.BasePermission):
    """Drop this on any ViewSet/action that should be paywalled. Applies
    to owner AND staff identically — a lapsed business subscription
    blocks the whole team, not just the owner."""
    message = 'This business\'s subscription is inactive. Ask the business owner to update billing.'

    def has_permission(self, request, view):
        from business.utils import get_user_business
        business = get_user_business(request.user)
        if business is None:
            return False
        sub = getattr(business, 'subscription', None)
        return bool(sub and sub.is_active_or_grace)