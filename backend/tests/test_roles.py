import pytest

from apps.organizations.roles import Perm, Role, can_assign_role, has_perm


@pytest.mark.parametrize(
    ("role", "perm", "allowed"),
    [
        (Role.VIEWER, Perm.ORG_VIEW, True),
        (Role.VIEWER, Perm.MEMBERS_MANAGE, False),
        (Role.MEMBER, Perm.AUDIT_VIEW, False),
        (Role.ADMIN, Perm.AUDIT_VIEW, True),
        (Role.ADMIN, Perm.ORG_DELETE, False),
        (Role.OWNER, Perm.ORG_DELETE, True),
    ],
)
def test_permission_matrix(role, perm, allowed):
    assert has_perm(role, perm) is allowed


def test_no_role_has_no_permission():
    assert has_perm(None, Perm.ORG_VIEW) is False


@pytest.mark.parametrize(
    ("actor", "current", "new", "allowed"),
    [
        (Role.OWNER, Role.OWNER, Role.ADMIN, True),
        (Role.OWNER, Role.MEMBER, Role.OWNER, True),
        (Role.ADMIN, Role.MEMBER, Role.ADMIN, True),
        (Role.ADMIN, Role.MEMBER, Role.OWNER, False),
        (Role.ADMIN, Role.OWNER, Role.MEMBER, False),
        (Role.ADMIN, None, Role.VIEWER, True),
        (Role.MEMBER, Role.VIEWER, Role.MEMBER, False),
        (Role.VIEWER, None, Role.VIEWER, False),
    ],
)
def test_role_assignment_rules(actor, current, new, allowed):
    assert can_assign_role(actor, current, new) is allowed
