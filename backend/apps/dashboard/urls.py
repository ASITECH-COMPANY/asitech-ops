from django.urls import path

from .views import DashboardView, MonitoringView

urlpatterns = [
    path("organizations/<slug:org_slug>/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("organizations/<slug:org_slug>/monitoring/", MonitoringView.as_view(), name="monitoring"),
]
