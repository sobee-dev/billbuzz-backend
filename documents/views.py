from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from django.db import transaction

from business.models import Business, StaffMember
from .models import Document
from .serializers import DocumentSerializer, DocumentListSerializer


class DocumentCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-document_date'
    cursor_query_param = 'cursor'


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DocumentCursorPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    def _get_base_queryset(self):
        """Returns the unfiltered base queryset scoped to the requesting user's role."""
        user = self.request.user

        if user.role == 'staff':
            staff = StaffMember.objects.filter(
                user=user, status='active'
            ).select_related('business').first()
            if not staff:
                return Document.objects.none()
            return Document.objects.filter(
                business=staff.business,
                created_by=user,
                deleted_at__isnull=True,
            ).select_related('business', 'customer', 'created_by')

        # owner (and admin) — see all documents for their business
        return Document.objects.filter(
            business__owner=user,
            deleted_at__isnull=True,
        ).select_related('business', 'customer', 'created_by')

    def get_queryset(self):
        queryset = self._get_base_queryset()

        # ── Filters ──────────────────────────────────────────────────────────
        doc_type = self.request.query_params.get('document_type')
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)

        doc_status = self.request.query_params.get('status')
        if doc_status:
            queryset = queryset.filter(status=doc_status)

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user

        if user.role == 'staff':
            staff = StaffMember.objects.filter(
                user=user, status='active'
            ).select_related('business').first()
            if not staff:
                raise PermissionDenied('No active staff account found.')
            business = staff.business
        else:
            business = Business.objects.get(owner=user)

        serializer.save(
            business=business,
            created_by=user,
            sync_status=Document.SyncStatus.SYNCED,
        )

    def perform_destroy(self, instance):
        instance.soft_delete()

    # ── Custom actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        doc = self.get_object()
        if doc.status != Document.Status.DRAFT:
            return Response(
                {'error': 'Only draft documents can be confirmed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc.status = Document.Status.CONFIRMED
        doc.save(update_fields=['status', 'updated_at'])
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='deliver')
    def deliver(self, request, pk=None):
        doc = self.get_object()
        if doc.status not in (Document.Status.CONFIRMED, Document.Status.DRAFT):
            return Response(
                {'error': 'Document cannot be marked delivered from its current status.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc.mark_delivered()
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        doc = self.get_object()
        if doc.status == Document.Status.CANCELLED:
            return Response(
                {'error': 'Document is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc.status = Document.Status.CANCELLED
        doc.save(update_fields=['status', 'updated_at'])
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        doc = self.get_object()
        doc.mark_paid()
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='soft-delete')
    def soft_delete(self, request, pk=None):
        doc = self.get_object()
        doc.soft_delete()
        return Response({'status': 'Document deleted', 'id': str(doc.id)})
