from sqlalchemy import text
from sqlalchemy.engine import Engine


class AuthRepo:
    """users + user_identities. Multi-provider (local|google|ctu)."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def find_identity(self, provider: str, provider_user_id: str) -> dict | None:
        """Trả identity + user (role) đã join, hoặc None."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT i.id AS identity_id, i.secret_hash, "
                    "u.id AS user_id, u.email, u.name, u.role, u.locked_at "
                    "FROM user_identities i JOIN users u ON u.id = i.user_id "
                    "WHERE i.provider = :p AND i.provider_user_id = :pid"
                ),
                {"p": provider, "pid": provider_user_id},
            ).mappings().first()
        return dict(row) if row else None

    def get_user(self, user_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email, name, role, avatar_url, locked_at FROM users WHERE id = :id"),
                {"id": user_id},
            ).mappings().first()
        return dict(row) if row else None

    def create_user_with_identity(
        self,
        *,
        email: str,
        name: str | None,
        provider: str,
        provider_user_id: str,
        secret_hash: str | None,
        avatar_url: str | None = None,
        email_verified: bool = False,
    ) -> dict:
        """Tạo user + identity atomic. Raise nếu email/identity trùng (UNIQUE)."""
        with self.engine.begin() as conn:
            user_id = conn.execute(
                text(
                    "INSERT INTO users (email, name, avatar_url, email_verified) "
                    "VALUES (:email, :name, :avatar, :verified) RETURNING id"
                ),
                {"email": email, "name": name, "avatar": avatar_url, "verified": email_verified},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO user_identities (user_id, provider, provider_user_id, secret_hash) "
                    "VALUES (:uid, :p, :pid, :sh)"
                ),
                {"uid": user_id, "p": provider, "pid": provider_user_id, "sh": secret_hash},
            )
        return {"user_id": user_id, "email": email, "name": name, "role": "user"}

    def email_exists(self, email: str) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT 1 FROM users WHERE email = :e"), {"e": email}
            ).first() is not None
