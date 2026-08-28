from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PushTokenViewSet

router = DefaultRouter()
router.register(r'', PushTokenViewSet, basename='push')

urlpatterns = [
    path('', include(router.urls)),
]