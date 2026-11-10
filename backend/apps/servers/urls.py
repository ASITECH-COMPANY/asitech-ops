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
]
