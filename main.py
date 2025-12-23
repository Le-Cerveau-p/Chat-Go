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
from dotenv import load_dotenv
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload
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
from datetime import datetime


load_dotenv()


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


app = FastAPI(title=os.getenv("APP_NAME", "Echo"))

origins = os.getenv("CORS_ORIGINS", "").split(",")

# Allow browser dev origins (adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # React + Vite
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create DB tables (for dev)
models.Base.metadata.create_all(bind=db.engine)

presence_manager = PresenceManager()


def require_thread_admin(session, thread_id: int, user_id: int):
    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")

    # 🔹 Personal chats have no admins
    if not thread.is_group:
        return

    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=user_id)
        .first()
    )

    if not member or not member.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")


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
        dead_sockets = []

        for ws in self.rooms.get(thread_id, []):
            try:
                await ws.send_text(json.dumps(message))
            except RuntimeError:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            self.disconnect(thread_id, ws)


thread_manager = ThreadConnectionManager()


async def broadcast_global(message: dict):
    for sockets in presence_manager.online_users.values():
        for ws in sockets:
            await ws.send_text(json.dumps(message))


@app.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    user = await auth.get_current_user(token)
    await websocket.accept()

    try:
        is_first = presence_manager.connect(user.id, websocket)
        if is_first:
            await broadcast_global(
                {
                    "type": "presence",
                    "user_id": user.id,
                    "username": user.username,
                    "status": "online",
                }
            )
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

                msg_id = msg.id
                msg_content = msg.content
                reply_to_id = msg.reply_to_id
                forward_from_id = msg.forward_from_id
                user_username = user.username
                created_at = (msg.created_at.isoformat(),)

                members = (
                    session.query(models.ThreadMember)
                    .filter(models.ThreadMember.thread_id == thread_id)
                    .all()
                )

                for m in members:
                    if m.user_id != user.id:
                        session.add(
                            models.MessageReceipt(
                                message_id=msg.id,
                                user_id=m.user_id,
                                delivered_at=datetime.utcnow(),
                            )
                        )

                session.commit()
                session.close()

                await thread_manager.broadcast(
                    thread_id,
                    {
                        "type": "message",
                        "id": msg_id,
                        "thread_id": thread_id,
                        "sender": user_username,
                        "content": msg_content,
                        "reply_to_id": reply_to_id,
                        "forward_from_id": forward_from_id,
                        "created_at": created_at,
                    },
                )

            elif data["action"] == "typing_start":
                thread_id = data["thread_id"]

                await thread_manager.broadcast(
                    thread_id,
                    {
                        "type": "typing",
                        "thread_id": thread_id,
                        "user_id": user.id,
                        "username": user.username,
                        "is_typing": True,
                    },
                )

            elif data["action"] == "typing_stop":
                thread_id = data["thread_id"]

                await thread_manager.broadcast(
                    thread_id,
                    {
                        "type": "typing",
                        "thread_id": thread_id,
                        "user_id": user.id,
                        "username": user.username,
                        "is_typing": False,
                    },
                )

    except WebSocketDisconnect:
        is_offline = presence_manager.disconnect(user.id, websocket)

        if is_offline:
            await broadcast_global(
                {
                    "type": "presence",
                    "user_id": user.id,
                    "username": user.username,
                    "status": "offline",
                }
            )

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
    admin_status = False
    if data.is_group:
        admin_status = True

    member = models.ThreadMember(
        thread_id=thread.id, user_id=user.id, is_admin=admin_status
    )
    session.add(member)
    session.commit()

    return {"id": thread.id, "name": thread.name}


@app.get("/api/threads/personal/{user_id}")
async def get_personal_thread(user_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    thread = (
        session.query(models.ChatThread)
        .join(models.ThreadMember)
        .filter(
            models.ChatThread.is_group == False,
            models.ThreadMember.user_id.in_([user.id, user_id]),
        )
        .group_by(models.ChatThread.id)
        .having(func.count(models.ThreadMember.id) == 2)
        .first()
    )

    session.close()

    if not thread:
        return None

    return {"id": thread.id, "name": thread.name, "is_group": False}


@app.post("/api/threads/{thread_id}/read")
async def mark_thread_read(thread_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    # ensure membership
    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=user.id)
        .first()
    )
    if not member:
        session.close()
        raise HTTPException(403, "Not a thread member")

    # mark all delivered messages as read
    receipts = (
        session.query(models.MessageReceipt)
        .join(models.Message)
        .filter(
            models.Message.thread_id == thread_id,
            models.MessageReceipt.user_id == user.id,
            models.MessageReceipt.read_at.is_(None),
        )
        .all()
    )

    now = datetime.utcnow()
    for r in receipts:
        r.read_at = now

    session.commit()

    # Broadcast read receipt asynchronously
    asyncio.create_task(
        thread_manager.broadcast(
            thread_id,
            {
                "type": "read",
                "thread_id": thread_id,
                "user_id": user.id,
                "username": user.username,
                "read_at": now.isoformat(),
            },
        )
    )

    session.close()

    return {"status": "ok"}


