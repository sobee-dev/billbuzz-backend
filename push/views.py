from django.shortcuts import render

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import RegisterTokenSerializer, UnregisterTokenSerializer


class PushTokenViewSet(viewsets.ViewSet):
    """
    Not a ModelViewSet — there's no list/retrieve use case for push
    tokens from the client side (a device only ever registers or
    unregisters its own token). Same "custom action" shape used in
    staff/views.py for the same reason.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        POST /api/push/register/
        Body: { "expoPushToken": "...", "platform": "ios" | "android" }

        Call this after login, and again any time Expo issues a fresh
        token (it does happen occasionally). update_or_create in the
        serializer makes repeat calls with the same token harmless.
        """
        serializer = RegisterTokenSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        token_obj = serializer.save()
        return Response(
            {'message': 'Push token registered.', 'id': str(token_obj.id)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def unregister(self, request):
        """
        POST /api/push/unregister/
        Body: { "expoPushToken": "..." }

        Call this on logout so a signed-out device stops receiving
        pushes meant for the account it just left. Doesn't error if
        the token isn't found — logout shouldn't fail over push
        bookkeeping.
        """
        serializer = UnregisterTokenSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {'message': 'Token not registered; nothing to do.'},
                status=status.HTTP_200_OK,
            )
        serializer.save()
        return Response({'message': 'Push token unregistered.'}, status=status.HTTP_200_OK)