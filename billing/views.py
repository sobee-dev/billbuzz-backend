from django.shortcuts import render

# billing/views.py
import stripe
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from business.utils import get_user_business
from .models import Subscription
from .serializers import SubscriptionStatusSerializer
from .services import handle_stripe_event
from .permissions import IsBusinessOwner


class SubscriptionStatusView(APIView):
    """
    GET /api/billing/status/
    Any authenticated business member (owner or staff) can read this —
    it's what powers the read-only banner on both dashboards.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        business = get_user_business(request.user)
        if business is None:
            return Response({'error': 'No business associated with this account.'}, status=400)

        sub, _ = Subscription.objects.get_or_create(business=business)
        return Response(SubscriptionStatusSerializer(sub).data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def stripe_webhook(request):
    """
    POST /api/billing/webhook/
    Public endpoint — Stripe calls this directly, no user auth. Security
    comes entirely from the signature check, not from DRF permissions.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    handle_stripe_event(event)
    return HttpResponse(status=200)