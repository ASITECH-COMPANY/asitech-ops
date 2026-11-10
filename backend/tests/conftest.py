import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.roles import Role

PASSWORD = "correct-horse-battery-staple-42"  # gitleaks:allow (test fixture)


@pytest.fixture(autouse=True)
def _clear_cache():
    # Throttle counters live in the cache.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(email=None, password=PASSWORD, **extra):
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.test"
        return User.objects.create_user(email=email, password=password, **extra)

    return _make


@pytest.fixture
def make_org(db):
    def _make(owner, name="Acme", slug=None, members=()):
        org = Organization.objects.create(
            name=name, slug=slug or name.lower().replace(" ", "-"), created_by=owner
        )
        Membership.objects.create(organization=org, user=owner, role=Role.OWNER)
        for user, role in members:
            Membership.objects.create(organization=org, user=user, role=role)
        return org

    return _make


@pytest.fixture
def client_for():
    def _client(user):
        client = APIClient()
        client.force_login(user)
        return client

    return _client


@pytest.fixture
def team(make_user, make_org):
    """An organization with one user per role, plus an outsider in another org."""
    owner = make_user("owner@acme.test")
    admin = make_user("admin@acme.test")
    member = make_user("member@acme.test")
    viewer = make_user("viewer@acme.test")
    org = make_org(owner, members=[(admin, Role.ADMIN), (member, Role.MEMBER), (viewer, Role.VIEWER)])
    outsider = make_user("outsider@globex.test")
    other_org = make_org(outsider, name="Globex")
    return {
        "org": org,
        "other_org": other_org,
        "owner": owner,
        "admin": admin,
        "member": member,
        "viewer": viewer,
        "outsider": outsider,
    }


def membership(org, user) -> Membership:
    return Membership.objects.get(organization=org, user=user)
