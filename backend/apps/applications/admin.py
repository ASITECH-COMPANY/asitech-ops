from django.contrib import admin

from .models import Application, Deployment


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "server", "build_type", "branch", "created_at"]
    list_filter = ["build_type"]
    search_fields = ["name", "slug", "repo_url"]
    exclude = ["repo_token_encrypted"]


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ["application", "number", "status", "trigger", "is_current", "created_at", "finished_at"]
    list_filter = ["status", "trigger"]
    readonly_fields = [f.name for f in Deployment._meta.fields]

    def has_add_permission(self, request):
        return False
