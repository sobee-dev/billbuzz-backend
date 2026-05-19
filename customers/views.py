from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from django.db.models import Q

from business.models import Business
from .models import Customer
from .serializers import CustomerSerializer, CustomerListSerializer


class CustomerCursorPagination(CursorPagination):
    page_size = 20
    ordering = 'last_name'
    cursor_query_param = 'cursor'


class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomerCursorPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Customer.objects.filter(
            business__owner=user
        ).select_related('business')

        status_filter = self.request.query_params.get('status')
        if status_filter in ('active', 'inactive'):
            queryset = queryset.filter(status=status_filter)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        business = Business.objects.get(owner=self.request.user)
        serializer.save(business=business)

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        customer = self.get_object()
        customer.status = 'inactive'
        customer.save(update_fields=['status'])
        return Response(
            {'status': 'Customer deactivated', 'id': str(customer.id)},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        customer = self.get_object()
        customer.status = 'active'
        customer.save(update_fields=['status'])
        return Response(
            {'status': 'Customer reactivated', 'id': str(customer.id)},
            status=status.HTTP_200_OK
        )
