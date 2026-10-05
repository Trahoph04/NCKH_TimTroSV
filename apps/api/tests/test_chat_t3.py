"""T3 — lộ liên hệ khi CẢ HAI bên đồng ý (DB thật, không mock).

Chạy: DATABASE_URL=... pytest tests/test_chat_t3.py

Đây là bài kiểm lời hứa đã in trong phiếu khảo sát cho ~30 SV: "MSSV và thông tin
liên hệ của bạn CHỈ hiện ra sau khi CẢ HAI BÊN cùng bấm đồng ý kết nối". Nên mọi
test ở đây đều soi phía KHÔNG được thấy gì, không chỉ phía được thấy — một cổng
khoá chỉ đúng ở nhánh "mở" là cổng khoá hỏng.
"""
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app, engine

client = TestClient(app)


def _blob(obj) -> str:
    """Dựng lại JSON để assert "chuỗi này KHÔNG có trong body".

    Quét cả body thay vì kiểm từng field: cổng khoá hỏng thường làm liên hệ lọt ra
    ở một field mà test không nghĩ tới (vd. partner_profile, last_message.body).
    """
    return json.dumps(obj, ensure_ascii=False, default=str)


def _user(name: str = "SV", gender: str = "nu") -> dict:
    """Đăng ký + TẠO HỒ SƠ Ở GHÉP (giống tests/test_chat.py:_user).

    Hồ sơ là bắt buộc để swipe được: POST /matching/swipe kiểm lọc cứng (chỉ ghép
    cùng giới), user không có hồ sơ thì không có giới tính để kiểm ⇒ 409.
    """
    email = f"t3_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123", "name": name})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/auth/me", headers=h).json()
    pr = client.post(
        "/matching/profile",
        json={"gender": gender, "sleep_time": 1, "cleanliness": 4,
              "noise_tolerance": 3, "budget_band": 1, "scenario": 2},
        headers=h,
    )
    assert pr.status_code == 200, pr.text
    return {"id": me["id"], "h": h, "name": name, "email": email}


def _like(a: dict, b: dict) -> dict:
    r = client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"}, headers=a["h"])
    assert r.status_code == 200, r.text
    return r.json()


def _pair() -> tuple[dict, dict, int]:
    a, b = _user("An"), _user("Bình")
    assert _like(a, b)["matched"] is False
    res = _like(b, a)
    assert res["matched"] is True
    return a, b, res["conversation_id"]


def _consent(u: dict, conv: int) -> dict:
    r = client.post(f"/chat/conversations/{conv}/contact-consent", headers=u["h"])
    assert r.status_code == 200, r.text
    return r.json()


def _state(u: dict, conv: int) -> dict:
    r = client.get(f"/chat/conversations/{conv}/contact-consent", headers=u["h"])
    assert r.status_code == 200, r.text
    return r.json()


def _give_ctu_mssv(user_id: int) -> str:
    """Gắn MSSV thật vào user để test "MSSV không bao giờ lọt" có nghĩa.

    Đăng ký bằng /auth/register chỉ sinh identity provider='local', không có MSSV
    nào để lọt — không gắn thì assert phía dưới xanh một cách rỗng.
    """
    mssv = f"B{uuid4().int % 10**7:07d}"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user_identities (user_id, provider, provider_user_id) "
                "VALUES (:u, 'ctu', :m)"
            ),
            {"u": user_id, "m": mssv},
        )
    return mssv


# --------------------------------------------------------------- chưa đồng ý
def test_truoc_khi_dong_y_khong_co_lien_he_o_dau_ca():
    a, b, conv = _pair()
    for u in (a, b):
        st = _state(u, conv)
        assert st == {
            "mine": False, "theirs": False, "unlocked": False,
            "waiting_for_other": False, "partner": None,
        }
    # Khối `contact` đi kèm detail hội thoại phải nói đúng điều đó, và detail vẫn
    # chỉ là T1/T2: tên + hồ sơ lối sống, không email.
    detail = client.get(f"/chat/conversations/{conv}", headers=a["h"]).json()
    assert detail["contact"]["unlocked"] is False and detail["contact"]["partner"] is None
    assert b["email"] not in _blob(detail)


