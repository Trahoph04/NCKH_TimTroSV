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
| GET | `/listings/nearby` | Tìm theo bán kính (lat,lng,radius,housing) — tối đa 1000 tin | 🌐 |
| GET | `/listings/{id}/route?campus=0\|1\|2` | Polyline `[[lat,lng],…]` khu CTU → tin; đọc `route_cache` trước, thiếu mới gọi ORS | 🌐 |
| POST | `/listings` | Đăng tin UGC (qua AI Risk Check) | ✓ |
| PUT | `/listings/{id}` | Sửa tin của mình | ✓ |
| DELETE | `/listings/{id}` | Ẩn tin của mình (soft) | ✓ |
| POST | `/listings/{id}/report` | Báo cáo tin sai | ✓ |

**GET /listings** — query params:
`q`, `min_price`, `max_price`, `min_area`, `district`, `amenities` (csv), `max_distance_ctu`, `housing` (`phong_tro`|`nha_mini`; bỏ trống = cả hai, giá trị khác → 422), `sort` (`price_asc`|`price_desc`|`newest`|`nearest`|`freshness`|`quality`), `page`, `size`.
Mỗi item có thêm `listing_type` (`phong_tro`|`nha_mini`|…) và `offer_kind` (`"lease_transfer"` = pass phòng/sang nhượng, `null` = thuê thường) — FE hiện nhãn "Nhà mini" / "Sang nhượng".
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

> **08/10 (ADR-024):** sinh viên không đăng tin. `POST /listings`, `PUT|DELETE /listings/{id}` và `GET /listings/managed`
> (thay `GET /listings/mine`) cần quyền **admin**; `PUT` tin không phải `source='user'` ⇒ **409** (tin crawl/khảo sát do
> pipeline cập nhật); `DELETE` = ẩn (`status='hidden'`) mọi tin.

## 2b. Tiện ích OSM (`/pois`) — ✅ đã code (07/10)

Dữ liệu © OpenStreetMap (Overpass, snapshot `infra/db/migrations/96_pois_seed.sql`). Khoảng cách = **đường chim bay**.
Nhóm: `cho` · `sieu_thi` · `atm` · `nha_thuoc` · `y_te` · `xe_buyt` (định nghĩa ở `apps/api/app/pois/categories.py`).

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| GET | `/pois?lat&lng&radius=1000&category=` | Tiện ích trong bán kính (≤ 5000 m), gần trước, tối đa 300; category lạ → 422 | 🌐 |
| GET | `/pois/summary?lat&lng&radius=1000` | Mỗi nhóm: `count` + `nearest` (luôn đủ 6 nhóm, nhóm trống count=0) | 🌐 |

```jsonc
// GET /pois/summary?lat=10.0146&lng=105.7615&radius=1000
{ "radius": 1000, "categories": [
  { "category": "nha_thuoc", "label": "Nhà thuốc", "count": 15,
    "nearest": { "id": 812, "category": "nha_thuoc", "name": "PharmaCity",
                 "lat": 10.0151, "lng": 105.7626, "distance_m": 131.4 } }, ... ] }
```
FE gọi qua Route Handler `/api/pois`, `/api/pois/summary`, `/api/listings/{id}/route` (FastAPI không bật CORS).

## 3. Recommendation (`/recommend`) — ✅ đã code (07/10)

Knowledge-based: lọc cứng + nới → MAUT (trọng số khảo sát) → MMR (ADR-021, `docs/specs/Recommendation.md`).
Thay thiết kế cũ (quiz → preference_vector cosine, popularity fallback, feedback) — xem ADR-021.

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/recommend` | 10 tin + `match` 0–100 + `reasons` + `ask` (nên hỏi chủ trọ) + `relaxed` | 🌐 |
| GET | `/recommend/prefill` | `{budget, gender}` từ hồ sơ ghép bạn (C1 → trần ngân sách) | ✓ |
| POST | `/recommend/eval/session` | Lượt đánh giá mù: gộp top-10 của 3 hệ, xáo trộn → thẻ (không điểm/hệ) | ✓ (10/10 phút) |
| GET | `/recommend/eval/session` | Lượt gần nhất (làm tiếp) | ✓ |
| POST | `/recommend/eval/judge` | `{card_code, relevance: 0\|1\|2}` → 204; thẻ người khác → 404 | ✓ (90/phút) |

```jsonc
// POST /recommend
{ "budget": 2000000, "campus": 1, "max_minutes": 10, "housing": "phong_tro",       // housing tuỳ chọn
  "required": ["wifi", "private_wc"], "top_factors": ["gia", "gan_truong"], "gender": "nam" }
