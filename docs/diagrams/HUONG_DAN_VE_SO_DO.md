# Hướng dẫn vẽ sơ đồ theo hệ thống hiện tại (14/10/2026)

Dành cho thành viên vẽ sơ đồ cho báo cáo. **Code trên `main` là nguồn đúng.** Thư mục `Diagrams/` (vẽ 08/2026) đã cũ — chưa có
ghép bạn/chat realtime, chatbot, bản đồ v2, đánh giá nhà trọ, quản trị người dùng — chỉ dùng tham khảo bố cục.

| Sơ đồ | Đọc ở đâu |
|---|---|
| ERD | [`ERD.md`](ERD.md) (sinh từ DB thật, 33 bảng) · `infra/db/migrations/*.sql` · `docs/reference/Data_Dictionary.md` |
| Use case | mục 1 dưới đây · `apps/web/src/app/*` (mỗi thư mục = 1 trang) |
| Kiến trúc / triển khai | mục 2 · `docker-compose.yml` · `apps/web/src/lib/proxy.ts` |
| Sequence | mục 3 · router + repo của từng module trong `apps/api/app/<module>/` |
| Activity | mục 4 · `apps/api/app/crawler/pipeline.py`, `cleaner/pipeline.py`, `recommend/core.py` |
| State | mục 5 · migration + repo tương ứng |
| Class / module | mục 6 |

API đầy đủ (tên, tham số, schema): chạy `docker compose up` rồi mở `http://localhost:8000/docs`, hoặc
`docs/reference/API_Specification.md`.

## 1. Use case

**Tác nhân:** Khách (chưa đăng nhập) · Sinh viên (đăng nhập email hoặc MSSV) · Quản trị viên · Hệ thống ngoài (trang nguồn tin
trọ, OpenRouteService/OSRM, OpenStreetMap, Gemini/Ollama) · Bộ lập lịch crawl.

| Nhóm | Use case | Tác nhân | Trang / API |
|---|---|---|---|
| Tìm trọ | Tìm kiếm, lọc (giá, quận, khoảng cách, diện tích, loại), sắp xếp | Khách, SV | `/` · `GET /listings` |
| | Xem chi tiết tin, liên hệ chủ trọ (gọi/Zalo/tin gốc) | Khách, SV | `/listings/[id]` · `GET /listings/{id}`, `/contact` |
| Bản đồ | Xem tin quanh CTU, đổi khu I/II/III, bán kính | Khách, SV | `/map` · `GET /listings/nearby` |
| | Xem đường đi tới trường, số phút | Khách, SV | `GET /listings/{id}/route` |
| | Xem tiện ích quanh tin (chợ, siêu thị, ATM, nhà thuốc, bệnh viện, xe buýt) | Khách, SV | `GET /pois`, `/pois/summary` |
| Gợi ý | Nhận gợi ý theo tiêu chí (ngân sách, khu, thời gian đi, tiện ích, ưu tiên) | Khách, SV | `/goi-y` · `POST /recommend` |
| | Chấm mù kết quả gợi ý (công cụ đánh giá) | SV | `/goi-y/danh-gia` · `/recommend/eval/*` |
| Ghép bạn ở | Khai hồ sơ lối sống | SV | `/roommate` · `POST /matching/profile` |
| | Xem bộ thẻ gợi ý, quan tâm/bỏ qua, gửi lời mời kèm lời nhắn | SV | `GET /matching/deck`, `POST /matching/swipe`, `/invite` |
| | Nhận lời mời, chấp nhận → thành đôi | SV | `/matching/invites/{id}/respond` |
| | Chấm điểm thẻ làm mù (công cụ đánh giá) | SV | `/roommate/rate` · `/matching/rate` |
| Chat | Nhắn tin realtime, gửi ảnh, chia sẻ tin trọ, đồng ý chia sẻ liên hệ, huỷ ghép, báo cáo | SV | `/chat` · `/chat/*`, WebSocket `/chat/ws` |
| Trợ lý AI | Hỏi tìm phòng / pháp lý thuê trọ / KTX CTU, xem lịch sử, phản hồi | SV | widget, `/tro-ly` · `POST /chatbot/ask` |
| Cẩm nang | Đọc KTX CTU, lưu ý tìm phòng, ở ghép, pháp lý; so KTX với thuê trọ | Khách, SV | `/cam-nang` |
| Đánh giá | Viết/sửa/xoá đánh giá nhà trọ (sao + tag) | SV | `/listings/[id]` · `POST /listings/{id}/reviews` |
| Tài khoản | Đăng ký, đăng nhập (email/MSSV), đăng xuất | Khách, SV | `/register`, `/login` · `/auth/*` |
| Quản trị | Quản lý nhà trọ (thêm/sửa tin nhập tay, ẩn tin) | Admin | `/quan-ly/nha-tro` · `POST/PUT/DELETE /listings` |
| | Quản lý người dùng (tìm, cấp/bỏ admin, khoá/mở khoá) | Admin | `/quan-ly/nguoi-dung` · `/admin/users` |
| | Kiểm duyệt đánh giá (ẩn/hiện) | Admin | `/quan-ly/danh-gia` · `/admin/reviews` |
| | Bật/tắt tài liệu của trợ lý AI | Admin | `/admin/documents` (chỉ API) |
| | Chạy crawl thủ công | Admin | `POST /crawler/run` |
| Dữ liệu | Thu thập tin định kỳ, làm sạch, tính phút tới trường | Bộ lập lịch | `crawler/scheduler.py` |

