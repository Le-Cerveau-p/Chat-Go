from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]

    class Config:
        orm_mode = True


class CreateThread(BaseModel):
    name: str
    is_group: bool = False


class AddMember(BaseModel):
    user_id: int
    is_admin: bool = False


class SendMessage(BaseModel):
    thread_id: int
    content: Optional[str] = None
    reply_to_id: Optional[int] = None
    forward_from_id: Optional[int] = None


class RemoveMember(BaseModel):
    user_id: int


class PromoteMember(BaseModel):
    user_id: int


class DemoteMember(BaseModel):
    user_id: int
