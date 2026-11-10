from django.urls import path

from . import views

base = "organizations/<slug:org_slug>/servers/"

urlpatterns = [
    path(base, views.ServerListCreateView.as_view(), name="server-list"),
    path(f"{base}<uuid:server_id>/", views.ServerDetailView.as_view(), name="server-detail"),
    path(f"{base}<uuid:server_id>/revoke/", views.ServerRevokeView.as_view(), name="server-revoke"),
    path(
        f"{base}<uuid:server_id>/enrollment/", views.ServerEnrollmentView.as_view(), name="server-enrollment"
    ),
    path(f"{base}<uuid:server_id>/metrics/", views.ServerMetricsView.as_view(), name="server-metrics"),
    path(f"{base}<uuid:server_id>/inventory/", views.ServerInventoryView.as_view(), name="server-inventory"),
    path(
        f"{base}<uuid:server_id>/operations/", views.ServerOperationsView.as_view(), name="server-operations"
    ),
    path(
        f"{base}<uuid:server_id>/operations/<uuid:operation_id>/",
        views.ServerOperationDetailView.as_view(),
        name="server-operation",
    ),
    path(
        f"{base}<uuid:server_id>/container-policy/",
        views.ServerContainerPolicyView.as_view(),
        name="server-container-policy",
    ),
]
