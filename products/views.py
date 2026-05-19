from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination

from business.models import Business
from .models import Product
from .serializers import ProductSerializer, ProductListSerializer


class ProductCursorPagination(CursorPagination):
    page_size = 20
    ordering = 'name'
    cursor_query_param = 'cursor'


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProductCursorPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Product.objects.filter(
            business__owner=user
        ).select_related('business')

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                name__icontains=search
            ) | queryset.filter(
                sku__icontains=search
            )

        return queryset

    def perform_create(self, serializer):
        business = Business.objects.get(owner=self.request.user)
        serializer.save(business=business)

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        if request.user.role != 'owner':
            return Response(
                {'error': 'Only business owners can deactivate products.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {'status': 'Product deactivated', 'id': str(product.id)},
            status=status.HTTP_200_OK
        )
