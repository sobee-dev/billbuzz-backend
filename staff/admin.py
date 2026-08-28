from django.contrib import admin

from .models import StaffMember

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "department", "permission_level", "status", "created_at"]
    list_filter = ["status", "permission_level", "created_at"]
    search_fields = ["user__email", "business__name", "department"]
    ordering = ["-created_at"]
    raw_id_fields = ["user", "business"]
    readonly_fields = ["created_at"]