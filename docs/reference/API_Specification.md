# Đặc Tả API (API Specification)
## Hệ thống tổng hợp & gợi ý nhà trọ AI — THS2026-66

**Phiên bản:** 1.0 · **Base URL:** `http://localhost:8000` (dev) · **Format:** JSON

## Quy ước chung
- Auth: `Authorization: Bearer <access_token>` (JWT). Route công khai đánh dấu 🌐.
- Mã lỗi: `400` validate, `401` chưa auth, `403` thiếu quyền, `404` không thấy, `429` rate-limit, `500` lỗi server.
- Phân trang: query `?page=1&size=20`, response kèm `{ "total", "page", "size", "items" }`.
- Thời gian: ISO 8601 UTC.

---

## 1. Auth (`/auth`)

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/auth/register` | Đăng ký, gửi OTP email | 🌐 |
| POST | `/auth/verify-otp` | Xác thực OTP kích hoạt tài khoản | 🌐 |
| POST | `/auth/login` | Đăng nhập → access + refresh token | 🌐 |
| POST | `/auth/login/ctu` | Đăng nhập bằng **MSSV** + mã cấp trước (tài khoản buổi thử nghiệm) — ✅ đã code | 🌐 |
| POST | `/auth/google` | OAuth 2.0 Google *(đã code ở `/auth/login/google`)* | 🌐 |
| POST | `/auth/refresh` | Làm mới access token | 🌐 |
| POST | `/auth/forgot-password` | Gửi link reset | 🌐 |
| POST | `/auth/reset-password` | Đặt mật khẩu mới | 🌐 |
| GET | `/auth/me` | Thông tin user hiện tại | ✓ |

**POST /auth/login**
```jsonc
// request
{ "email": "sv@student.ctu.edu.vn", "password": "***" }
// 200
{ "access_token": "ey...", "refresh_token": "ey...", "token_type": "bearer",
  "user": { "id": 1, "name": "Trần Phú", "role": "user" } }
// 401
{ "detail": "Invalid email or password" }
```

**POST /auth/login/ctu** — tài khoản từ khảo sát chỉ có identity `provider='ctu'`, nên `/auth/login` (tìm identity
`local`) trả 401 với họ. Web gọi qua Route Handler `/api/auth/login/ctu` (tab "MSSV" ở `/login`).
```jsonc
// request — mssv không phân biệt hoa/thường (server chuẩn hoá CHỮ HOA)
{ "mssv": "B2300000", "password": "***" }          // mssv 4–20 ký tự, password 4–128
// 200
{ "access_token": "ey...", "refresh_token": "ey...", "token_type": "bearer" }
// 401 — cùng một câu cho "không có MSSV" và "sai mã": không cho dò MSSV nào tồn tại
{ "detail": "MSSV hoặc mã đăng nhập sai" }
```
KHÔNG tự tạo tài khoản khi MSSV lạ (khác Google): pool chỉ gồm người đã đồng ý dùng thử trong khảo sát.

---

## 2. Listings (`/listings`)

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/listings` | Tìm kiếm + lọc + sắp xếp + phân trang | 🌐 |
| GET | `/listings/{id}` | Chi tiết 1 tin | 🌐 |
| GET | `/listings/nearby` | Tìm theo bán kính (lat,lng,radius) | 🌐 |
| POST | `/listings` | Đăng tin UGC (qua AI Risk Check) | ✓ |
| PUT | `/listings/{id}` | Sửa tin của mình | ✓ |
| DELETE | `/listings/{id}` | Ẩn tin của mình (soft) | ✓ |
| POST | `/listings/{id}/report` | Báo cáo tin sai | ✓ |

**GET /listings** — query params:
`q`, `min_price`, `max_price`, `min_area`, `district`, `amenities` (csv), `max_distance_ctu`, `sort` (`price_asc`|`price_desc`|`newest`|`nearest`|`freshness`), `page`, `size`.
```jsonc
// 200 — chỉ trả status=active, kèm freshness
{ "total": 142, "page": 1, "size": 20, "items": [
  { "id": 1, "title": "Phòng gần CTU", "price": 2500000, "area": 25,
    "district": "Ninh Kiều", "lat": 10.03, "lng": 105.77,
    "distance_to_ctu": 800, "risk_score": 0.1, "risk_level": "safe",
    "freshness_score": 0.95, "last_seen": "2026-06-29T02:00:00Z",
    "source": "phongtro123", "images": ["..."] } ] }
```

---

