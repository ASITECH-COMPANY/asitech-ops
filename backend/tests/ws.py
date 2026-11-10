"""Minimal ASGI WebSocket test client.

Equivalent to channels.testing.WebsocketCommunicator, which cannot be imported
without daphne (and Twisted), neither of which this project depends on.
"""

import json

from asgiref.testing import ApplicationCommunicator


class WebsocketClient(ApplicationCommunicator):
    def __init__(self, application, path: str, headers: list[tuple[bytes, bytes]] | None = None):
        scope = {
            "type": "websocket",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "subprotocols": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
        super().__init__(application, scope)

    async def connect(self, timeout: float = 3):
        await self.send_input({"type": "websocket.connect"})
        response = await self.receive_output(timeout)
        if response["type"] == "websocket.close":
            return False, response.get("code", 1000)
        return True, response.get("subprotocol")

    async def send_json_to(self, data) -> None:
        await self.send_input({"type": "websocket.receive", "text": json.dumps(data)})

    async def receive_json_from(self, timeout: float = 3):
        response = await self.receive_output(timeout)
        assert response["type"] == "websocket.send", response
        return json.loads(response["text"])

    async def disconnect(self, code: int = 1000, timeout: float = 3) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(timeout)