@app.post("/api/threads/{thread_id}/members")
async def add_member(
    thread_id: int, data: schemas.AddMember, user=Depends(auth.get_current_user)
):
    session = db.SessionLocal()
    existing = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=data.user_id)
        .first()
    )

    if existing:
        return {"error": "User already in thread"}

    m = models.ThreadMember(
        thread_id=thread_id, user_id=data.user_id, is_admin=data.is_admin
    )
    session.add(m)
    session.commit()
    await presence_manager.send_to_user(
        data.user_id,
        {
            "type": "thread_added",
            "thread_id": thread_id,
        },
    )

    await broadcast_global(
        {
            "type": "thread_added",
            "thread_id": thread_id,
        }
    )

    session.close()
    return {"status": "added"}


@app.get("/api/threads/{thread_id}/members")
async def get_thread_members(thread_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    members = (
        session.query(models.ThreadMember)
        .join(models.User)
        .filter(models.ThreadMember.thread_id == thread_id)
        .all()
    )

    return [
        {"user_id": m.user_id, "username": m.user.username, "is_admin": m.is_admin}
        for m in members
    ]


@app.post("/api/threads/{thread_id}/leave")
async def leave_thread(thread_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=user.id)
        .first()
    )

    if not member:
        session.close()
        raise HTTPException(404, "Not a member of this thread")

    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()

    # 🔐 Group safety
    if thread.is_group and member.is_admin:
        admin_count = (
            session.query(models.ThreadMember)
            .filter_by(thread_id=thread_id, is_admin=True)
            .count()
        )

        if admin_count == 1:
            session.close()
            raise HTTPException(400, "You are the only admin. Promote someone first.")

    username = member.user.username
    session.delete(member)
    session.commit()
    session.close()

    await thread_manager.broadcast(
        thread_id,
        {"system": True, "message": f"{username} left"},
    )

    return {"status": "left thread"}


@app.post("/api/threads/{thread_id}/remove")
async def remove_member(
    thread_id: int,
    data: schemas.RemoveMember,
    user=Depends(auth.get_current_user),
):
    session = db.SessionLocal()
    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()
    if not thread.is_group:
        session.close()
        raise HTTPException(400, "Not a group thread")

    require_thread_admin(session, thread_id, user.id)

    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=data.user_id)
        .first()
    )

    if not member:
        session.close()
        raise HTTPException(404, "User not in thread")

    target = member.user.username

    session.delete(member)
    session.commit()
    session.close()
    await thread_manager.broadcast(
        thread_id,
        {
            "system": True,
            "message": f"{user.username} removed {target}",
            "type": "thread_updated",
            "thread_id": thread_id,
        },
    )

    return {"status": "member removed"}


@app.post("/api/threads/{thread_id}/promote")
async def promote_member(
    thread_id: int,
    data: schemas.PromoteMember,
    user=Depends(auth.get_current_user),
):
    session = db.SessionLocal()
    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()
    if not thread.is_group:
        session.close()
        raise HTTPException(400, "Not a group thread")
    require_thread_admin(session, thread_id, user.id)

    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=data.user_id)
        .first()
    )

    if not member:
        session.close()
        raise HTTPException(404, "User not found")

    member.is_admin = True

    target = member.user.username
    session.commit()
    session.close()
    await thread_manager.broadcast(
        thread_id,
        {
            "system": True,
            "message": f"{target} was promoted to admin",
            "type": "thread_updated",
            "thread_id": thread_id,
        },
    )

    return {"status": "promoted"}


@app.post("/api/threads/{thread_id}/demote")
async def demote_member(
    thread_id: int,
    data: schemas.DemoteMember,
    user=Depends(auth.get_current_user),
):
    session = db.SessionLocal()
    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()
    if not thread.is_group:
        session.close()
        raise HTTPException(400, "Not a group thread")
    require_thread_admin(session, thread_id, user.id)

    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=data.user_id)
        .first()
    )

    if not member or not member.is_admin:
        session.close()
        raise HTTPException(400, "User is not an admin")

    member.is_admin = False

    target = member.user.username
    session.commit()
    session.close()
    await thread_manager.broadcast(
        thread_id,
        {
            "system": True,
            "message": f"{target} was removed from admin",
            "type": "thread_updated",
            "thread_id": thread_id,
        },
    )

    return {"status": "demoted"}


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
    session = db.SessionLocal()

    users = (
        session.query(models.User)
        # .filter(models.User.id.in_(presence_manager.list_online_users()))
        .all()
    )

    session.close()

    return [{"id": u.id, "username": u.username} for u in users]


@app.post("/api/threads/{thread_id}/upload")
async def upload_file(
    thread_id: int, file: UploadFile = File(...), user=Depends(auth.get_current_user)
):
    session = db.SessionLocal()

    filename = safe_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)
    msg = models.Message(
        thread_id=thread_id,
        sender_id=user.id,
        file_path=file_path,
        file_name=file.filename,
        file_size=file_size,
    )

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
            "filename": msg.file_name,
            "file_size": msg.file_size,
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


