from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.actions import AuditAction
from apps.audit.services import record
from apps.core.csrf import CSRFEnforcedMixin

from .models import normalize_email
from .serializers import (
    CSRFTokenSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)
from .throttles import LoginEmailRateThrottle


@extend_schema(tags=["auth"])
class CSRFView(APIView):
    """Sets the CSRF cookie. The dashboard calls it once before any unsafe request."""

    permission_classes = [AllowAny]

    @extend_schema(responses=CSRFTokenSerializer)
    def get(self, request):
        return Response({"csrf_token": get_token(request._request)})


@extend_schema(tags=["auth"])
class LoginView(CSRFEnforcedMixin, APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def get_throttles(self):
        return [*super().get_throttles(), LoginEmailRateThrottle()]

    @extend_schema(request=LoginSerializer, responses=UserSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = normalize_email(serializer.validated_data["email"])
        user = authenticate(request._request, username=email, password=serializer.validated_data["password"])
        if user is None:
            record(AuditAction.LOGIN_FAILED, request=request, metadata={"email": email})
            # Same message whether the account exists or not.
            raise ValidationError({"non_field_errors": ["Invalid e-mail address or password."]})
        login(request._request, user)  # rotates the session key
        record(AuditAction.LOGIN, request=request, actor=user)
        return Response(UserSerializer(user).data)


@extend_schema(tags=["auth"])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        record(AuditAction.LOGOUT, request=request)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changed = sorted(k for k, v in serializer.validated_data.items() if getattr(request.user, k) != v)
        serializer.save()
        if changed:
            record(AuditAction.PROFILE_UPDATED, request=request, metadata={"fields": changed})
        return Response(UserSerializer(request.user).data)


@extend_schema(tags=["auth"])
class PasswordChangeView(APIView):
    throttle_scope = "password"

    @extend_schema(request=PasswordChangeSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        # Keep this session, invalidate every other session of the user.
        update_session_auth_hash(request._request, request.user)
        record(AuditAction.PASSWORD_CHANGED, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
