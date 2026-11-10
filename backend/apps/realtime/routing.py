from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from apps.servers.consumers import AgentConsumer

from .consumers import OrganizationEventsConsumer


def browser(app):
    """Dashboard sockets: same-origin only, authenticated by the session cookie."""
    return AllowedHostsOriginValidator(AuthMiddlewareStack(app))


websocket_urlpatterns = [
    path("ws/v1/organizations/<slug:org_slug>/events/", browser(OrganizationEventsConsumer.as_asgi())),
    # Agents are not browsers (no Origin, no cookies): they prove their identity
    # with a signed challenge inside the connection.
    path("ws/agent/v1/connect/", AgentConsumer.as_asgi()),
]
