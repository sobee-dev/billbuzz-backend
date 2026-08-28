# billing/web_views.py
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from business.utils import get_user_business
from .models import Subscription
from .services import create_checkout_session, create_billing_portal_session


def login_view(request):
    if request.user.is_authenticated:
        return redirect('billing-dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is None:
            messages.error(request, 'Invalid email or password.')
        elif user.role != 'owner':
            messages.error(request, 'Only business owners can manage billing.')
        else:
            login(request, user)
            return redirect('billing-dashboard')

    return render(request, 'billing/login.html')


def logout_view(request):
    logout(request)
    return redirect('billing-login')


@login_required(login_url='billing-login')
def dashboard_view(request):
    business = get_user_business(request.user)
    if business is None or request.user.role != 'owner':
        messages.error(request, 'No business found for this account.')
        return redirect('billing-login')

    sub, _ = Subscription.objects.get_or_create(business=business)
    return render(request, 'billing/dashboard.html', {'business': business, 'subscription': sub})


@login_required(login_url='billing-login')
def plans_view(request):
    business = get_user_business(request.user)
    return render(request, 'billing/plans.html', {
        'business': business,
        'plans': [
            {'tier': 'basic', 'label': 'Basic', 'price': '$9/mo'},
            {'tier': 'pro',   'label': 'Pro',   'price': '$29/mo'},
        ],
    })


@login_required(login_url='billing-login')
def start_checkout(request, tier: str):
    business = get_user_business(request.user)
    price_id = settings.STRIPE_PRICE_IDS.get(tier)
    if not price_id:
        messages.error(request, 'Unknown plan.')
        return redirect('billing-plans')

    checkout_url = create_checkout_session(
        business=business,
        price_id=price_id,
        success_url=request.build_absolute_uri('/billing/success/'),
        cancel_url=request.build_absolute_uri('/billing/cancel/'),
    )
    return redirect(checkout_url)


@login_required(login_url='billing-login')
def open_portal(request):
    business = get_user_business(request.user)
    portal_url = create_billing_portal_session(
        business=business,
        return_url=request.build_absolute_uri('/billing/'),
    )
    return redirect(portal_url)


def checkout_success(request):
    return render(request, 'billing/success.html')


def checkout_cancel(request):
    return render(request, 'billing/cancel.html')