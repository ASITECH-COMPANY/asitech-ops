"""ASGI entrypoint: HTTP is handled by Django, WebSockets by Channels."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Django must be initialised before importing anything that touches models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.realtime.routing import websocket_urlpatterns  # noqa: E402

# Browser routes are wrapped (origin check + session auth) in realtime/routing.py;
# agent routes authenticate with their own Ed25519 challenge.
application = ProtocolTypeRouter({"http": django_asgi_app, "websocket": URLRouter(websocket_urlpatterns)})
