from django.contrib.auth import login
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.core.csrf import CSRFEnforcedMixin
from apps.core.exceptions_api import Gone

from . import services
from .access import OrganizationScopedMixin
from .models import Invitation, Membership, Organization
from .roles import Perm, has_perm
from .serializers import (
    InvitationAcceptSerializer,
    InvitationCreatedSerializer,
    InvitationCreateSerializer,
    InvitationPreviewSerializer,
    InvitationSerializer,
    InvitationTokenSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
)


def _member_count_subquery():
    return Subquery(
        Membership.objects.filter(organization=OuterRef("pk"))
        .order_by()
        .values("organization")
        .annotate(c=Count("pk"))
        .values("c"),
        output_field=IntegerField(),
    )


@extend_schema(tags=["organizations"])
class OrganizationListCreateView(generics.ListAPIView):
    serializer_class = OrganizationSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()
        mine = Membership.objects.filter(organization=OuterRef("pk"), user=self.request.user)
        return (
            Organization.objects.filter(memberships__user=self.request.user)
            .annotate(my_role=Subquery(mine.values("role")[:1]), member_count=_member_count_subquery())
            .order_by("name")
        )

    @extend_schema(request=OrganizationCreateSerializer, responses={201: OrganizationSerializer})
    def post(self, request):
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = services.create_organization(
            user=request.user,
            name=serializer.validated_data["name"],
            slug=serializer.validated_data.get("slug") or None,
            request=request,
        )
        organization.my_role = Membership.objects.get(organization=organization, user=request.user).role
        organization.member_count = 1
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["organizations"])
class OrganizationDetailView(OrganizationScopedMixin, APIView):
    permission_map = {"GET": Perm.ORG_VIEW, "PATCH": Perm.ORG_UPDATE, "DELETE": Perm.ORG_DELETE}

    def _serialize(self):
        org = self.organization
        org.my_role = self.membership.role
        org.member_count = Membership.objects.filter(organization=org).count()
        return OrganizationSerializer(org).data

    @extend_schema(responses=OrganizationSerializer)
    def get(self, request, org_slug):
        return Response(self._serialize())

    @extend_schema(request=OrganizationUpdateSerializer, responses=OrganizationSerializer)
    def patch(self, request, org_slug):
        serializer = OrganizationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_organization(
            self.organization, name=serializer.validated_data["name"], request=request
        )
        return Response(self._serialize())

    @extend_schema(responses={204: None})
    def delete(self, request, org_slug):
        services.delete_organization(self.organization, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["members"],
    parameters=[OpenApiParameter("search", str, description="Filter by e-mail or name")],
)
class MemberListView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = MemberSerializer
    permission_map = {"GET": Perm.MEMBERS_VIEW}

    def get_queryset(self):
        if self.is_schema_generation():
            return Membership.objects.none()
        qs = Membership.objects.filter(organization=self.organization).select_related("user")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(user__email__icontains=search) | Q(user__full_name__icontains=search))
        return qs.order_by("created_at")


@extend_schema(tags=["members"])
class MemberDetailView(OrganizationScopedMixin, APIView):
    # DELETE is checked in the handler: members may always leave on their own.
    permission_map = {"PATCH": Perm.MEMBERS_MANAGE, "DELETE": None}

    def _get_member(self, member_id) -> Membership:
        member = Membership.objects.filter(organization=self.organization, pk=member_id).first()
        if member is None:
            raise NotFound()
        return member

    @extend_schema(request=MemberUpdateSerializer, responses=MemberSerializer)
    def patch(self, request, org_slug, member_id):
        member = self._get_member(member_id)
        serializer = MemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.change_member_role(
            member, new_role=serializer.validated_data["role"], actor=self.membership, request=request
        )
        return Response(MemberSerializer(member).data)

    @extend_schema(responses={204: None})
    def delete(self, request, org_slug, member_id):
        member = self._get_member(member_id)
        if member.pk != self.membership.pk and not has_perm(self.membership.role, Perm.MEMBERS_MANAGE):
            raise PermissionDenied("Your role in this organization does not allow this action.")
        services.remove_member(member, actor=self.membership, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["invitations"],
    parameters=[
        OpenApiParameter("status", str, enum=["pending", "all"], description="Default: pending"),
    ],
)
class InvitationListCreateView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = InvitationSerializer
    permission_map = {"GET": Perm.INVITATIONS_MANAGE, "POST": Perm.INVITATIONS_MANAGE}

    def get_queryset(self):
        if self.is_schema_generation():
            return Invitation.objects.none()
        qs = Invitation.objects.filter(organization=self.organization).select_related("invited_by")
        if self.request.query_params.get("status", "pending") == "pending":
            qs = qs.pending()
        return qs.order_by("-created_at")

    @extend_schema(request=InvitationCreateSerializer, responses={201: InvitationCreatedSerializer})
    def post(self, request, org_slug):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation, raw_token = services.create_invitation(
            self.organization,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            actor=self.membership,
            request=request,
        )
        # The accept link is returned once, so administrators can share it when
        # no SMTP server is configured. It is never retrievable again.
        invitation.accept_url = services.build_accept_url(raw_token)
        return Response(InvitationCreatedSerializer(invitation).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["invitations"])
