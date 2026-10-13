"""Đánh giá nhà trọ của SV (app/reviews, mig 90 + 102): 1 đánh giá/tài khoản/tin, tóm tắt điểm + tag, chặn SĐT/link,
admin ẩn được và sửa lại không tự hiện; điểm hiện trên ListingOut. Chạy trên nckh_test."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app, engine
from app.ratelimit import _hits

client = TestClient(app)
SRC = "test-reviews"


def _register(admin: bool = False) -> dict:
    email = f"review_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123", "name": "Trần Hoàng Phú"})
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    if admin:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
    return {"headers": headers, "id": user_id}


def _listing(status: str = "active") -> int:
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO aggregated_listings (title, price, source, source_id, cleaning_status, listing_type, status) "
                 "VALUES ('Phòng trọ test đánh giá', 2000000, :s, :sid, 'cleaned', 'phong_tro', :st) RETURNING id"),
            {"s": SRC, "sid": uuid4().hex[:12], "st": status},
        ).scalar_one()


def teardown_module():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM aggregated_listings WHERE source = :s"), {"s": SRC})
    _hits.clear()


def _post(lid: int, user: dict, **body):
    payload = {"rating": 4, "tags": [], "relation": "dang_o", **body}
    return client.post(f"/listings/{lid}/reviews", json=payload, headers=user["headers"])


def test_review_requires_login_and_visible_listing():
    lid = _listing()
    assert client.post(f"/listings/{lid}/reviews", json={"rating": 5, "relation": "dang_o"}).status_code == 403
    hidden = _listing(status="hidden")
    assert _post(hidden, _register()).status_code == 404
    assert client.get(f"/listings/{hidden}/reviews").status_code == 404


def test_one_review_per_user_summary_and_listing_rating():
    lid, a, b = _listing(), _register(), _register()
    r = _post(lid, a, rating=2, tags=["coc_khong_tra", "on_ao"], content="Chủ giữ cọc khi trả phòng sớm")
    assert r.status_code == 200, r.text
    assert r.json()["author"] == "Phú T.H."  # tên rút gọn, không lộ họ tên đầy đủ
    _post(lid, a, rating=3, tags=["coc_khong_tra"])  # gửi lại = sửa, không thành 2 đánh giá
    _post(lid, b, rating=5, tags=["chu_tot", "sach_se"], relation="da_o")

    body = client.get(f"/listings/{lid}/reviews").json()
    s = body["summary"]
    assert s["total"] == 2 and s["average"] == 4.0
    assert s["rating_counts"] == {"3": 1, "5": 1}
    assert s["tag_counts"] == {"coc_khong_tra": 1, "chu_tot": 1, "sach_se": 1}
    listing = client.get(f"/listings/{lid}").json()
    assert listing["rating_avg"] == 4.0 and listing["rating_count"] == 2


def test_review_validation():
    lid, user = _listing(), _register()
    assert _post(lid, user, rating=6).status_code == 422
    assert _post(lid, user, tags=["khong_co_tag_nay"]).status_code == 422
    assert _post(lid, user, relation="ban_be").status_code == 422
    assert _post(lid, user, content="Liên hệ 0901 234 567 để thuê").status_code == 422
    assert _post(lid, user, content="Xem thêm tại zalo.me/abc").status_code == 422


def test_admin_hides_review_and_edit_does_not_unhide():
    lid, user, admin = _listing(), _register(), _register(admin=True)
    review_id = _post(lid, user, rating=1, content="Nội dung vi phạm").json()["id"]
    assert client.get("/admin/reviews", headers=user["headers"]).status_code == 403
    assert client.patch(f"/admin/reviews/{review_id}", json={"status": "hidden"},
                        headers=admin["headers"]).status_code == 204
    assert client.get(f"/listings/{lid}/reviews").json()["summary"]["total"] == 0

    _post(lid, user, rating=5)  # sửa lại sau khi bị ẩn ⇒ vẫn ẩn
    assert client.get(f"/listings/{lid}/reviews").json()["summary"]["total"] == 0
    assert client.get(f"/listings/{lid}/reviews/mine", headers=user["headers"]).json()["status"] == "hidden"
    listed = client.get("/admin/reviews", params={"status": "hidden"}, headers=admin["headers"]).json()
    assert any(i["id"] == review_id and i["listing_title"] for i in listed["items"])


def test_delete_own_review():
    lid, user = _listing(), _register()
    _post(lid, user, rating=4)
    assert client.delete(f"/listings/{lid}/reviews/mine", headers=user["headers"]).status_code == 204
    assert client.get(f"/listings/{lid}/reviews/mine", headers=user["headers"]).json() is None
    assert client.delete(f"/listings/{lid}/reviews/mine", headers=user["headers"]).status_code == 404


def test_short_name_hides_full_name():
    from app.reviews.repo import short_name
    assert short_name("Trần Hoàng Phú") == "Phú T.H."
    assert short_name("Nguyễn Văn A (CNTT)") == "A N.V."
    assert short_name("phu") == "phu"
    assert short_name("  ") == "Sinh viên" and short_name(None) == "Sinh viên"


def test_phone_filter_does_not_block_prices_or_years():
    from app.reviews.schemas import _PHONE
    for ok in ("giá 2.000.000 2.500.000", "giá từ 1.500.000-2.000.000", "tiền điện 3.500 4.000 4.500",
               "thuê 2022 2023 2024", "đóng 500.000 0912345", "ở đây 10 tháng", "phòng 25m2, điện 3.500đ/kWh"):
        assert not _PHONE.search(ok), ok
    for bad in ("gọi 0912345678", "0912 345 678", "0912.345.678", "+84 912 345 678", "ĐT: 0292 3831 234"):
        assert _PHONE.search(bad), bad


def test_hidden_review_cannot_be_deleted_to_escape_moderation():
    lid, user, admin = _listing(), _register(), _register(admin=True)
    review_id = _post(lid, user, rating=1).json()["id"]
    client.patch(f"/admin/reviews/{review_id}", json={"status": "hidden"}, headers=admin["headers"])
    assert client.delete(f"/listings/{lid}/reviews/mine", headers=user["headers"]).status_code == 409
    assert client.get(f"/listings/{lid}/reviews/mine", headers=user["headers"]).json()["status"] == "hidden"


def test_owner_cannot_review_own_listing():
    owner, lid = _register(), _listing()
    with engine.begin() as conn:
        conn.execute(text("UPDATE aggregated_listings SET posted_by = :u WHERE id = :id"), {"u": owner["id"], "id": lid})
    assert _post(lid, owner, rating=5).status_code == 403
