# billing/urls.py
from django.urls import path
from .views import SubscriptionStatusView, stripe_webhook

urlpatterns = [
    path('status/', SubscriptionStatusView.as_view(), name='billing-status'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]