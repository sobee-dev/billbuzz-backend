from django.db import models

import uuid

from django.conf import settings
from django.db import models


class PushToken(models.Model):
    """
    One row per device push token. A user can have several active
    tokens at once (multiple devices signed into the same account) —
    the unique constraint lives on the token itself, not per-user,
    since an Expo push token identifies a single device+app install
    and should only ever belong to whoever is currently logged in on
    that device.
    """

    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_tokens',
    )
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.platform or 'unknown'} ({self.token[:24]}…)"
