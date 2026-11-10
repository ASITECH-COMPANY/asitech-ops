import re

from django.contrib.auth import password_validation
from rest_framework import serializers

from apps.accounts.models import User

from .models import Invitation, Membership, Organization
from .roles import Role, permissions_for

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])?$")


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "created_at", "role", "permissions", "member_count"]
        read_only_fields = ["id", "slug", "created_at"]

    def _role(self, obj) -> str | None:
        role = getattr(obj, "my_role", None)
        if role is None:
            role = self.context.get("role")
        return role

    def get_role(self, obj) -> str | None:
        return self._role(obj)

    def get_permissions(self, obj) -> list[str]:
        role = self._role(obj)
        return permissions_for(role) if role else []


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    slug = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Use at least 2 characters.")
        return value.strip()

    def validate_slug(self, value: str) -> str:
        value = value.strip().lower()
        if value and not SLUG_RE.match(value):
            raise serializers.ValidationError(
                "Use 3-60 lowercase letters, digits or hyphens, starting and ending with a letter or digit."
            )
        return value


class OrganizationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Use at least 2 characters.")
        return value.strip()


class MemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name"]
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)
    joined_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "joined_at"]
        read_only_fields = ["id", "user", "joined_at"]


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    invited_by = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "status", "invited_by", "created_at", "expires_at"]
        read_only_fields = fields

    def get_invited_by(self, obj) -> str | None:
        return obj.invited_by.email if obj.invited_by else None


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.MEMBER)


class InvitationCreatedSerializer(InvitationSerializer):
    accept_url = serializers.CharField(read_only=True)

    class Meta(InvitationSerializer.Meta):
        fields = [*InvitationSerializer.Meta.fields, "accept_url"]
        read_only_fields = fields


class InvitationTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128, trim_whitespace=True)


class InvitationPreviewSerializer(serializers.Serializer):
    organization = serializers.DictField(child=serializers.CharField())
    email = serializers.EmailField()
    role = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    invited_by = serializers.CharField(allow_null=True)
    account_exists = serializers.BooleanField()


class InvitationAcceptSerializer(InvitationTokenSerializer):
    """Anonymous visitors without an account provide a name and a password."""

    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    def validate_password_for(self, email: str, full_name: str, password: str) -> None:
        candidate = User(email=email, full_name=full_name)
        password_validation.validate_password(password, user=candidate)