// required ⊂ wifi|air_conditioner|private_wc|parking|kitchen|fridge|washing_machine|free_hours
// top_factors ≤ 3 ⊂ gia|gan_truong|gio_tu_do|tien_nghi|cho_de_xe|gan_cho   — sai → 422
// 200
{ "items": [{ "listing": { /* ListingOut */ }, "match": 92,
              "reasons": ["Giá 1,3 triệu, thấp hơn ngân sách 700k", "5 phút xe máy tới khu II"],
              "ask": ["WC riêng"] }],
  "relaxed": [], "candidates": 325, "weights": { "gia": 0.302, ... }, "algo_ver": "maut-mmr-v1" }
```
Xuất phán đoán: `python -m app.recommend.export_judgments` (người chấm = mã băm, không PII).

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

## 5. Chatbot RAG (`/chatbot`) — ✅ đã code (08/10, ghép từ branch `PHUC`, ADR-023)

> Tiền tố `/chat` thuộc chat realtime (mục 4b) ⇒ chatbot dùng `/chatbot` (FE: `/api/chatbot/*`). Mọi route cần đăng nhập;
> chủ lịch sử lấy từ token, không nhận `user_id` từ client. Rate limit 12 câu/phút/user (feedback 30/phút).

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/chatbot/ask` | Hỏi tìm trọ / KTX / pháp lý; trả câu trả lời + tin + nguồn, lưu vào hội thoại | ✓ |
| GET | `/chatbot/conversations?limit=30&offset=0` | Danh sách hội thoại của mình | ✓ |
| GET | `/chatbot/conversations/{uuid}?limit=50&before_id=` | Mở hội thoại, phân trang lượt cũ | ✓ |
| DELETE | `/chatbot/conversations/{uuid}` | Xoá hội thoại (kèm cache riêng của nó) — 204 | ✓ |
| POST | `/chatbot/feedback` | `{event_id, rating: 1\|-1, reason?, comment?}` — event phải của chính mình | ✓ |
| GET/PATCH | `/admin/documents[/{id}]` | Admin tìm/đọc/bật-tắt tài liệu của corpus đang phục vụ (có audit) | admin |
| GET | `/health/ai` | Provider, Ollama có model chưa, Gemini có key chưa, corpus đã nạp | 🌐 |

```jsonc
// POST /chatbot/ask
{ "message": "Phòng dưới 2 triệu ở Ninh Kiều có máy lạnh", "conversation_id": null }
// 200
{ "answer": "Mình tìm thấy 5 lựa chọn phù hợp nhất: … [1] …", "intent": "find_listing",
  "listings": [ { "id": 1530, "title": "…", "price": 1500000, "match_reasons": ["Trong ngân sách"], "rank": 1 } ],
  "sources": [ { "kind": "listing" | "legal_document", "rank": 1, "title": "…", "heading": "Điều 328…" } ],
  "no_answer": false, "partial_answer": false, "degraded": true, "degraded_reasons": ["…"],
  "retrieval_mode": "hybrid" | "lexical_structured" | "legal_hybrid", "generation_provider": "gemini" | "qwen-local" | "template" | "legal-extractive" | …,
  "conversation_id": "uuid", "turn_id": 12, "reused_answer": false, "event_id": 34, "latency_ms": 2700 }
```

`degraded: true` = không dùng được LLM hoặc bộ kiểm chứng bác bản nháp ⇒ câu trả lời template/trích nguyên văn theo nguồn
(không bịa). Câu hỏi độc lập có nguồn được cache (pháp lý/KTX 24 h, tin trọ 5 phút) — `reused_answer: true`.

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
| GET | `/health/ai` | Chatbot: provider/model, Ollama, corpus (mục 5) | 🌐 |

---

## Phụ lục: trạng thái hiện thực
- ✅ Đã code: `/health`, `/health/deps`, `/crawler/*`, `/listings` (search/filter/sort/nearby/detail/route), `/pois`, `/recommend`, `/auth`
  (register/login/login-google/login-ctu/refresh/me), `/matching` (mục 4), `/chat` realtime (mục 4b), `/chatbot` (mục 5, 08/10).
- ⬜ Chưa code: verify-otp / forgot / reset password, risk, admin (risk/admin ở branch nhóm, chờ ghép; riêng `/admin/documents` của chatbot đã có API).
- Khi code, dùng FastAPI auto-docs tại `/docs` (OpenAPI) làm nguồn chính thức; file này là hợp đồng thiết kế.
