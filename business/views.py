from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from .models import Business, StaffMember, SyncStatus
from .serializers import (
    BusinessSerializer,
    BusinessListSerializer,
    BusinessCreateSerializer,
    BusinessUpdateSerializer,
    BusinessSyncSerializer,
    BusinessOnboardingSerializer
)

class BusinessViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Business management with custom actions for 
    onboarding, synchronization, and profile management.
    """
    queryset = Business.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """
        Dynamically assign serializers based on the action being performed.
        """
        if self.action == 'list':
            return BusinessListSerializer
        elif self.action == 'create':
            return BusinessCreateSerializer
        elif self.action in ['update', 'partial_update','manage_my_business']:
            return BusinessUpdateSerializer
        elif self.action == 'sync':
            return BusinessSyncSerializer
        elif self.action == 'complete_onboarding':
            return BusinessOnboardingSerializer
        return BusinessSerializer

    def get_queryset(self):
        """
        Admins see all businesses; regular users see only their own.
        """
        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(owner=self.request.user)

    @action(detail=False, methods=['get', 'patch' ,'post'], url_path='me')
    def manage_my_business(self, request):
        user_business = self.get_queryset().first()
        
        
        if request.method == 'GET':
            
           if not user_business:
                return Response({"detail": "No business found."}, status=status.HTTP_404_NOT_FOUND)
           serializer = self.get_serializer(user_business)
           return Response(serializer.data)
       
       
        # 2. CREATE Business
        if request.method == 'POST':
            # We check if they already have one to prevent duplicates
            if user_business:
                return Response({"detail": "Business already exists."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(owner=request.user,onboarding_complete=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        
        # 3. UPDATE Business
        if request.method == 'PATCH':
            
            if not user_business:
                return Response({"detail": "Business not found."}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = self.get_serializer(user_business, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        
    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        """
        POST /api/businesses/{uuid}/sync/
        Update the server_id and sync_status after a successful external sync.
        """
        business = self.get_object()
        serializer = self.get_serializer(business, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='complete-onboarding')
    def complete_onboarding(self, request, pk=None):
        """
        POST /api/businesses/{uuid}/complete-onboarding/
        Final check before allowing the user to start creating receipts.
        """
        business = self.get_object()
        # Force the onboarding_complete flag to True in the request data
        data = request.data.copy()
        data['onboarding_complete'] = True
        
        serializer = self.get_serializer(business, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "status": "Onboarding successful",
            "business": BusinessSerializer(business).data
        })
        
        
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        GET /api/business/profile/dashboard/
        Combines profile info and stats in one call.
        """
        business = get_object_or_404(self.get_queryset())
        
        # You can call other methods to build this response
        return Response({
            "info": BusinessListSerializer(business).data,
            "stats": {
                "total_expenses": 0, # Future Receipt logic
                "sync_status": business.sync_status
            }
        })
        
    @action(detail=False, methods=['get'])
    def summary_stats(self, request):
        """Moved from DashboardViewSet"""
        business = get_object_or_404(self.get_queryset)
        return Response({
            "monthly_spending": [1200, 1500, 800, 2100], 
            "categories": {"Travel": 20, "Supplies": 50, "Software": 30}
        })

    @action(detail=False, methods=['get'])
    def sync_health(self, request):
        """Moved from DashboardViewSet"""
        business = get_object_or_404(self.get_queryset)
        return Response({
            "status": business.sync_status,
            "last_synced": business.updated_at,
            "server_id": business.server_id
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def staff_dashboard(request):
    """
    GET /api/staff/me/dashboard/
    Returns performance metrics for the authenticated staff member.
    403 if the requesting user is not a staff role.
    """
    if request.user.role != 'staff':
        return Response(
            {'error': 'This endpoint is only available to staff users.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    staff = StaffMember.objects.filter(
        user=request.user, status='active'
    ).select_related('business').first()

    if not staff:
        return Response(
            {'error': 'No active staff account found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    from documents.models import Document

    docs = Document.objects.filter(
        business=staff.business,
        created_by=request.user,
    )

    documents_created = docs.count()
    revenue_generated = docs.filter(
        status__in=[Document.Status.CONFIRMED, Document.Status.DELIVERED]
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    avg_transaction_value = (
        revenue_generated / documents_created
        if documents_created else Decimal('0.00')
    )

    return Response({
        'documents_created': documents_created,
        'revenue_generated': revenue_generated,
        'avg_transaction_value': avg_transaction_value,
    })
        
        
