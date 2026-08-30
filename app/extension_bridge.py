import asyncio
import json
import uuid

from fastapi import WebSocket

_PENDING_TIMEOUT = 20.0


class ExtensionNotConnected(Exception):
    pass


class ExtensionCommandError(Exception):
    pass


class ExtensionManager:
    def __init__(self) -> None:
        self._socket: WebSocket | None = None
        self._pending: dict[str, asyncio.Future] = {}

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    async def register(self, websocket: WebSocket) -> None:
        self._socket = websocket

    def unregister(self, websocket: WebSocket) -> None:
        if self._socket is websocket:
            self._socket = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ExtensionNotConnected("Extension đã ngắt kết nối."))
        self._pending.clear()

    async def handle_response(self, message: dict) -> None:
        request_id = message.get("request_id")
        future = self._pending.pop(request_id, None)
        if future and not future.done():
            future.set_result(message)

    async def send_command(self, action: str, payload: dict, timeout: float = _PENDING_TIMEOUT) -> dict:
        if self._socket is None:
            raise ExtensionNotConnected("Chưa có extension nào kết nối tới backend.")

        request_id = uuid.uuid4().hex[:8]
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        await self._socket.send_text(
            json.dumps({"request_id": request_id, "action": action, **payload}, ensure_ascii=False)
        )

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)

        if "error" in result:
            raise ExtensionCommandError(str(result["error"]))
        return result


extension_manager = ExtensionManager()
