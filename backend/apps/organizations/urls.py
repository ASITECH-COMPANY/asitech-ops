from django.urls import path

from . import views

urlpatterns = [
    path("organizations/", views.OrganizationListCreateView.as_view(), name="organization-list"),
    path(
        "organizations/<slug:org_slug>/", views.OrganizationDetailView.as_view(), name="organization-detail"
    ),
    path("organizations/<slug:org_slug>/members/", views.MemberListView.as_view(), name="member-list"),
    path(
        "organizations/<slug:org_slug>/members/<uuid:member_id>/",
        views.MemberDetailView.as_view(),
        name="member-detail",
    ),
    path(
        "organizations/<slug:org_slug>/invitations/",
        views.InvitationListCreateView.as_view(),
        name="invitation-list",
    ),
    path(
        "organizations/<slug:org_slug>/invitations/<uuid:invitation_id>/",
        views.InvitationRevokeView.as_view(),
        name="invitation-detail",
    ),
    path("invitations/preview/", views.InvitationPreviewView.as_view(), name="invitation-preview"),
    path("invitations/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
]
