from rest_framework import mixins, viewsets, permissions
from rest_framework.pagination import CursorPagination
from rest_framework.exceptions import MethodNotAllowed

from .models import InventoryTransaction
from .serializers import InventoryTransactionSerializer


class InventoryTransactionPagination(CursorPagination):
    page_size = 50
    ordering = '-created_at'
    cursor_query_param = 'cursor'


class InventoryTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only audit trail. Transactions are created by business logic only,
    never through the API. All mutating methods are explicitly rejected.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = InventoryTransactionPagination
    serializer_class = InventoryTransactionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = InventoryTransaction.objects.filter(
            business__owner=user,
        ).select_related('product', 'business', 'initiated_by')

        product_id = self.kwargs.get('product_pk')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        return queryset

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed('POST')

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PUT')

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH')

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed('DELETE')
