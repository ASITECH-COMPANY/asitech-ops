"""Role-based access control for organizations.

Roles are ordered: owner > admin > member > viewer. Each permission is granted
to an explicit set of roles so the matrix stays auditable in one place.
Future phases add permissions (servers, deployments...) here.
"""

from enum import StrEnum

from django.db import models


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


ROLE_RANK = {Role.VIEWER: 10, Role.MEMBER: 20, Role.ADMIN: 30, Role.OWNER: 40}


class Perm(StrEnum):
    ORG_VIEW = "organization.view"
    ORG_UPDATE = "organization.update"
    ORG_DELETE = "organization.delete"
    MEMBERS_VIEW = "members.view"
    MEMBERS_MANAGE = "members.manage"
    INVITATIONS_MANAGE = "invitations.manage"
    AUDIT_VIEW = "audit.view"
    SERVERS_VIEW = "servers.view"
    # Registering or revoking a server grants Docker (root-equivalent) control over it.
    SERVERS_MANAGE = "servers.manage"
    APPS_VIEW = "applications.view"
    APPS_MANAGE = "applications.manage"  # create/edit apps and their environment variables
    APPS_DEPLOY = "applications.deploy"  # deploy and roll back


_ALL = frozenset(Role)
_ADMINS = frozenset({Role.OWNER, Role.ADMIN})

ROLE_PERMISSIONS: dict[Perm, frozenset[Role]] = {
    Perm.ORG_VIEW: _ALL,
    Perm.MEMBERS_VIEW: _ALL,
    Perm.ORG_UPDATE: _ADMINS,
    Perm.MEMBERS_MANAGE: _ADMINS,
    Perm.INVITATIONS_MANAGE: _ADMINS,
    Perm.AUDIT_VIEW: _ADMINS,
    Perm.ORG_DELETE: frozenset({Role.OWNER}),
    Perm.SERVERS_VIEW: _ALL,
    Perm.SERVERS_MANAGE: _ADMINS,
    Perm.APPS_VIEW: _ALL,
    Perm.APPS_MANAGE: _ADMINS,
    Perm.APPS_DEPLOY: frozenset({Role.OWNER, Role.ADMIN, Role.MEMBER}),
}


def has_perm(role: str | None, perm: Perm) -> bool:
    return role is not None and Role(role) in ROLE_PERMISSIONS[perm]


def permissions_for(role: str) -> list[str]:
    return sorted(str(perm) for perm, roles in ROLE_PERMISSIONS.items() if Role(role) in roles)


def can_assign_role(actor_role: str, target_current_role: str | None, new_role: str) -> bool:
    """Admins manage non-owners; only owners can grant, change or remove the owner role."""
    actor = Role(actor_role)
    if actor == Role.OWNER:
        return True
    if actor != Role.ADMIN:
        return False
    if Role(new_role) == Role.OWNER:
        return False
    return target_current_role is None or Role(target_current_role) != Role.OWNER
