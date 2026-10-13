from sqlalchemy import text
from sqlalchemy.engine import Engine

from .schemas import AdminUserOut

_SELECT = """
    SELECT u.id, u.email, u.name, u.role, u.created_at, u.last_seen_at, (u.locked_at IS NOT NULL) AS locked,
           COALESCE(array_agg(DISTINCT i.provider) FILTER (WHERE i.provider IS NOT NULL), '{}') AS providers,
           max(i.provider_user_id) FILTER (WHERE i.provider = 'ctu') AS mssv,
           EXISTS (SELECT 1 FROM roommate_profiles p WHERE p.user_id = u.id) AS has_roommate_profile
    FROM users u LEFT JOIN user_identities i ON i.user_id = u.id
"""


class AdminUserRepo:
    """Quản lý người dùng cho admin (thuyết minh dòng 4). Khoá = users.locked_at (mig 101), không xoá tài khoản."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _where(self, q: str | None, role: str | None, locked: bool | None) -> tuple[str, dict]:
        clauses, params = ["TRUE"], {}
        if q:
            # tìm cả MSSV: SV thử nghiệm đăng nhập bằng MSSV, admin thường chỉ biết mã số
            clauses.append("(u.email ILIKE :q ESCAPE '\\' OR u.name ILIKE :q ESCAPE '\\' OR EXISTS (SELECT 1 "
                           "FROM user_identities x WHERE x.user_id = u.id AND x.provider_user_id ILIKE :q ESCAPE '\\'))")
            # "_"/"%" admin gõ là ký tự thường, không phải ký tự đại diện của LIKE
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params["q"] = f"%{escaped}%"
        if role:
            clauses.append("u.role = :role")
            params["role"] = role
        if locked is not None:
            clauses.append("(u.locked_at IS NOT NULL) = :locked")
            params["locked"] = locked
        return " AND ".join(clauses), params

    def search(self, q: str | None, role: str | None, locked: bool | None,
               page: int, size: int) -> tuple[int, list[AdminUserOut]]:
        where, params = self._where(q, role, locked)
        with self.engine.connect() as conn:
            total = conn.execute(text(f"SELECT count(*) FROM users u WHERE {where}"), params).scalar_one()
            rows = conn.execute(
                text(f"{_SELECT} WHERE {where} GROUP BY u.id ORDER BY u.created_at DESC NULLS LAST, u.id DESC "
                     "LIMIT :limit OFFSET :offset"),
                {**params, "limit": size, "offset": (page - 1) * size},
            ).mappings().all()
        return total, [AdminUserOut(**r) for r in rows]

    def get(self, user_id: int) -> AdminUserOut | None:
        with self.engine.connect() as conn:
            row = conn.execute(text(f"{_SELECT} WHERE u.id = :id GROUP BY u.id"), {"id": user_id}).mappings().first()
        return AdminUserOut(**row) if row else None

    def other_active_admins(self, user_id: int) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT count(*) FROM users WHERE role = 'admin' AND locked_at IS NULL AND id <> :id"),
                {"id": user_id},
            ).scalar_one()

    def update(self, user_id: int, role: str | None, locked: bool | None) -> None:
        sets, params = [], {"id": user_id}
        if role is not None:
            sets.append("role = :role")
            params["role"] = role
        if locked is not None:
            # giữ mốc khoá đầu tiên nếu khoá lại lần nữa
            sets.append("locked_at = CASE WHEN :locked THEN COALESCE(locked_at, now()) ELSE NULL END")
            params["locked"] = locked
        if not sets:
            return
        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE users SET {', '.join(sets)} WHERE id = :id"), params)
