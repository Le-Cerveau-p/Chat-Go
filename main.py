from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio


app = FastAPI()


# Allow browser dev origins (adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")


# Simple health route
@app.get("/api/health")
async def health():
    return JSONResponse({"status": "ok"})


# In-memory connection manager for demo (replace with Redis for scale)
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections[username] = websocket

    async def disconnect(self, username: str):
        async with self.lock:
            self.active_connections.pop(username, None)

    async def send_personal_message(self, message: str, username: str):
        ws = self.active_connections.get(username)
        if ws:
            await ws.send_text(message)

    async def broadcast(self, message: str):
        async with self.lock:
            for ws in list(self.active_connections.values()):
                await ws.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        await manager.broadcast(f"{username} joined")
        while True:
            data = await websocket.receive_text()
            # handle simple commands: "who" to list online users
            if data == "who":
                users = list(manager.active_connections.keys())
                await websocket.send_text("ONLINE:" + ",".join(users))
            else:
                # echo as broadcast for demo
                await manager.broadcast(f"{username}: {data}")
    except WebSocketDisconnect:
        await manager.disconnect(username)
        await manager.broadcast(f"{username} left")


# Serve a simple index page
@app.get("/")
async def get_index(request: Request):
    html = open("static/index.html", "r").read()
    return HTMLResponse(html)
