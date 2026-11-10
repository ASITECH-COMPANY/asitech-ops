from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    can_create_organizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "language",
            "is_staff",
            "date_joined",
            "can_create_organizations",
        ]
        read_only_fields = ["id", "email", "is_staff", "date_joined", "can_create_organizations"]

    def get_can_create_organizations(self, obj) -> bool:
        from apps.organizations.services import can_create_organizations

        return can_create_organizations(obj)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "language"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"}, max_length=256)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, max_length=256)
    new_password = serializers.CharField(write_only=True, max_length=256)

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value, user=self.context["request"].user)
        return value


class CSRFTokenSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
