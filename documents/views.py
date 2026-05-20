from decimal import Decimal

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from business.models import Business, StaffMember
from inventory.models import InventoryTransaction
from .models import Document, DocumentItem
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
        try:
            doc.confirm()
        except DjangoValidationError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)
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
        try:
            doc.cancel()
        except DjangoValidationError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)
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

    @action(detail=True, methods=['post'], url_path='deduct-inventory')
    @transaction.atomic
    def deduct_inventory(self, request, pk=None):
        """
        Manually deduct stock for a sales invoice.

        Body (choose one):
          { "subtract_all": true }
          { "items": [{"item_id": "<uuid>", "quantity": 5}] }
        """
        doc = self.get_object()
        if doc.document_type != Document.DocumentType.SALES_INVOICE:
            return Response(
                {'error': 'deduct-inventory is only valid for sales invoices.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subtract_all = request.data.get('subtract_all', False)
        items_payload = request.data.get('items', [])

        if not subtract_all and not items_payload:
            return Response(
                {'error': 'Provide either subtract_all=true or a non-empty items list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tracked = doc.items.filter(product__isnull=False).select_related('product')

        if subtract_all:
            targets = [(item, item.quantity) for item in tracked]
        else:
            # Build a lookup by item id
            item_map = {str(item.id): item for item in tracked}
            targets = []
            for entry in items_payload:
                item_id = str(entry.get('item_id', ''))
                try:
                    qty = Decimal(str(entry.get('quantity', 0)))
                except Exception:
                    return Response(
                        {'error': f'Invalid quantity for item {item_id}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if item_id not in item_map:
                    return Response(
                        {'error': f'Item {item_id} not found on this document.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                targets.append((item_map[item_id], qty))

        # Validate stock before touching anything
        for item, qty in targets:
            if item.product.quantity_on_hand < qty:
                return Response(
                    {
                        'error': (
                            f"Insufficient stock for '{item.product.name}'. "
                            f"Available: {item.product.quantity_on_hand}, "
                            f"Requested: {qty}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for item, qty in targets:
            item.product.quantity_on_hand -= qty
            item.product.save(update_fields=['quantity_on_hand', 'updated_at'])
            InventoryTransaction.objects.create(
                business=doc.business,
                product=item.product,
                quantity_change=-qty,
                transaction_type=InventoryTransaction.TransactionType.SALE_DELIVERED,
                reference_document_id=doc.id,
                initiated_by=request.user,
            )

        return Response({'status': 'Stock deducted.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='add-to-inventory')
    @transaction.atomic
    def add_to_inventory(self, request, pk=None):
        """Add all line items to inventory for a purchase invoice."""
        doc = self.get_object()
        if doc.document_type != Document.DocumentType.PURCHASE_INVOICE:
            return Response(
                {'error': 'add-to-inventory is only valid for purchase invoices.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tracked = doc.items.filter(product__isnull=False).select_related('product')
        if not tracked.exists():
            return Response(
                {'error': 'No inventory-tracked items on this document.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in tracked:
            item.product.quantity_on_hand += item.quantity
            item.product.save(update_fields=['quantity_on_hand', 'updated_at'])
            InventoryTransaction.objects.create(
                business=doc.business,
                product=item.product,
                quantity_change=item.quantity,
                transaction_type=InventoryTransaction.TransactionType.PURCHASE_RECEIVED,
                reference_document_id=doc.id,
                initiated_by=request.user,
            )

        return Response({'status': 'Stock added.'}, status=status.HTTP_200_OK)
