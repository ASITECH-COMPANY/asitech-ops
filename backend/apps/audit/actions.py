"""Catalogue of audit actions. Keep values stable: they are stored in the database."""

from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password_changed"  # noqa: S105 (an action name, not a secret)
    PROFILE_UPDATED = "user.profile_updated"

    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"

    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    MEMBER_LEFT = "member.left"

    INVITATION_CREATED = "invitation.created"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_ACCEPTED = "invitation.accepted"

    SERVER_CREATED = "server.created"
    SERVER_UPDATED = "server.updated"
    SERVER_ENROLLMENT_TOKEN_CREATED = "server.enrollment_token_created"  # noqa: S105 (action name)
    SERVER_ENROLLED = "server.enrolled"
    SERVER_REVOKED = "server.revoked"
    SERVER_DELETED = "server.deleted"


# Which dashboard resource an action affects. Used by the real-time channel so
# clients know what to refresh, without leaking audit details to every member.
ACTION_RESOURCE = {
    AuditAction.ORGANIZATION_CREATED: "organization",
    AuditAction.ORGANIZATION_UPDATED: "organization",
    AuditAction.ORGANIZATION_DELETED: "organization",
    AuditAction.MEMBER_ROLE_CHANGED: "members",
    AuditAction.MEMBER_REMOVED: "members",
    AuditAction.MEMBER_LEFT: "members",
    AuditAction.INVITATION_CREATED: "invitations",
    AuditAction.INVITATION_REVOKED: "invitations",
    AuditAction.INVITATION_ACCEPTED: "members",
    AuditAction.SERVER_CREATED: "servers",
    AuditAction.SERVER_UPDATED: "servers",
    AuditAction.SERVER_ENROLLMENT_TOKEN_CREATED: "servers",
    AuditAction.SERVER_ENROLLED: "servers",
    AuditAction.SERVER_REVOKED: "servers",
    AuditAction.SERVER_DELETED: "servers",
}
