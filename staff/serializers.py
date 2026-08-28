# staff/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
import secrets
from .models import StaffMember, Invitation
import random
import string

User = get_user_model()


# ============================================
# 1. StaffMember Detail Serializer
# ============================================
class StaffMemberSerializer(serializers.ModelSerializer):
    """
    Full serializer for StaffMember model.
    Includes related user information.
    """
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    requires_password_change = serializers.CharField(source='user.requires_password_change', read_only=True)
    password_changed_at = serializers.CharField(source='user.password_changed_at', read_only=True)
    is_online = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'department',
            'permission_level',
            'status',
            'requires_password_change',
            'password_changed_at',
            'is_online',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'requires_password_change',
            'password_changed_at',
            'is_online',
            'created_at',
            'updated_at',
        ]

    def get_full_name(self, obj):
        """Get staff member full name"""
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.email


# ============================================
# 2. StaffMember List Serializer
# ============================================
class StaffMemberListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing staff members.
    Used in tables and dashboards.
    """
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    requires_password_change = serializers.CharField(source='user.requires_password_change', read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'department',
            'permission_level',
            'status',
            'requires_password_change',
            'created_at',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        """Get staff member full name"""
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.email


# ============================================
# 3. Create Staff Serializer
# ============================================
class CreateStaffSerializer(serializers.Serializer):
    """
    Owner creates a staff account with placeholder password.
    Staff will be prompted to change password on first login.
    """
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    permission_level = serializers.ChoiceField(
        choices=StaffMember.PERMISSION_CHOICES,
        default='limited_access'
    )

    def validate_email(self, value):
        """Check if email is already registered"""
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        """Create User and StaffMember"""
        # Generate random 6 dgt placeholder password
        temp_password = ''.join(random.choices(string.digits, k=6))
        
        owner = self.context['request'].user
        business = owner.business
        
        # Create User with role='staff'
        user = User.objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=temp_password,
            role='staff',
            requires_password_change=True,  # ← Flag for first login
            is_active=True,
        )
        
        # Create StaffMember entry
        staff_member = StaffMember.objects.create(
            user=user,
            business=business,
            department=validated_data.get('department', ''),
            temp_password=temp_password,
            permission_level=validated_data.get('permission_level', 'limited_access'),
            status='active'
        )
        
        return staff_member


# ============================================
# 4. Invitation Serializer
# ============================================
class InvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for Invitation model.
    Shows invitation details to owners.
    """
    class Meta:
        model = Invitation
        fields = [
            'id',
            'email',
            'token',
            'is_accepted',
            'created_at',
            'accepted_at',
        ]
        read_only_fields = [
            'id',
            'token',
            'created_at',
            'accepted_at',
        ]


# ============================================
# 5. Create Invitation Serializer
# ============================================
class CreateInvitationSerializer(serializers.Serializer):
    """
    Owner invites a staff member via email link.
    Alternative to direct staff creation.
    """
    email = serializers.EmailField()
    permission_level = serializers.ChoiceField(
        choices=StaffMember.PERMISSION_CHOICES,
        default='limited_access',
        required=False
    )

    def validate_email(self, value):
        """Check if email is already registered"""
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        
        # Check if invitation already exists and is not accepted
        business = self.context['request'].user.business
        existing = Invitation.objects.filter(
            email=value,
            business=business,
            is_accepted=False
        ).exists()
        
        if existing:
            raise serializers.ValidationError("An invitation for this email already exists.")
        
        return value

    def create(self, validated_data):
        """Create invitation"""
        business = self.context['request'].user.business
        token = secrets.token_urlsafe(32)
        
        invitation = Invitation.objects.create(
            email=validated_data['email'],
            business=business,
            token=token,
            is_accepted=False
        )
        
        return invitation


# ============================================
# 6. Accept Invitation Serializer
# ============================================
class AcceptInvitationSerializer(serializers.Serializer):
    """
    Staff accepts invitation and creates account with password.
    Alternative to direct staff creation flow.
    """
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_token(self, value):
        """Verify token exists and is not accepted"""
        try:
            self.invitation = Invitation.objects.get(token=value, is_accepted=False)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired invitation token.")
        return value

    def validate(self, attrs):
        """Validate password fields"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        
        # Validate password strength
        try:
            validate_password(attrs['password'])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})
        
        return attrs

    def create(self, validated_data):
        """Create user from invitation"""
        # Create user
        user = User.objects.create_user(
            email=self.invitation.email,
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role='staff',
            is_active=True,
        )
        
        # Create staff member
        staff_member = StaffMember.objects.create(
            user=user,
            business=self.invitation.business,
            department=validated_data.get('department', ''),
            permission_level=StaffMember.PERMISSION_CHOICES[1][0],  # limited_access
            status='active'
        )
        
        # Mark invitation as accepted
        from django.utils import timezone
        self.invitation.is_accepted = True
        self.invitation.accepted_at = timezone.now()
        self.invitation.save()
        
        return user


# ============================================
# 7. Invite Staff Serializer (Legacy)
# ============================================
class InviteStaffSerializer(serializers.Serializer):
    """
    Legacy serializer for inviting staff.
    Kept for backward compatibility.
    """
    email = serializers.EmailField()
    permission_level = serializers.ChoiceField(choices=StaffMember.PERMISSION_CHOICES)

    def validate_email(self, value):
        """Check if email exists"""
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


# ============================================
# 8. Accept Invite Serializer (Legacy)
# ============================================
class AcceptInviteSerializer(serializers.Serializer):
    """
    Legacy serializer for accepting invitation.
    Kept for backward compatibility.
    """
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    department = serializers.CharField(required=False, allow_blank=True)

    def validate_token(self, value):
        """Verify token"""
        try:
            self.invitation = Invitation.objects.get(token=value, is_accepted=False)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired token.")
        return value

    def validate_password(self, value):
        """Validate password"""
        try:
            validate_password(value)
        except serializers.ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    
    
    # ============================================
# 9. Owner-only Update Serializer
# ============================================
class StaffMemberUpdateSerializer(serializers.ModelSerializer):
    """
    Owner-only serializer for editing a staff member's department and
    permission level. Identity fields (email, name) and status live
    elsewhere (StaffMember is a read-only proxy for those; status has
    its own dedicated activate/deactivate actions) — kept out of this
    serializer so there's exactly one way to change each thing.
    """
    class Meta:
        model = StaffMember
        fields = ['department', 'permission_level']