Lưu ý phạm vi (ADR-024): sinh viên **không** đăng tin; chủ trọ **không** có tài khoản (liên hệ qua SĐT/tin gốc).

## 2. Kiến trúc / triển khai

Docker Compose 4 container: **web** (Next.js, cổng 3000) · **api** (FastAPI, 8000) · **db** (Postgres + PostGIS + pgvector) ·
**redis** (pub/sub chat). Ollama (mô hình Qwen) chạy trên máy host, không trong compose.

- Trình duyệt **không** gọi thẳng API: mọi request đi qua Route Handler của Next (`apps/web/src/app/api/**`) — đây là lớp BFF,
  gắn token từ cookie httpOnly (`lib/session.ts`) và tự làm mới token khi 401 (`lib/proxy.ts`). Riêng WebSocket chat nối thẳng
  `api:8000/chat/ws` bằng vé ngắn hạn xin qua `/api/chat/ws-ticket`.
- Dịch vụ ngoài: bản đồ nền OpenFreeMap (tile vector) · OpenRouteService (số phút, đường đi) → OSRM công khai (dự phòng) ·
  Nominatim (geocode) · Overpass/OSM (tiện ích, nạp sẵn vào DB) · Gemini API → Ollama → câu trả lời mẫu (trợ lý AI) · 6 trang
  nguồn tin trọ (crawl).
- Backend mỗi module = 1 package `router.py` + `repo.py` (+ `schemas.py`), SQL viết tay (SQLAlchemy Core, không ORM).

## 3. Sequence — các luồng chính

**3.1 Đăng nhập + gọi API có xác thực.** Trình duyệt → `POST /api/auth/login` (Next) → `POST /auth/login` hoặc `/auth/login/ctu`
(FastAPI: tìm `user_identities`, kiểm bcrypt, kiểm `users.locked_at`) → trả access (15 phút) + refresh (30 ngày) → Next ghi
cookie httpOnly. Request sau: trình duyệt → Route Handler → `proxyToApi` gắn `Bearer` → API `get_current_user` đọc user từ
DB (role, khoá) → nếu 401 thì proxy gọi `/auth/refresh` 1 lần, ghi cookie mới, gọi lại.
File: `apps/web/src/app/api/auth/login/route.ts`, `lib/proxy.ts`, `apps/api/app/auth/{router,deps}.py`.

**3.2 Bản đồ — chọn một tin.** `MapScreen` → song song 3 request: (a) `GET /api/listings/{id}/route?campus=` → API: tra
`route_cache` → chưa có thì ORS Directions → lỗi thì OSRM → ghi cache → polyline; (b) `GET /api/pois` + `/api/pois/summary`
(PostGIS `ST_DWithin` 1 km trên bảng `pois`); (c) `GET /api/listings/{id}/contact`. MapLibre vẽ đường + icon tiện ích.
File: `app/map/MapScreen.tsx`, `MapCanvas.tsx`, `apps/api/app/listings/{router,routing}.py`, `pois/repo.py`.

**3.3 Gợi ý nhà trọ.** `/goi-y` (form) → `POST /api/recommend` → `recommend/router.py` → `repo.candidates()` (danh mục tin, cache
60 s) → `core.py`: lọc cứng → nới tiêu chí nếu thiếu → chấm MAUT (trọng số từ khảo sát) → MMR đa dạng vị trí → 10 tin + lý do.
File: `apps/api/app/recommend/{router,repo,core}.py`.

**3.4 Ghép bạn ở → thành đôi.** `GET /matching/deck` (lọc cứng 2 tầng `filters.py` → điểm Gower + harmonic `score.py` → ghi
`deck_log`) → SV bấm Quan tâm: `POST /matching/swipe` → nếu người kia đã thích: trong 1 transaction `lock_pair` →
`create_match` (tạo `match_requests` accepted + `conversations` + `conversation_members`) → `ChatHub.publish(match.new)` qua
Redis tới cả hai → UI hiện "Thành đôi!". Lời mời: `/matching/invite` → người kia `/invites/{id}/respond`.
File: `apps/api/app/matching/{router,repo,filters,score}.py`, `chat/hub.py`.

**3.5 Chat realtime.** Mở `/chat` → `POST /api/chat/ws-ticket` (vé 60 s) → WebSocket `/chat/ws?ticket=` (API kiểm vé + tài khoản
không bị khoá, đăng ký `Connection` vào `ChatHub`) → gửi tin: `POST /chat/conversations/{id}/messages` (REST, ghi `messages`) →
`hub.publish(message.new)` → Redis kênh `chat:u:<id>` → worker giữ socket của người nhận đẩy xuống. Redis chết ⇒ chỉ đẩy cục
bộ, FE tự chuyển sang polling. Đồng ý chia sẻ liên hệ: `POST /contact-consent` — đủ 2 bên mới lộ SĐT/email (T3).
File: `apps/api/app/chat/{router,repo,hub}.py`, `apps/web/src/lib/chat/useChatSocket.ts`.