# ------------------------------------------------------------ đồng ý một bên
def test_dong_y_mot_ben_khong_lo_gi_ca_hai_phia():
    a, b, conv = _pair()
    st = _consent(a, conv)
    assert st["mine"] is True and st["theirs"] is False
    assert st["unlocked"] is False and st["waiting_for_other"] is True
    assert st["partner"] is None

    # Phía A (đã đồng ý) vẫn chưa thấy gì — đồng ý là CHO, không phải XIN.
    assert b["email"] not in _blob(_state(a, conv))
    assert b["email"] not in _blob(client.get(f"/chat/conversations/{conv}", headers=a["h"]).json())

    # Phía B (chưa đồng ý) thấy "họ đã đồng ý" nhưng KHÔNG thấy liên hệ của A.
    st_b = _state(b, conv)
    assert st_b["mine"] is False and st_b["theirs"] is True
    assert st_b["unlocked"] is False and st_b["partner"] is None
    assert a["email"] not in _blob(st_b)
    assert a["email"] not in _blob(client.get(f"/chat/conversations/{conv}", headers=b["h"]).json())


def test_nguoi_khong_bao_gio_dong_y_van_khong_xem_duoc_du_ben_kia_da_dong_y():
    """Kịch bản dễ sai nhất: cổng khoá viết thành "có ít nhất một người đồng ý".

    B không bấm gì cả, chỉ gọi mọi endpoint đọc được. Bất kể A bấm bao nhiêu lần,
    B phải không thấy liên hệ của A.
    """
    a, b, conv = _pair()
    _consent(a, conv)
    _consent(a, conv)
    _consent(a, conv)
    for _ in range(2):
        assert _state(b, conv)["partner"] is None
        assert client.get(f"/chat/conversations/{conv}", headers=b["h"]).json()["contact"]["partner"] is None
    # và DB đúng là chỉ có một chữ ký
    with engine.connect() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) FROM conversation_members "
                "WHERE conversation_id = :c AND COALESCE(contact_consent, FALSE)"
            ),
            {"c": conv},
        ).scalar_one()
    assert n == 1


# ------------------------------------------------------------- đồng ý hai bên
def test_dong_y_hai_ben_moi_lo_lien_he():
    a, b, conv = _pair()
    _consent(a, conv)
    st = _consent(b, conv)  # người bấm sau thấy mở ngay trong response
    assert st["mine"] is True and st["theirs"] is True
    assert st["unlocked"] is True and st["waiting_for_other"] is False
    assert st["partner"]["user_id"] == a["id"]
    assert st["partner"]["email"] == a["email"]
    assert st["partner"]["name"] == "An"
    # Khảo sát KHÔNG thu số điện thoại ⇒ user mới không có phone ⇒ không deep link
    # Zalo (FE phải hiện dòng "chưa có số", không hiện nút chết).
    assert st["partner"]["phone"] is None and st["partner"]["zalo_url"] is None

    # Người bấm trước cũng thấy mở ở nhịp hỏi lại / lần mở panel sau.
    st_a = _state(a, conv)
    assert st_a["unlocked"] is True and st_a["partner"]["email"] == b["email"]
    detail = client.get(f"/chat/conversations/{conv}", headers=a["h"]).json()
    assert detail["contact"]["partner"]["email"] == b["email"]


def test_co_so_dien_thoai_thi_tra_kem_deep_link_zalo():
    a, b, conv = _pair()
    # phone chỉ có nếu người dùng tự nhập trong app; set thẳng DB vì chưa có
    # endpoint sửa phone trong phiên này.
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET phone = '0912000111' WHERE id = :u"), {"u": b["id"]})
    _consent(a, conv)
    _consent(b, conv)
    partner = _state(a, conv)["partner"]
    assert partner["phone"] == "0912000111"
    assert partner["zalo_url"] == "https://zalo.me/0912000111"


def test_bam_lai_nhieu_lan_khong_loi_va_khong_doi_trang_thai():
    a, b, conv = _pair()
    first = _consent(a, conv)
    assert _consent(a, conv) == first  # idempotent: y nguyên, không 409/500
    _consent(b, conv)
    opened = _state(a, conv)
    assert _consent(a, conv) == opened
    assert _consent(b, conv)["unlocked"] is True


