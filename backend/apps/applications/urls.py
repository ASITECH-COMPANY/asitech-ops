from django.urls import path

from . import views

apps = "organizations/<slug:org_slug>/applications/"
deployments = "organizations/<slug:org_slug>/deployments/"

urlpatterns = [
    path(apps, views.ApplicationListCreateView.as_view(), name="application-list"),
    path(f"{apps}<uuid:app_id>/", views.ApplicationDetailView.as_view(), name="application-detail"),
    path(f"{apps}<uuid:app_id>/environment/", views.EnvironmentView.as_view(), name="application-env"),
    path(
        f"{apps}<uuid:app_id>/deployments/",
        views.ApplicationDeploymentsView.as_view(),
        name="app-deployments",
    ),
    path(deployments, views.DeploymentListView.as_view(), name="deployment-list"),
    path(
        f"{deployments}<uuid:deployment_id>/", views.DeploymentDetailView.as_view(), name="deployment-detail"
    ),
    path(
        f"{deployments}<uuid:deployment_id>/logs/", views.DeploymentLogsView.as_view(), name="deployment-logs"
    ),
    path(
        f"{deployments}<uuid:deployment_id>/rollback/",
        views.DeploymentRollbackView.as_view(),
        name="deployment-rollback",
    ),
]
