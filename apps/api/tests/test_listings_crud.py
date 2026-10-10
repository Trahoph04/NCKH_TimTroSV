"""E2E tests cho quản lý tin bằng tay — CHỈ admin (ADR-024: sinh viên không đăng tin).

Chạy với Postgres thật (DATABASE_URL trỏ vào docker network `db`), không mock DB.
Mỗi test tự đăng ký user mới (email random) để tránh đụng độ 409 giữa các lần chạy; admin = user vừa đăng ký
rồi nâng role trong DB (get_current_user đọc role từ DB, không từ token).
"""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app, engine

client = TestClient(app)


def _register(admin: bool = False) -> dict:
    """Đăng ký user mới (email random) -> {headers, user_id}; admin=True thì nâng role."""
    email = f"crud_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    user_id = me.json()["id"]
    if admin:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
    return {"email": email, "headers": headers, "user_id": user_id}


def _listing_payload(**overrides) -> dict:
    payload = {
        "title": f"Phong tro test {uuid4().hex[:6]}",
        "price": 2000000,
        "area": 25.5,
        "address": "Xuan Khanh, Ninh Kieu, Can Tho",
        "district": "Ninh Kieu",
    }
    payload.update(overrides)
    return payload


def _create(admin: dict) -> int:
    r = client.post("/listings", json=_listing_payload(), headers=admin["headers"])
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_admin_create_listing_persists_with_owner():
    admin = _register(admin=True)
    payload = _listing_payload()

    r = client.post("/listings", json=payload, headers=admin["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == payload["title"]
    assert body["price"] == payload["price"]
    assert body["source"] == "user"

    got = client.get(f"/listings/{body['id']}")
    assert got.status_code == 200, got.text
    assert got.json()["district"] == payload["district"]

    # posted_by qua DB trực tiếp (ListingOut không expose posted_by)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT posted_by, status FROM aggregated_listings WHERE id = :id"),
            {"id": body["id"]},
        ).mappings().first()
    assert row["posted_by"] == admin["user_id"]
    assert row["status"] == "active"


def test_student_cannot_create_listing():
    student = _register()
    r = client.post("/listings", json=_listing_payload(), headers=student["headers"])
    assert r.status_code == 403, r.text


def test_create_listing_requires_auth():
    r = client.post("/listings", json=_listing_payload())
    # HTTPBearer(auto_error=True) trả 403 "Not authenticated" khi thiếu header Authorization
    assert r.status_code == 403, r.text


def test_admin_updates_manual_listing():
    admin = _register(admin=True)
    listing_id = _create(admin)

    new_title = f"Updated title {uuid4().hex[:6]}"
    r = client.put(f"/listings/{listing_id}", json={"title": new_title, "price": 3000000},
                   headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["title"] == new_title

    got = client.get(f"/listings/{listing_id}")
    assert got.json()["price"] == 3000000


def test_another_admin_can_update_manual_listing():
    # tin nhập tay là của nhóm, không của riêng admin tạo ra
    listing_id = _create(_register(admin=True))
    other = _register(admin=True)
    r = client.put(f"/listings/{listing_id}", json={"title": "Sửa bởi admin khác"}, headers=other["headers"])
    assert r.status_code == 200, r.text


def test_student_cannot_update_listing():
    listing_id = _create(_register(admin=True))
    student = _register()
    r = client.put(f"/listings/{listing_id}", json={"title": "hijacked"}, headers=student["headers"])
    assert r.status_code == 403, r.text


def test_update_missing_listing_404():
    admin = _register(admin=True)
    r = client.put("/listings/999999999", json={"title": "no such listing"}, headers=admin["headers"])
    assert r.status_code == 404, r.text


def test_update_pipeline_listing_conflict():
    """Tin crawl/khảo sát không sửa tay — lần crawl/import sau sẽ ghi đè."""
    admin = _register(admin=True)
    with engine.begin() as conn:
        listing_id = conn.execute(text(
            "INSERT INTO aggregated_listings (title, source, source_id, price) "
            "VALUES ('Tin crawl test', 'phongtro123', :sid, 1500000) RETURNING id"),
            {"sid": f"test-{uuid4().hex[:8]}"}).scalar_one()
    r = client.put(f"/listings/{listing_id}", json={"title": "sửa tay"}, headers=admin["headers"])
    assert r.status_code == 409, r.text
    # nhưng ẩn thì được (crawler không bật lại tin 'hidden')
    assert client.delete(f"/listings/{listing_id}", headers=admin["headers"]).status_code == 204


def test_admin_hide_listing():
    admin = _register(admin=True)
    listing_id = _create(admin)

    r = client.delete(f"/listings/{listing_id}", headers=admin["headers"])
    assert r.status_code == 204, r.text

    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM aggregated_listings WHERE id = :id"), {"id": listing_id}
        ).scalar_one()
    assert status == "hidden"

    assert client.get(f"/listings/{listing_id}").status_code == 404
    ids = [item["id"] for item in client.get("/listings").json()["items"]]
    assert listing_id not in ids


def test_student_cannot_hide_listing():
    listing_id = _create(_register(admin=True))
    student = _register()
    r = client.delete(f"/listings/{listing_id}", headers=student["headers"])
    assert r.status_code == 403, r.text


def test_managed_listings_admin_only():
    admin = _register(admin=True)
    listing_id = _create(admin)

    r = client.get("/listings/managed", headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert listing_id in [item["id"] for item in r.json()]

    student = _register()
    assert client.get("/listings/managed", headers=student["headers"]).status_code == 403
