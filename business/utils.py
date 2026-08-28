# business/utils.py
from .models import Business
from staff.models import StaffMember

def get_user_business(user):
    """Resolve the Business a user operates within, regardless of role."""
    if hasattr(user, 'business'):
        return user.business
    staff_profile = (
        StaffMember.objects
        .filter(user=user, status='active')
        .select_related('business')
        .first()
    )
    return staff_profile.business if staff_profile else None