from fastapi import WebSocket


class PresenceManager:
    def __init__(self):
        self.online_users = {}  # user_id -> set of websockets

    def connect(self, user_id: int, websocket: WebSocket):
        self.online_users.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.online_users:
            self.online_users[user_id].discard(websocket)
            if not self.online_users[user_id]:
                del self.online_users[user_id]

    def list_online_users(self):
        return list(self.online_users.keys())
