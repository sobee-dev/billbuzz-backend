# accounts/models.py
# ============================================
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import uuid
 
 
class UserManager(BaseUserManager):
    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
 
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)
 
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra_fields)
 
 
class User(AbstractUser):
    """
    Custom user model with role-based access and password change tracking.
    
    - Owners: Have a OneToOne Business relationship
    - Staff: Can belong to a business via StaffMember
    - Admins: System administrators
    """
    
    ROLE_CHOICES = [
        ('owner', 'Business Owner'),
        ('staff', 'Staff'),
        # ('admin', 'Admin'),
    ]
 
    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Authentication
    username = None  # Removed for email-only login
    email = models.EmailField(unique=True)
    
    # User info
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    
    # Role and permissions
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='owner'
    )
    
    # Email verification
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Password change on first login (for new staff)
    requires_password_change = models.BooleanField(
        default=False,
        help_text="Staff must change password on first login"
    )
    password_changed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom manager
    objects = UserManager()
    
    # Django auth
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
 
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
        ]
 
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
 
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
 
    @property
    def is_owner(self):
        """Check if user is a business owner"""
        return self.role == 'owner'
 
    @property
    def is_staff_member(self):
        """Check if user is a staff member"""
        return self.role == 'staff'