## 3. Recommendation (`/recommend`)

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/recommend/quiz` | Nộp onboarding quiz → tạo preference_vector | ✓ |
| GET | `/recommend/for-you` | Top-10 gợi ý (cold-start fallback popularity) | ✓ |
| GET | `/recommend/popular` | Top-10 phổ biến (guest dùng được) | 🌐 |
| POST | `/recommend/feedback` | Ghi implicit feedback (view/bookmark/click) | ✓ |

```jsonc
// POST /recommend/feedback
{ "listing_id": 1, "type": "bookmark", "duration_ms": 4200 }
```

---

## 4. Roommate Matching (`/matching`) — ✅ đã code

Thuật toán: lọc cứng 2 tầng → Gower có trọng số → harmonic mean (ADR-013/014). Mọi route cần auth; thiếu header
`Authorization` ⇒ **403** (HTTPBearer), token sai/hết hạn ⇒ 401. Ghi (swipe/invite/rate) có **rate limit** ⇒ 429 + `Retry-After`.

| Method | Path | Mô tả |
|---|---|---|
| GET | `/matching/profile` | Hồ sơ 12 câu + `in_pool` + danh sách lựa chọn hợp lệ |
| POST | `/matching/profile` | Lưu hồ sơ (trường nào cũng optional) → trả `preview` = top-3 ngay |
| GET | `/matching/deck?limit=10&mode=ranked\|random&weights_ver=survey\|uniform` | Bộ thẻ hôm nay. **200 kèm `items: []`** khi rỗng — không 404 |
| POST | `/matching/swipe` | `{target_id, decision: like\|pass}` — 2 chiều like ⇒ match + hội thoại |
| POST | `/matching/invite` | `{target_id, note?≤300}` — lời mời kèm lời nhắn (= like + match_requests `pending`) |
| GET | `/matching/invites` | `{received: [...], sent: [...]}` lời mời đang chờ |
| POST | `/matching/invites/{id}/respond` | `{accept: bool}` — chỉ người nhận; đã xử lý ⇒ 409; không phải của mình ⇒ 404 |
| GET | `/matching/likes?limit=50` | Tab "Lời mời": ai đã thích mình mà mình chưa quyết (kèm `note`, `invite_id` nếu có) |
| GET | `/matching/passed?limit=50` | Thẻ đã bỏ qua (pass chỉ hạ ưu tiên 7 ngày) |
| GET | `/matching/rate` | 5 thẻ chấm điểm làm mù (3 thuật toán + 2 ngẫu nhiên) — sinh 1 lần, F5 không đổi |
| POST | `/matching/rate` | `{card_code, rating: 1..5}` → 204 |

```jsonc
// GET /matching/deck?mode=ranked → 200
{ "items": [ { "user_id": 98, "position": 0, "score": 0.71,
               "reasons": ["cùng ngủ 22h-24h", "..."], "caveat": null, "soft_flags": [],
               "is_simulated": false,
               "profile": { "name": "...", "gender": "nu", "don_vi": "...", "sleep_time": 1, "cleanliness": 4, ... } } ],
  "reason": null,          // no_profile | profile_incomplete | pool_empty | deck_done khi items rỗng
  "pool_total": 4, "deck_mode": "ranked", "weights_ver": "survey" }
// mode=random (buổi thử nghiệm): score=null, reasons=[], caveat=null, soft_flags=[] — ẩn mọi tín hiệu thuật toán

// POST /matching/swipe → 200
{ "matched": true, "conversation_id": 12 }
{ "matched": false, "conversation_id": null, "unmatched": true }  // pass một người ĐANG ghép ⇒ huỷ ghép + xoá hội thoại
// 409 — vi phạm lọc cứng; thông điệp KHÔNG tiết lộ deal-breaker cụ thể của người kia
{ "detail": "Hệ thống chỉ ghép bạn ở cùng giới tính" }

// GET /matching/rate → 200 — KHÔNG có score/arm/algo_rank (chấm làm mù)
{ "items": [ { "card_code": "K7QF", "position": 0, "rating": null, "is_simulated": false, "profile": { ... } } ],
  "reason": null, "round": 1, "done": false }
