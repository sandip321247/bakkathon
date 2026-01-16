from fastapi import WebSocket
from typing import Dict, List


class WSManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room, []).append(ws)

    def disconnect(self, room: str, ws: WebSocket):
        if room in self.rooms and ws in self.rooms[room]:
            self.rooms[room].remove(ws)

    async def broadcast(self, room: str, message: dict):
        if room not in self.rooms:
            return
        dead = []
        for ws in self.rooms[room]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)
