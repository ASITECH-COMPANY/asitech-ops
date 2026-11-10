from django.contrib import admin

from .models import Invitation, Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    inlines = [MembershipInline]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "status", "expires_at", "created_at"]
    list_filter = ["role"]
    search_fields = ["email", "organization__name"]
    readonly_fields = [f.name for f in Invitation._meta.fields]

    def has_add_permission(self, request):
        return False
