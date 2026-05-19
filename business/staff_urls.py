from django.urls import path
from .views import staff_dashboard

urlpatterns = [
    path('me/dashboard/', staff_dashboard, name='staff-dashboard'),
]
