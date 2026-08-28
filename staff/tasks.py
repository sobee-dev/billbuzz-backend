from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3) # Retry up to 3 times if it fails
def send_staff_email_task(self, user_email, first_name, temp_password):
    try:
        send_mail(
            subject="Welcome to the Portal",
            message=f"Hi {first_name}, your password is {temp_password}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Email failed for {user_email}: {e}")
        # Automatically retry the task after 60 seconds
        raise self.retry(exc=e, countdown=60)