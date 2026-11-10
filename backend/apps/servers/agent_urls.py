from django.urls import path

from .views import AgentEnrollView

urlpatterns = [
    path("enroll/", AgentEnrollView.as_view(), name="agent-enroll"),
]
