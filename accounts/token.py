# accounts/tokens.py
from datetime import datetime, timedelta, timezone as dt_timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

MAX_SESSION_AGE = timedelta(days=14)


class SessionLimitedTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        orig_iat = refresh.get('orig_iat')

        # Tokens issued before this feature shipped won't have the claim —
        # treat those as already expired rather than granting them an
        # unbounded session by default.
        if orig_iat is None:
            raise serializers.ValidationError('Session expired. Please log in again.')

        issued_at = datetime.fromtimestamp(orig_iat, tz=dt_timezone.utc)
        if datetime.now(dt_timezone.utc) - issued_at > MAX_SESSION_AGE:
            raise serializers.ValidationError('Session expired. Please log in again.')

        return super().validate(attrs)