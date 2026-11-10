from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from .models import Membership
from .roles import Perm, has_perm


def get_membership(user, org_slug: str) -> Membership:
    """Return the caller's membership, or 404.

    Non-members get 404 rather than 403 so organization slugs cannot be
    enumerated by other tenants.
    """
    if not user.is_authenticated:
        raise Http404
    membership = (
        Membership.objects.select_related("organization", "user")
        .filter(user=user, organization__slug=org_slug)
        .first()
    )
    if membership is None:
        raise Http404
    return membership


class OrganizationScopedMixin:
    """Resolves ``self.organization`` / ``self.membership`` and checks permissions.

    ``permission_map`` maps HTTP methods to the permission required. A method
    mapped to ``None`` performs its own check (e.g. "leave organization").
    """

    org_url_kwarg = "org_slug"
    permission_map: dict[str, Perm | None] = {}

    organization = None
    membership = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.membership = get_membership(request.user, kwargs[self.org_url_kwarg])
        self.organization = self.membership.organization
        method = request.method.upper()
        if method in self.permission_map:
            perm = self.permission_map[method]
        elif method in ("GET", "HEAD", "OPTIONS"):
            perm = Perm.ORG_VIEW
        else:
            raise PermissionDenied()
        if perm is not None and not has_perm(self.membership.role, perm):
            raise PermissionDenied("Your role in this organization does not allow this action.")

    def is_schema_generation(self) -> bool:
        return getattr(self, "swagger_fake_view", False)
