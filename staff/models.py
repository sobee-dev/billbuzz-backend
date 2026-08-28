from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import uuid

from receipt_backend_api import settings


class StaffMember(models.Model):
    """
    Staff member profile linked to a business.
    One staff member per user per business (via unique_together).
    """
    
    PERMISSION_CHOICES = [
        ('managerial_access', 'Managerial Access'),
        ('limited_access', 'Limited Access'),
    ]
    
    
 
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
 
    # User relationship (foreign key for multiple staff entries per user across businesses)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_accounts',
        help_text="The user who is a staff member"
    )
    
    temp_password = models.CharField(max_length=6, null=True, blank=True)
    
    password_changed = models.BooleanField(default=False)
    
    # Business relationship
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='staff_members',
        help_text="The business this staff member belongs to"
    )
    
    # Staff details
    department = models.CharField(max_length=100, blank=True)
    permission_level = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default='limited_access'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    is_online = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['-created_at']
        unique_together = [['user', 'business']]
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['user', 'business']),
        ]
 
    def __str__(self):
        return f"{self.user.get_full_name()} @ {self.business.name}"
 
    @property
    def full_name(self):
        """Get staff member full name"""
        return self.user.get_full_name()
 
    @property
    def email(self):
        """Get staff member email"""
        return self.user.email
    
    
class Invitation(models.Model):
    """
    Email-based invitation for staff members.
    Allows owner to invite someone via email before creating an account.
    """
    
    # Invitation details
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    
    # Relationship
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    
    # Status
    is_accepted = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        ordering = ['-created_at']
        unique_together = [['email', 'business']]
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['email']),
        ]
 
    def __str__(self):
        return f"Invitation for {self.email} @ {self.business.name}"