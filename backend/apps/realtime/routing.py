from django.urls import path

from .consumers import OrganizationEventsConsumer

websocket_urlpatterns = [
    path("ws/v1/organizations/<slug:org_slug>/events/", OrganizationEventsConsumer.as_asgi()),
]
