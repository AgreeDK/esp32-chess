import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # game_id → liste af (websocket, device_name) tuples
        self._rooms: dict[str, list[tuple[WebSocket, str]]] = {}

    def join_room(self, websocket: WebSocket, game_id: str, device_name: str = "ukendt"):
        self._rooms.setdefault(game_id, []).append((websocket, device_name))
        count = len(self._rooms[game_id])
        logger.info(f"[{game_id}] '{device_name}' i rum ({count} forbundet)")

    def disconnect(self, websocket: WebSocket, game_id: str):
        room = self._rooms.get(game_id, [])
        self._rooms[game_id] = [(ws, name) for ws, name in room if ws is not websocket]
        if not self._rooms[game_id]:
            self._rooms.pop(game_id, None)

    def players_in_room(self, game_id: str) -> list[str]:
        return [name for _, name in self._rooms.get(game_id, [])]

    async def send(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    async def broadcast(self, game_id: str, data: dict, exclude: WebSocket | None = None):
        for ws, _ in self._rooms.get(game_id, []):
            if ws is not exclude:
                await ws.send_json(data)
