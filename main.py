from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    UploadFile,
    File,
    Depends,
    HTTPException,
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import db, models, auth, schemas
from typing import Dict, Set
from presence import PresenceManager
import json
import asyncio
import uvicorn
import os
import uuid
import shutil
import re
import random
from pathlib import Path

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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

# Create DB tables (for dev)
models.Base.metadata.create_all(bind=db.engine)

presence_manager = PresenceManager()


def safe_filename(original: str) -> str:
    name = Path(original).stem
    ext = Path(original).suffix

    # remove weird chars
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    suffix = random.randint(1000, 9999)
    return f"{name}_{suffix}{ext}"


@app.post("/api/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate):
    session = db.SessionLocal()
    existing = (
        session.query(models.User).filter(models.User.username == user.username).first()
    )
    if existing:
        session.close()
        raise HTTPException(status_code=400, detail="Username already taken")
    hashed = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    session.close()
    return db_user


@app.post("/api/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    session = db.SessionLocal()
    user = auth.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"sub": user.username})
    session.close()
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me", response_model=schemas.UserOut)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# Connection manager unchanged but we validate token on WS connect
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

    async def broadcast(self, message: str):
        async with self.lock:
            for ws in list(self.active_connections.values()):
                await ws.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket):
    # Expect token as query param: ?token=...
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        user = await auth.get_current_user(token)
    except Exception:
        await websocket.close(code=1008)
        return
    username = user.username
    await manager.connect(username, websocket)
    try:
        await manager.broadcast(f"{username} joined")
        while True:
            data = await websocket.receive_text()
            if data == "who":
                users = list(manager.active_connections.keys())
                await websocket.send_text("ONLINE:" + ",".join(users))
            else:
                await manager.broadcast(f"{username}: {data}")
    except WebSocketDisconnect:
        await manager.disconnect(username)
        await manager.broadcast(f"{username} left")


class ThreadConnectionManager:
    def __init__(self):
        self.rooms: Dict[int, Set[WebSocket]] = {}

    async def connect(self, thread_id: int, websocket: WebSocket):
        self.rooms.setdefault(thread_id, set()).add(websocket)

    def disconnect(self, thread_id: int, websocket: WebSocket):
        if thread_id in self.rooms:
            self.rooms[thread_id].discard(websocket)
            if not self.rooms[thread_id]:
                del self.rooms[thread_id]

    async def broadcast(self, thread_id: int, message: dict):
        for ws in self.rooms.get(thread_id, []):
            await ws.send_text(json.dumps(message))


thread_manager = ThreadConnectionManager()


@app.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        user = await auth.get_current_user(token)
        presence_manager.connect(user.id, websocket)
    except Exception:
        await websocket.close(code=1008)
        return

    joined_threads = set()

    try:
        while True:
            data = json.loads(await websocket.receive_text())

            if data["action"] == "join":
                thread_id = data["thread_id"]
                await thread_manager.connect(thread_id, websocket)
                joined_threads.add(thread_id)

                await thread_manager.broadcast(
                    thread_id,
                    {"system": True, "message": f"{user.username} joined thread"},
                )

            elif data["action"] == "message":
                thread_id = data["thread_id"]
                content = data["content"]

                session = db.SessionLocal()
                msg = models.Message(
                    thread_id=thread_id,
                    sender_id=user.id,
                    content=content,
                    reply_to_id=data.get("reply_to_id"),
                    forward_from_id=data.get("forward_from_id"),
                )
                session.add(msg)
                session.commit()
                session.refresh(msg)
                session.close()

                await thread_manager.broadcast(
                    thread_id,
                    {
                        "type": "message",
                        "id": msg.id,
                        "thread_id": thread_id,
                        "sender": user.username,
                        "content": msg.content,
                        "reply_to_id": msg.reply_to_id,
                        "forward_from_id": msg.forward_from_id,
                    },
                )

    except WebSocketDisconnect:
        presence_manager.disconnect(user.id, websocket)
        print(f"User {user.username} went offline")
        for tid in joined_threads:
            thread_manager.disconnect(tid, websocket)


@app.get("/")
async def get_index(request: Request):
    html = open("static/index.html", "r").read()
    return HTMLResponse(html)


@app.post("/api/threads")
async def create_thread(
    data: schemas.CreateThread, user=Depends(auth.get_current_user)
):
    session = db.SessionLocal()
    thread = models.ChatThread(
        name=data.name, is_group=data.is_group, created_by=user.id
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)

    member = models.ThreadMember(thread_id=thread.id, user_id=user.id, is_admin=True)
    session.add(member)
    session.commit()

    return {"id": thread.id, "name": thread.name}


@app.post("/api/threads/{thread_id}/members")
async def add_member(
    thread_id: int, data: schemas.AddMember, user=Depends(auth.get_current_user)
):
    session = db.SessionLocal()
    m = models.ThreadMember(
        thread_id=thread_id, user_id=data.user_id, is_admin=data.is_admin
    )
    session.add(m)
    session.commit()
    return {"status": "added"}


@app.post("/api/messages")
async def send_message(data: schemas.SendMessage, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()
    msg = models.Message(
        thread_id=data.thread_id,
        sender_id=user.id,
        content=data.content,
        reply_to_id=data.reply_to_id,
        forward_from_id=data.forward_from_id,
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return {"id": msg.id, "content": msg.content}


@app.get("/api/online-users")
def get_online_users(current_user=Depends(auth.get_current_user)):
    return {"online_user_ids": presence_manager.list_online_users()}


@app.post("/api/threads/{thread_id}/upload")
async def upload_file(
    thread_id: int, file: UploadFile = File(...), user=Depends(auth.get_current_user)
):
    session = db.SessionLocal()

    ext = file.filename.split(".")[-1]
    filename = safe_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    msg = models.Message(thread_id=thread_id, sender_id=user.id, file_path=file_path)

    session.add(msg)
    session.commit()
    session.refresh(msg)
    session.close()

    # 🔥 BROADCAST FILE MESSAGE HERE
    await thread_manager.broadcast(
        thread_id,
        {
            "type": "file",
            "id": msg.id,
            "thread_id": thread_id,
            "sender": user.username,
            "file_url": f"/api/files/{msg.id}",
        },
    )

    return {"id": msg.id, "file_url": f"/api/files/{msg.id}"}


@app.get("/api/files/{message_id}")
def get_file(message_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    msg = session.query(models.Message).filter(models.Message.id == message_id).first()

    if not msg or not msg.file_path:
        session.close()
        raise HTTPException(status_code=404, detail="File not found")

    session.close()

    return FileResponse(msg.file_path, filename=os.path.basename(msg.file_path))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
