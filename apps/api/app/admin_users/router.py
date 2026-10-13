from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from ..auth.deps import require_admin
from ..auth.schemas import UserOut
from .repo import AdminUserRepo
from .schemas import AdminUserOut, AdminUserPage, AdminUserUpdate

router = APIRouter(prefix="/admin/users", tags=["admin"])

# engine (+ chat hub để cắt socket khi khoá) được set bởi main.py qua init_admin_users(engine, hub)
_engine: Engine | None = None
_hub = None


def init_admin_users(engine: Engine, hub=None) -> None:
    global _engine, _hub
    _engine, _hub = engine, hub


def get_repo() -> AdminUserRepo:
    if _engine is None:
        raise HTTPException(503, "Admin user repo chưa khởi tạo")
    return AdminUserRepo(_engine)


@router.get("", response_model=AdminUserPage)
def list_users(
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, pattern="^(user|admin)$"),
    locked: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: UserOut = Depends(require_admin),
    repo: AdminUserRepo = Depends(get_repo),
):
    total, items = repo.search(q, role, locked, page, size)
    return AdminUserPage(total=total, page=page, size=size, items=items)


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: UserOut = Depends(require_admin),
    repo: AdminUserRepo = Depends(get_repo),
):
    target = repo.get(user_id)
    if target is None:
        raise HTTPException(404, "Không tìm thấy người dùng")
    demote = body.role == "user" and target.role == "admin"
    lock = body.locked is True
    if user_id == admin.id and (demote or lock):
        raise HTTPException(400, "Không thể tự bỏ quyền admin hoặc tự khoá tài khoản của mình")
    # luôn còn ít nhất 1 admin hoạt động — mất hết admin thì không ai mở khoá/ quản lý tin được nữa (chỉ sửa được bằng SQL)
    if target.role == "admin" and (demote or lock) and repo.other_active_admins(user_id) == 0:
        raise HTTPException(400, "Phải còn ít nhất một admin đang hoạt động")
    repo.update(user_id, body.role, body.locked)
    if lock and _hub is not None:
        # REST đã bị chặn qua get_current_user; socket chat đang mở thì phải chủ động đóng (best-effort như mọi nhịp đẩy)
        _hub.publish([user_id], {"type": "account.locked"})
    return repo.get(user_id)
