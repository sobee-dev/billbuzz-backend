# billing/web_urls.py
from django.urls import path
from . import web_views

urlpatterns = [
    path('login/', web_views.login_view, name='billing-login'),
    path('logout/', web_views.logout_view, name='billing-logout'),
    path('', web_views.dashboard_view, name='billing-dashboard'),
    path('plans/', web_views.plans_view, name='billing-plans'),
    path('checkout/<str:tier>/', web_views.start_checkout, name='billing-checkout'),
    path('portal/', web_views.open_portal, name='billing-portal'),
    path('success/', web_views.checkout_success, name='billing-success'),
    path('cancel/', web_views.checkout_cancel, name='billing-cancel'),
]