from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import InventoryTransactionViewSet

# Manually wire the nested route so no extra package is needed.
# GET /api/inventory/products/{product_pk}/history/
# GET /api/inventory/products/{product_pk}/history/{pk}/

router = DefaultRouter()

urlpatterns = [
    path(
        'products/<uuid:product_pk>/history/',
        InventoryTransactionViewSet.as_view({'get': 'list'}),
        name='product-inventory-list',
    ),
    path(
        'products/<uuid:product_pk>/history/<uuid:pk>/',
        InventoryTransactionViewSet.as_view({'get': 'retrieve'}),
        name='product-inventory-detail',
    ),
]
