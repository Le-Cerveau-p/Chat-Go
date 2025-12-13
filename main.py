from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    Depends,
    HTTPException,
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import db, models, auth, schemas
import asyncio
import uvicorn


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


@app.get("/")
async def get_index(request: Request):
    html = open("static/index.html", "r").read()
    return HTMLResponse(html)


@app.post("/api/threads")
async def create_thread(
    data: schemas.CreateThread, user=Depends(auth.get_current_user)
):
    thread = models.ChatThread(
        name=data.name, is_group=data.is_group, created_by=user.id
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    member = models.ThreadMember(thread_id=thread.id, user_id=user.id, is_admin=True)
    db.add(member)
    db.commit()

    return {"id": thread.id, "name": thread.name}


@app.post("/api/threads/{thread_id}/members")
async def add_member(
    thread_id: int, data: schemas.AddMember, user=Depends(auth.get_current_user)
):
    m = models.ThreadMember(
        thread_id=thread_id, user_id=data.user_id, is_admin=data.is_admin
    )
    db.add(m)
    db.commit()
    return {"status": "added"}


@app.post("/api/messages")
async def send_message(data: schemas.SendMessage, user=Depends(auth.get_current_user)):
    msg = models.Message(
        thread_id=data.thread_id,
        sender_id=user.id,
        content=data.content,
        reply_to_id=data.reply_to_id,
        forward_from_id=data.forward_from_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "content": msg.content}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
