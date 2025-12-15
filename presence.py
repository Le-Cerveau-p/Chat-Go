from fastapi import WebSocket


class PresenceManager:
    def __init__(self):
        self.online_users = {}  # user_id -> set of websockets

    def connect(self, user_id: int, websocket: WebSocket):
        first_connection = user_id not in self.online_users
        self.online_users.setdefault(user_id, set()).add(websocket)
        return first_connection

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.online_users:
            self.online_users[user_id].discard(websocket)
            if not self.online_users[user_id]:
                del self.online_users[user_id]
                return True
        return False

    def list_online_users(self):
        return list(self.online_users.keys())