# ------------------------------------------------------------------- quyền
def test_nguoi_ngoai_hoi_thoai_nhan_404_khong_phai_403():
    """404 (không 403) để không lộ hội thoại nào tồn tại — giữ nguyên quy ước
    của _require_member. Kiểm cả khi cặp kia ĐÃ mở T3: lúc đó điều kiện "mọi
    thành viên đã đồng ý" là ĐÚNG, nên nếu thiếu kiểm thành viên thì người lạ
    lấy được liên hệ của người khác.
    """
    a, b, conv = _pair()
    _consent(a, conv)
    _consent(b, conv)
    stranger = _user()
    assert client.post(f"/chat/conversations/{conv}/contact-consent", headers=stranger["h"]).status_code == 404
    assert client.get(f"/chat/conversations/{conv}/contact-consent", headers=stranger["h"]).status_code == 404
    assert client.get(f"/chat/conversations/{conv}", headers=stranger["h"]).status_code == 404
    # hội thoại không tồn tại cũng 404 (không 500)
    assert client.post("/chat/conversations/100000000/contact-consent", headers=a["h"]).status_code == 404
    assert client.get("/chat/conversations/100000000/contact-consent", headers=a["h"]).status_code == 404
    # người lạ không hề ghi được chữ ký nào vào hội thoại
    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM conversation_members WHERE conversation_id = :c"),
            {"c": conv},
        ).scalar_one()
    assert n == 2


def test_thieu_token_tra_403_hbearer():
    a, b, conv = _pair()
    # HTTPBearer trả 403 khi thiếu header Authorization (không phải 401)
    assert client.post(f"/chat/conversations/{conv}/contact-consent").status_code == 403
    assert client.get(f"/chat/conversations/{conv}/contact-consent").status_code == 403


def test_dong_y_chi_bat_cho_chinh_minh():
    a, b, conv = _pair()
    _consent(a, conv)
    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                text(
                    "SELECT user_id, COALESCE(contact_consent, FALSE) FROM conversation_members "
                    "WHERE conversation_id = :c"
                ),
                {"c": conv},
            ).all()
        )
    assert rows[a["id"]] is True
    assert rows[b["id"]] is False  # không có đường nào bật thay người khác


# -------------------------------------------------------------------- MSSV
def test_mssv_khong_bao_gio_xuat_hien_o_bat_ky_response_nao():
    """MSSV ở user_identities(provider='ctu'), chỉ để CTU xác thực nội bộ.

    Lời hứa trong phiếu nói MSSV hiện ra sau khi cả hai đồng ý, nhưng T3 cố ý KHÔNG
    lộ nó: người ở ghép không cần MSSV của nhau, mà rò một mã định danh sinh viên
    thì không thu lại được. Test quét toàn bộ body, không chỉ một field.
    """
    a, b, conv = _pair()
    mssv_a, mssv_b = _give_ctu_mssv(a["id"]), _give_ctu_mssv(b["id"])
    _consent(a, conv)
    _consent(b, conv)

    bodies = []
    for u in (a, b):
        bodies.append(client.get(f"/chat/conversations/{conv}/contact-consent", headers=u["h"]).text)
        bodies.append(client.post(f"/chat/conversations/{conv}/contact-consent", headers=u["h"]).text)
        bodies.append(client.get(f"/chat/conversations/{conv}", headers=u["h"]).text)
        bodies.append(client.get("/chat/conversations", headers=u["h"]).text)
        bodies.append(client.get("/matching/likes", headers=u["h"]).text)
    blob = "\n".join(bodies)
    assert mssv_a not in blob and mssv_b not in blob
    # ngược lại: email ĐÃ phải lọt (nếu không thì assert trên xanh vì chẳng lộ gì)
    assert a["email"] in blob and b["email"] in blob


# --------------------------------------------------------------- huỷ ghép
def test_huy_ghep_xoa_luon_chu_ky_dong_y():
    """Huỷ ghép là xoá cứng hội thoại ⇒ chữ ký T3 cũng mất theo (CASCADE).

    Quan trọng vì ghép lại sẽ tạo hội thoại MỚI: không được thừa hưởng "đã đồng ý
    lộ liên hệ" từ lần ghép trước.
    """
    a, b, conv = _pair()
    _consent(a, conv)
    _consent(b, conv)
    assert client.delete(f"/chat/conversations/{conv}", headers=a["h"]).status_code == 204
    assert client.get(f"/chat/conversations/{conv}/contact-consent", headers=a["h"]).status_code == 404

    _like(a, b)
    res = _like(b, a)
    conv2 = res["conversation_id"]
    assert conv2 != conv
    assert _state(a, conv2) == {
        "mine": False, "theirs": False, "unlocked": False,
        "waiting_for_other": False, "partner": None,
    }
