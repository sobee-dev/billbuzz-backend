

# accounts/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
import os
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from business.models import Business
from business.serializers import BusinessSerializer
from business.utils import get_user_business
from receipts.models import Receipt
from receipts.serializers import ReceiptListSerializer
from django.conf import settings

from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    UserListSerializer,
    UserWithBusinessSerializer,
    AdminDashboardSerializer,
    LoginResponseSerializer,
)

from rest_framework_simplejwt.views import TokenRefreshView
from .token import SessionLimitedTokenRefreshSerializer
from django.http import HttpResponse
from django.views.decorators.http import require_GET
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User model handling Authentication and Profile management.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action in ['create', 'register']:
            return UserRegistrationSerializer
        elif self.action in ['update', 'partial_update', 'update_notifications']:
            return UserUpdateSerializer
        elif self.action == 'list':
            return UserListSerializer
        elif self.action == 'with_business':
            return UserWithBusinessSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        elif self.action == 'admin_dashboard_stats':
            return AdminDashboardSerializer
        
        return UserSerializer
        
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['register', 'login']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """Filter queryset: Admins see all, users see only themselves"""
        if self.request.user.is_authenticated:
            if self.request.user.is_staff:
                return User.objects.all()
            return User.objects.filter(id=self.request.user.id)
        return User.objects.none()

    # ========== REGISTER ==========
    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        POST /api/users/register/
        Register a new user account
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        refresh['orig_iat'] = int(timezone.now().timestamp())
        
        response = Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'requires_password_change': user.requires_password_change,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)

        return response

    # ========== LOGIN ==========
    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        POST /api/users/login/
        
        Accepts:
          - email + password (standard login)
        
        Returns:
          - access token
          - refresh token
          - user data
          - requires_password_change flag ← KEY FOR STAFF PASSWORD CHANGE
          - business data (if owner)
          - recent receipts (if owner)
        """
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email:
            return Response(
                {'error': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not password:
            return Response(
                {'error': 'Password is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(request, email=email.lower(), password=password)
        if user is None:
            return Response(
                {'error': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'Account is disabled.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh['orig_iat'] = int(timezone.now().timestamp())
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Get business and receipts (for owners)
        business = get_user_business(user)
        receipts_qs = Receipt.objects.filter(
            business=business
        ).order_by('-updated_at')[:50] if business else []
        receipts_data = ReceiptListSerializer(receipts_qs, many=True).data
        
        # Prepare response
        response = Response({
            'user': UserSerializer(user).data,
            'business': BusinessSerializer(business).data if business else None,
            'receipts': receipts_data,
            'access': access_token,
            'refresh': refresh_token,
            'requires_password_change': user.requires_password_change,  # ← KEY FLAG
            'message': 'Login successful',
        }, status=status.HTTP_200_OK)
        
        return response

    # ========== CHANGE PASSWORD ==========
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """
        POST /api/users/change_password/
        
        Staff changes password (required on first login).
        On first login, old_password is not required.
        
        Request:
          - old_password (optional on first login, required after)
          - new_password
          - new_password_confirm
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)

    # ========== VERIFY EMAIL ==========
    @action(detail=False, methods=['post'])
    def verify_email(self, request):
        """POST /api/users/verify_email/"""
        user = request.user
        user.email_verified_at = timezone.now()
        user.save()
        
        return Response({
            'message': 'Email verified successfully',
            'email_verified_at': user.email_verified_at
        }, status=status.HTTP_200_OK)

    # ========== UPDATE NOTIFICATIONS ==========
    @action(detail=False, methods=['patch'])
    def update_notifications(self, request):
        """PATCH /api/users/update_notifications/"""
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Notification preferences updated',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    # ========== GET CURRENT USER ==========
    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /api/users/me/"""
        serializer = UserWithBusinessSerializer(request.user)
        return Response(serializer.data)

    # ========== LOGOUT ==========
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """POST /api/users/logout/"""
        response = Response(
            {'message': 'Logout successful'},
            status=status.HTTP_200_OK
        )
        
        # Delete the cookie from the browser (if using cookies)
        if hasattr(settings, 'SIMPLE_JWT') and 'AUTH_COOKIE' in settings.SIMPLE_JWT:
            response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
        
        # Optional: Blacklist refresh token if provided
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Token might already be expired
            
        return response

    # ========== ADMIN DASHBOARD STATS ==========
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def admin_dashboard_stats(self, request):
        """GET /api/users/admin_dashboard_stats/"""
        stats_data = {
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "verified_users": User.objects.filter(email_verified_at__isnull=False).count(),
            "new_users_today": User.objects.filter(date_joined__date=timezone.now().date()).count(),
        }   
        serializer = self.get_serializer(stats_data)
        return Response(serializer.data)



# accounts/views.py
@require_GET
def oauth_mobile_bridge(request):
    code = request.GET.get('code', '')
    state = request.GET.get('state', '')
    error = request.GET.get('error', '')

    deep_link = (
        f"billbuzz://oauth/callback?error={error}"
        if error else
        f"billbuzz://oauth/callback?code={code}&state={state}"
    )

    html = f"""<!DOCTYPE html>
    <html><head><meta http-equiv="refresh" content="0;url={deep_link}"></head>
    <body>
      <p>Redirecting back to the app…</p>
      <script>window.location.replace("{deep_link}");</script>
    </body></html>"""
    return HttpResponse(html)


# ============================================
# GOOGLE OAUTH VIEW
# ============================================
class GoogleCallbackView(APIView):
    """
    Handle Google OAuth callback.
    Exchanges authorization code for tokens and creates/updates user.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        """POST /api/users/google_callback/"""
        code = request.data.get("code")
        redirect_uri = request.data.get("redirect_uri")

        if not code:
            return Response(
                {"error": "Authorization code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Step 1: Exchange code for Google tokens ──────────────────────────
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

        if not token_response.ok:
            return Response(
                {"error": "Failed to exchange code with Google."},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_data = token_response.json()
        google_id_token_value = token_data.get("id_token")

        if not google_id_token_value:
            return Response(
                {"error": "No ID token returned from Google."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Step 2: Verify the ID token ──────────────────────────────────────
        try:
            user_info = id_token.verify_oauth2_token(
                google_id_token_value,
                google_requests.Request(),
                os.getenv("GOOGLE_CLIENT_ID"),
            )
        except ValueError as e:
            return Response(
                {"error": f"Invalid Google token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Step 3: Extract user info ────────────────────────────────────────
        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")
        email_verified = user_info.get("email_verified", False)

        if not email:
            return Response(
                {"error": "Could not retrieve email from Google."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email_verified:
            return Response(
                {"error": "Google email is not verified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Step 4: Find or create user ──────────────────────────────────────
        user, is_new = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )

        # Update name on every login in case it changed on Google
        if not is_new:
            if user.first_name != first_name or user.last_name != last_name:
                user.first_name = first_name
                user.last_name = last_name
                user.save()

        # ── Step 5: Fetch business and receipts ──────────────────────────────
        business = Business.objects.filter(owner=user).first()
        receipts_qs = Receipt.objects.filter(
            business=business
        ).order_by('-updated_at')[:50] if business else []
        receipts_data = ReceiptListSerializer(receipts_qs, many=True).data

        # ── Step 6: Generate JWT tokens ──────────────────────────────────────
        refresh = RefreshToken.for_user(user)
        refresh['orig_iat'] = int(timezone.now().timestamp())
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return Response({
            "user": UserSerializer(user).data,
            "business": BusinessSerializer(business).data if business else None,
            "receipts": receipts_data,
            "access": access_token,
            "refresh": refresh_token,
            "requires_password_change": user.requires_password_change,  # ← KEY FLAG
            "isNew": is_new,
            "message": "Google login successful",
        }, status=status.HTTP_200_OK)
        
        
class SessionLimitedTokenRefreshView(TokenRefreshView):
    serializer_class = SessionLimitedTokenRefreshSerializer
        