"""Per-organization event stream for the dashboard.

Clients only receive *what changed* (action + resource) and refetch through the
REST API, which applies the normal permission checks. Membership is re-checked
for every event, so a removed member stops receiving events immediately.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.audit.services import organization_group
from apps.organizations.models import Membership

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403


@database_sync_to_async
def _membership(user_id, org_slug=None, org_id=None):
    qs = Membership.objects.select_related("organization").filter(user_id=user_id)
    qs = qs.filter(organization__slug=org_slug) if org_slug else qs.filter(organization_id=org_id)
    return qs.first()


class OrganizationEventsConsumer(AsyncJsonWebsocketConsumer):
    group_name: str | None = None

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHORIZED)
            return
        membership = await _membership(user.pk, org_slug=self.scope["url_route"]["kwargs"]["org_slug"])
        if membership is None:
            await self.close(code=CLOSE_FORBIDDEN)
            return
        self.user_id = user.pk
        self.organization_id = membership.organization_id
        self.group_name = organization_group(self.organization_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "hello", "organization": membership.organization.slug})

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # The stream is server -> client only; answer pings to keep proxies happy.
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def org_event(self, event):
        membership = await _membership(self.user_id, org_id=self.organization_id)
        if membership is None:
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.send_json({"type": "event", "action": event["action"], "resource": event["resource"]})