**3.6 Trợ lý AI (RAG).** Widget → `POST /api/chatbot/ask` → `chatbot/router.py` → `parser.parse_query` phân loại: khẩn cấp
(113/114/115) · ngoài khu vực · ngoài phạm vi · pháp lý/KTX · tìm phòng → (pháp lý) mở rộng truy vấn + truy xuất BM25 + vector
E5 trên `legal_ctu_v1.legal_chunks` · (tìm phòng) BM25 + vector trên tin đang hiển thị → sinh câu trả lời: Gemini → Qwen
(Ollama) → mẫu → kiểm chứng trích dẫn (bác ý không có nguồn) → lưu `chatbot_turns`.
File: `apps/api/app/room_service/chatbot/{router,service,parser,legal_retrieval,repo,providers}.py`.

**3.7 Đánh giá nhà trọ.** `ReviewSection` → `POST /api/listings/{id}/reviews` → API: giới hạn tần suất → kiểm tin còn hiển thị +
không phải chủ tin → validate (tag chuẩn, không SĐT/link) → upsert 1 đánh giá/tài khoản → trả về; trang tải lại tóm tắt
(`GET .../reviews`: điểm TB, phân bố sao, đếm tag). Admin: `PATCH /admin/reviews/{id}` ẩn/hiện.
File: `apps/api/app/reviews/{router,repo,schemas}.py`.

**3.8 Admin khoá tài khoản.** `/quan-ly/nguoi-dung` → `PATCH /api/admin/users/{id}` `{locked: true}` → API: kiểm không tự khoá,
còn ≥ 1 admin → `users.locked_at = now()` → `ChatHub.publish(account.locked)` → socket chat của người đó tự đóng (4403); mọi
request sau của họ bị `get_current_user` trả 403.
File: `apps/api/app/admin_users/router.py`, `auth/deps.py`, `chat/hub.py`.

## 4. Activity

**Thu thập dữ liệu** (`crawler/pipeline.py:run_source`, `nhatot.py`): lập lịch / `run_once` → tải trang danh sách → parse →
tải trang chi tiết → geocode (bảng mốc + Nominatim, chặn ngoài Cần Thơ) → upsert (đổi toạ độ ⇒ xoá phút cũ) → trích điện/nước/
cọc, liên hệ, địa chỉ → [lượt full sạch?] đánh dấu tin vắng mặt → `run_cleaner` → `auto_route` (ORS Matrix) → (thủ công) `audit`.

**Làm sạch 5 tầng** (`cleaner/pipeline.py:run_cleaner`): phân loại loại chỗ ở → kiểm giá → suy diện tích → chuẩn hoá →
`quality_score` → `cleaned` hoặc `rejected`.

**Gợi ý** (`recommend/core.py`): lọc cứng → đủ ứng viên? (không ⇒ nới giá/thời gian) → chấm MAUT → MMR chọn 10 → lý do + "nên hỏi
chủ trọ".

## 5. State

- **Tin trọ** `aggregated_listings.status`: `active` → `expired` (vắng ≥ 2 lượt full) → `active` (gặp lại, trừ tin bị audit loại);
  `active` → `hidden` (admin/audit); `flagged`. Song song `cleaning_status`: `raw` → `cleaned` | `rejected` (nội dung đổi ⇒ về `raw`).
- **Lời mời ghép** `match_requests.status`: `pending` → `accepted` | `rejected`; `accepted` → `unmatched` (huỷ ghép từ khung chat).
- **Quẹt** `swipes.decision`: `like` | `pass` (pass hết hạn sau thời gian chờ, có thể hiện lại).
- **Đánh giá** `reviews.status`: `visible` ⇄ `hidden` (admin).
- **Tài khoản** `users`: hoạt động ⇄ bị khoá (`locked_at`); `role`: `user` ⇄ `admin`.

## 6. Class / module

Backend không có lớp ORM — sơ đồ lớp nên vẽ ở mức **module**: mỗi package `listings`, `pois`, `recommend`, `auth`, `admin_users`,
`reviews`, `matching`, `chat`, `crawler`, `cleaner`, `room_service/chatbot` gồm `Router` (endpoint) → `Repo` (truy vấn SQL) →
`schemas` (Pydantic, vd. `ListingOut`, `ReviewIn`, `AdminUserOut`, `ChatAskRequest`). Lớp có hành vi rõ: `ChatHub` + `Connection`
(`chat/hub.py`), `Geocoder` (`crawler/geocode.py`), `ListingRepo` (`crawler/repo.py`), `Candidate`/`Query` (`recommend/core.py`).
Frontend: trang (`app/*/page.tsx`) → component client (`MapScreen`, `RecommendApp`, `RoommateApp`, `ChatApp`, `ReviewSection`…) →
Route Handler (`app/api/**`) → `lib/proxy.ts`.
