from django.contrib import admin

from .models import AgentCredential, Server


class AgentCredentialInline(admin.TabularInline):
    model = AgentCredential
    extra = 0
    can_delete = False
    readonly_fields = ["fingerprint", "created_at", "revoked_at"]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "status", "environment", "last_seen_at"]
    list_filter = ["status", "environment"]
    search_fields = ["name", "organization__name"]
    readonly_fields = [
        "status",
        "facts",
        "last_seen_at",
        "last_ip",
        "enrolled_at",
        "created_by",
        "created_at",
    ]
    exclude = ["connection_id"]
    inlines = [AgentCredentialInline]