```

**Bất biến:** telemetry (`deck_position`, `deck_mode`, `score_at_swipe`, `features`, `decided_ms`) do server đọc từ
`deck_log` (ADR-015) — body swipe có gửi các trường này cũng bị bỏ qua. Thông tin trên thẻ là tầng T1 (ẩn danh):
không email/SĐT/MSSV. Xuất điểm chấm: `python -m app.matching.export_ratings > eval/data/ratings.csv`.

---

## 4b. Chat realtime giữa SV đã ghép (`/chat`) — ✅ đã code

Chi tiết as-built: `docs/tech_specs/Chat_Realtime.md`. Chỉ thành viên hội thoại mới thấy hội thoại (người ngoài ⇒
**404**, không 403 — không lộ hội thoại nào tồn tại). Hội thoại chỉ sinh từ match, không tạo tay.

| Method | Path | Mô tả |
|---|---|---|
| POST | `/chat/ws-ticket` | Vé 60 s để mở WebSocket (`{ticket, expires_in}`) |
| WS | `/chat/ws?ticket=…` | Kênh đẩy sự kiện. Vé sai ⇒ từ chối ở bắt tay; > 5 socket/user ⇒ đóng `4429` |
| GET | `/chat/unread` | `{messages, likes}` cho badge header |
| GET | `/chat/conversations?limit=50&before=&before_id=` | Danh sách (keyset theo `last_message_at, id`) → `{items, has_more, next}` |
| GET | `/chat/conversations/{id}` | Chi tiết + hồ sơ T1 đối phương + 6 tin trọ đã chia sẻ + khối `contact` (T3) |
| GET | `/chat/conversations/{id}/messages?after_id=\|before_id=&limit=50` | Tin nhắn; `after_id` = đồng bộ/polling |
| POST | `/chat/conversations/{id}/messages` | `{kind: text\|listing, body?, listing_id?, client_id?}` — trùng `client_id` ⇒ trả tin cũ |
| POST | `/chat/conversations/{id}/images` | multipart `files` (≤ 4 ảnh, ≤ 8 MB/ảnh; body quá lớn ⇒ **413** trước khi đọc) — re-encode, xoá EXIF |
| GET | `/chat/media/{media_id}` | Ảnh (chỉ thành viên hội thoại chứa ảnh) |
| POST | `/chat/conversations/{id}/read` | `{message_id}` — con trỏ đã đọc, không bao giờ lùi |
| GET | `/chat/conversations/{id}/contact-consent` | Trạng thái T3 `{mine, theirs, unlocked, waiting_for_other, partner}` |
| POST | `/chat/conversations/{id}/contact-consent` | Đồng ý cho người kia xem liên hệ CỦA MÌNH; `partner` chỉ có khi **mọi** thành viên đã đồng ý |
| DELETE | `/chat/conversations/{id}` | Huỷ ghép: xoá cứng tin + ảnh cho cả hai bên → 204 |
| POST | `/chat/conversations/{id}/report` | `{reason: spam\|harass\|fake\|scam\|other, note?}` → 201 |

Sự kiện WS (server → client): `hello` · `pong` · `message.new` · `read` · `typing` · `presence` · `match.new` ·
`like.new` · `conversation.removed` · `contact.consent` (chỉ là tín hiệu — không mang email/SĐT).
Client → server: `{type:"ping"}` · `{type:"typing", conversation_id, is_typing}`.

Rate limit (429): tin nhắn 30/phút · upload 10/phút · báo cáo 5/10 phút.

---

## 5. Chatbot RAG (`/assistant`) — ⬜ chưa code

> Tiền tố `/chat` đã thuộc về chat realtime (mục 4b). Khi code chatbot RAG, dùng tiền tố khác (đề xuất `/assistant`).

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/assistant/ask` | Hỏi đáp ngôn ngữ tự nhiên (confidence threshold) | ✓ |
| GET | `/assistant/history` | Lịch sử hội thoại (5 lượt gần nhất) | ✓ |

```jsonc
// POST /assistant/ask
{ "question": "Phòng 1.5 triệu gần CTU có wifi?", "session_id": "abc" }
// 200 — confidence cao
{ "answer": "Có 3 phòng phù hợp...", "confidence": "high",
  "sources": [ { "listing_id": 1, "title": "..." } ] }
// 200 — confidence thấp (T8: không bịa)
{ "answer": "Không tìm thấy thông tin phù hợp. Thử từ khóa khác nhé!",
  "confidence": "low", "sources": [] }
```

---

## 6. Risk (`/risk`)

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/listings/{id}/risk` | Chi tiết risk_score + risk_reasons[] | 🌐 |

```jsonc
// 200
{ "listing_id": 1, "risk_score": 0.72, "risk_level": "suspicious",
  "risk_reasons": ["Giá thấp hơn 40% so với khu vực", "Không có ảnh thực tế"] }
```

---

## 7. Admin (`/admin`)

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/admin/dashboard` | Thống kê tổng quan | Admin |
| GET | `/admin/listings/flagged` | DS tin risk cao / bị report | Admin |
| POST | `/admin/listings/{id}/moderate` | Duyệt / ẩn tin | Admin |
| GET | `/admin/users` | Quản lý người dùng | Admin |
| POST | `/admin/users/{id}/lock` | Khóa tài khoản | Admin |

---

## 8. Crawler (`/crawler`) — đã hiện thực

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/crawler/status` | Trạng thái N lần crawl gần nhất (crawl_runs) | Admin |
| POST | `/crawler/run` | Trigger thủ công 1 nguồn (`source`, `mode`) | Admin |

```jsonc
// POST /crawler/run?source=phongtro123&mode=incremental
{ "source": "phongtro123", "mode": "incremental",
  "fetched": 2, "new_count": 12, "updated_count": 3, "expired_count": 0, "error": null }
```

---

## 9. Health — đã hiện thực

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/health` | Liveness | 🌐 |
| GET | `/health/deps` | PostGIS + pgvector + Redis | 🌐 |

---

## Phụ lục: trạng thái hiện thực
- ✅ Đã code: `/health`, `/health/deps`, `/crawler/*`, `/listings` (search/filter/sort/nearby/detail), `/auth`
  (register/login/login-google/login-ctu/refresh/me), `/matching` (mục 4), `/chat` realtime (mục 4b).
- ⬜ Chưa code: verify-otp / forgot / reset password, recommend, chatbot RAG, risk, admin.
- Khi code, dùng FastAPI auto-docs tại `/docs` (OpenAPI) làm nguồn chính thức; file này là hợp đồng thiết kế.
