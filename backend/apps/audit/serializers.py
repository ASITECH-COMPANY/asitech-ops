from rest_framework import serializers

from .models import AuditLog


class AuditActorSerializer(serializers.Serializer):
    id = serializers.UUIDField(allow_null=True)
    email = serializers.EmailField(allow_blank=True)


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "action",
            "actor",
            "target_type",
            "target_id",
            "target_repr",
            "metadata",
            "ip_address",
        ]
        read_only_fields = fields

    def get_actor(self, obj) -> dict:
        return {"id": obj.actor_id, "email": obj.actor_email}