class InvitationRevokeView(OrganizationScopedMixin, APIView):
    permission_map = {"DELETE": Perm.INVITATIONS_MANAGE}

    @extend_schema(responses={204: None})
    def delete(self, request, org_slug, invitation_id):
        invitation = Invitation.objects.filter(organization=self.organization, pk=invitation_id).first()
        if invitation is None:
            raise NotFound()
        services.revoke_invitation(invitation, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _invitation_or_404(token: str) -> Invitation:
    invitation = services.get_invitation_by_token(token)
    if invitation is None:
        raise NotFound("This invitation link is invalid.")
    return invitation


@extend_schema(tags=["invitations"])
class InvitationPreviewView(APIView):
    """Show who invited whom, before accepting. The token is sent in the body."""

    permission_classes = [AllowAny]
    throttle_scope = "invitation"

    @extend_schema(request=InvitationTokenSerializer, responses=InvitationPreviewSerializer)
    def post(self, request):
        serializer = InvitationTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = _invitation_or_404(serializer.validated_data["token"])
        data = {
            "organization": {"name": invitation.organization.name, "slug": invitation.organization.slug},
            "email": invitation.email,
            "role": invitation.role,
            "status": invitation.status,
            "expires_at": invitation.expires_at,
            "invited_by": invitation.invited_by.display_name if invitation.invited_by else None,
            "account_exists": User.objects.filter(email=invitation.email).exists(),
        }
        return Response(InvitationPreviewSerializer(data).data)


@extend_schema(tags=["invitations"])
class InvitationAcceptView(CSRFEnforcedMixin, APIView):
    """Accept an invitation.

    Signed-in users accept for their own address. Anonymous visitors whose
    address has no account yet create one (name + password) and are signed in.
    """

    permission_classes = [AllowAny]
    throttle_scope = "invitation"

    @extend_schema(request=InvitationAcceptSerializer, responses=OrganizationSerializer)
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = _invitation_or_404(serializer.validated_data["token"])
        if invitation.status != Invitation.Status.PENDING:
            raise Gone(f"This invitation is {invitation.status}.")

        user = request.user
        if not user.is_authenticated:
            if User.objects.filter(email=invitation.email).exists():
                raise NotAuthenticated("Sign in with the invited e-mail address to accept this invitation.")
            full_name = serializer.validated_data.get("full_name", "").strip()
            password = serializer.validated_data.get("password") or ""
            errors = {}
            if not full_name:
                errors["full_name"] = ["This field is required."]
            if not password:
                errors["password"] = ["This field is required."]
            if errors:
                raise ValidationError(errors)
            try:
                serializer.validate_password_for(invitation.email, full_name, password)
            except DjangoValidationError as exc:
                raise ValidationError({"password": list(exc.messages)}) from exc
            user = User.objects.create_user(email=invitation.email, password=password, full_name=full_name)
            membership = services.accept_invitation(invitation, user=user, request=request)
            login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        else:
            membership = services.accept_invitation(invitation, user=user, request=request)

        org = membership.organization
        org.my_role = membership.role
        org.member_count = Membership.objects.filter(organization=org).count()
        data = OrganizationSerializer(org).data
        data["user"] = UserSerializer(user, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)
