from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    role: str
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    locked: bool = False
    providers: list[str] = []          # local | google | ctu
    mssv: str | None = None            # provider_user_id của identity 'ctu' (chỉ admin thấy)
    has_roommate_profile: bool = False


class AdminUserPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[AdminUserOut]


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    locked: bool | None = None