@app.get("/api/files/{message_id}/preview")
def preview_file(message_id: int):
    session = db.SessionLocal()
    msg = session.query(models.Message).filter(models.Message.id == message_id).first()

    if not msg or not msg.file_path:
        session.close()
        raise HTTPException(404, "File not found")

    session.close()

    return FileResponse(msg.file_path, media_type="image/*")


@app.get("/api/messages/{message_id}")
def get_message(message_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()
    msg = session.query(models.Message).get(message_id)
    session.close()

    if not msg:
        raise HTTPException(404, "Message not found")

    return {
        "id": msg.id,
        "content": msg.content,
        "sender_id": msg.sender_id,
        "reply_to_id": msg.reply_to_id,
        "forward_from_id": msg.forward_from_id,
        "file_path": msg.file_path,
    }


@app.get("/api/threads/{thread_id}")
async def get_thread(thread_id: int, user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    # ensure user is a member
    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=user.id)
        .first()
    )

    if not member:
        session.close()
        raise HTTPException(403, "Not a member of this thread")

    thread = session.query(models.ChatThread).filter_by(id=thread_id).first()
    session.close()

    if not thread:
        raise HTTPException(404, "Thread not found")

    return {
        "id": thread.id,
        "name": thread.name,
        "is_group": thread.is_group,
    }


@app.get("/api/chats")
def get_chat_list(user=Depends(auth.get_current_user)):
    session = db.SessionLocal()

    threads = (
        session.query(
            models.ChatThread.id.label("thread_id"),
            models.ChatThread.name.label("thread_name"),
            models.ChatThread.is_group,
            func.max(models.Message.created_at).label("last_time"),
        )
        .join(
            models.ThreadMember, models.ThreadMember.thread_id == models.ChatThread.id
        )
        .outerjoin(models.Message, models.Message.thread_id == models.ChatThread.id)
        .filter(models.ThreadMember.user_id == user.id)
        .group_by(models.ChatThread.id)
        .order_by(desc("last_time"))
        .all()
    )

    result = []

    for t in threads:
        last_msg = (
            session.query(models.Message)
            .filter(models.Message.thread_id == t.thread_id)
            .order_by(models.Message.created_at.desc())
            .first()
        )

        unread_count = (
            session.query(models.MessageReceipt)
            .join(models.Message)
            .filter(
                models.Message.thread_id == t.thread_id,
                models.MessageReceipt.user_id == user.id,
                models.MessageReceipt.read_at.is_(None),
            )
            .count()
        )

        if not t.is_group:
            other = (
                session.query(models.User)
                .join(models.ThreadMember)
                .filter(
                    models.ThreadMember.thread_id == t.thread_id,
                    models.User.id != user.id,
                )
                .first()
            )
            name = other.username if other else "Chat"
        else:
            name = t.thread_name

        result.append(
            {
                "thread_id": t.thread_id,
                "name": name,
                "is_group": t.is_group,
                "last_message": last_msg.content if last_msg else None,
                "last_message_time": last_msg.created_at.isoformat()
                if last_msg
                else None,
                "unread_count": unread_count,
            }
        )

    session.close()
    return result


@app.get("/api/threads/{thread_id}/messages")
def get_thread_messages(
    thread_id: int,
    limit: int = 50,
    offset: int = 0,
    user=Depends(auth.get_current_user),
):
    session = db.SessionLocal()

    # Ensure membership
    member = (
        session.query(models.ThreadMember)
        .filter_by(thread_id=thread_id, user_id=user.id)
        .first()
    )
    if not member:
        session.close()
        raise HTTPException(403, "Not a member of this thread")

    messages = (
        session.query(models.Message)
        .options(joinedload(models.Message.sender))
        .filter(models.Message.thread_id == thread_id)
        .order_by(models.Message.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for m in messages:
        delivered_count = (
            session.query(models.MessageReceipt)
            .filter(models.MessageReceipt.message_id == m.id)
            .filter(models.MessageReceipt.delivered_at.isnot(None))
            .count()
        )

        read_count = (
            session.query(models.MessageReceipt)
            .filter(models.MessageReceipt.message_id == m.id)
            .filter(models.MessageReceipt.read_at.isnot(None))
            .count()
        )
        result.append(
            {
                "id": m.id,
                "thread_id": m.thread_id,
                "sender": m.sender.username if hasattr(m, "sender") else None,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "reply_to_id": m.reply_to_id,
                "forward_from_id": m.forward_from_id,
                "file_url": f"/api/files/{m.id}" if m.file_path else None,
                "filename": m.file_name if m.file_path else None,  # 👈 FIX
                "file_size": m.file_size if m.file_path else None,
                "type": "file" if m.file_path else "message",
                "delivered_count": delivered_count,
                "read_count": read_count,
            }
        )

    session.close()
    return result


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
