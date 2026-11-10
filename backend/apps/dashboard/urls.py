from django.urls import path

from .views import DashboardView

urlpatterns = [
    path("organizations/<slug:org_slug>/dashboard/", DashboardView.as_view(), name="dashboard"),
]
