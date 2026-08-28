# business/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, cloudinary_remove, cloudinary_signature

router = DefaultRouter()
router.register(r'', BusinessViewSet, basename='business')

urlpatterns = [
    path('', include(router.urls)),
    path('cloudinary/signature/', cloudinary_signature, name='cloudinary-signature'),
    path('cloudinary/remove/', cloudinary_remove, name='cloudinary-remove'),
]   