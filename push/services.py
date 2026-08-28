import logging
from typing import Iterable, Optional

import requests

from .models import PushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
EXPO_BATCH_SIZE = 100  # Expo rejects requests with more than 100 messages


def _chunk(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def send_push_to_tokens(
    tokens: Iterable[str], title: str, body: str, data: Optional[dict] = None
) -> bool:
    """
    Low-level send: batches messages and posts them to Expo's push API.
    Returns True only if every batch was *accepted* by Expo — this
    confirms Expo received the request, not that the notification was
    actually delivered to the device. Delivery confirmation requires
    polling Expo's separate receipt endpoint, which isn't implemented
    here; add it if you need delivery guarantees rather than best-effort.
    """
    tokens = [t for t in dict.fromkeys(tokens) if t]  # de-dupe, keep order
    if not tokens:
        return True

    messages = [
        {'to': t, 'title': title, 'body': body, 'data': data or {}, 'sound': 'default'}
        for t in tokens
    ]

    all_ok = True
    for batch in _chunk(messages, EXPO_BATCH_SIZE):
        try:
            resp = requests.post(
                EXPO_PUSH_URL,
                json=batch,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=10,
            )
            resp.raise_for_status()
            tickets = resp.json().get('data', [])

            # A DeviceNotRegistered error means the token is dead (app
            # uninstalled, etc.) — prune it opportunistically so future
            # sends don't keep paying for a doomed request.
            for ticket, sent_token in zip(tickets, [m['to'] for m in batch]):
                if ticket.get('status') == 'error' and \
                        ticket.get('details', {}).get('error') == 'DeviceNotRegistered':
                    PushToken.objects.filter(token=sent_token).delete()
                    logger.info(f"Pruned dead push token: {sent_token}")
        except requests.RequestException as e:
            all_ok = False
            logger.error(f"Push batch failed to send: {e}")

    return all_ok


def send_push_to_user(user, title: str, body: str, data: Optional[dict] = None) -> bool:
    """Sends to every device currently registered for this user."""
    tokens = list(PushToken.objects.filter(user=user).values_list('token', flat=True))
    return send_push_to_tokens(tokens, title, body, data)


def send_push_to_business_owner(
    business, title: str, body: str, data: Optional[dict] = None
) -> bool:
    """
    Convenience wrapper for the common "notify the owner" case — new
    staff-created document, low stock crossing, invitation accepted,
    etc.

    NOTE: this assumes `business.owner` resolves to the owning User.
    I don't have your Business model in context, so adjust the
    attribute/related_name to whatever it actually is (e.g. if it's
    the reverse of a User.business OneToOneField, it may need to be
    `business.user` or a lookup like
    `User.objects.get(business=business, role='owner')` instead).
    """
    owner = getattr(business, 'owner', None)
    if owner is None:
        logger.warning(f"send_push_to_business_owner: no owner resolvable for business {business}")
        return False
    return send_push_to_user(owner, title, body, data)