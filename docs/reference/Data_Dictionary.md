# Từ Điển Dữ Liệu & ERD
## Hệ thống tổng hợp & gợi ý nhà trọ AI — THS2026-66

**Phiên bản:** 1.0 · **DBMS:** PostgreSQL 16 + PostGIS 3.4 + pgvector
**Nguồn:** `infra/db/migrations/20_listings.sql`, `Agent-Generated/02_PhanTich_NghiepVu_Va_DuLieu.md`
**ERD:** `Diagrams/archify/07_ERD.html`

---

## Tổng quan quan hệ

```
users 1──N user_interactions N──1 aggregated_listings
users 1──N reports            N──1 aggregated_listings
users 1──1 roommate_profiles
users 1──N match_requests (from_user / to_user)
aggregated_listings 1──N crawl_runs (theo source, không FK cứng)
```

---

## Bảng `aggregated_listings` — tin nhà trọ (lõi)

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | Khóa chính |
| title | TEXT | NOT NULL | Tiêu đề tin |
| price | INTEGER | | Giá thuê/tháng (VND) |
| area | REAL | | Diện tích (m²) |
| address | TEXT | | Địa chỉ thô |
| district | VARCHAR(50) | | Quận/huyện |
| geom | GEOMETRY(Point,4326) | GIST index | Tọa độ (geocode) |
| images | TEXT[] | | Mảng URL ảnh |
| description | TEXT | | Mô tả |
| source | VARCHAR(30) | NOT NULL | Nguồn: phongtro123/nhatot/mogi/…/`survey` (nhóm khảo sát thực địa, `source_id` = `KS-<STT>`, toạ độ đo tại chỗ)/`user` (UGC) |
| source_url | TEXT | | Link gốc |
| source_id | VARCHAR(100) | UNIQUE(source,source_id) | ID gốc trên nguồn (incremental dedup) |
| content_hash | CHAR(64) | index | SHA-256 nội dung → đổi → trigger update |
| minhash | BYTEA | | MinHash signature (T4 cross-source dedup) |
| parsed_amenities | JSONB | | Tiện ích chuẩn hóa {wifi:true,...} |
| risk_score | REAL | DEFAULT 0 | Điểm rủi ro 0-1 (T10) |
| risk_reasons | TEXT[] | | Lý do rủi ro |
| distance_to_ctu | REAL | | Khoảng cách đến CTU (m) |
| geocode_confidence | VARCHAR(10) | | high/medium/low/failed (T2) |
| embedding_vector | VECTOR(384) | | Embedding cho RAG/recommend |
| status | listing_status | DEFAULT 'active' | active/expired/flagged (P2: không xóa) |
| first_seen | TIMESTAMPTZ | DEFAULT now() | Lần đầu crawl thấy |
| last_seen | TIMESTAMPTZ | DEFAULT now() | Lần cuối còn thấy (freshness) |
| miss_count | INTEGER | DEFAULT 0 | Số chu kỳ full không thấy (T11) |
| freshness_score | REAL | DEFAULT 1.0 | exp(-age/7), độ tươi |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Lần cập nhật nội dung gần nhất |

| listing_type | listing_type_enum | DEFAULT 'khac' | `phong_tro` · `nha_mini` (mig 95) · `nha_nguyen_can` · `mat_bang` · `khac` — search chỉ trả 2 loại đầu |
| offer_kind | VARCHAR(16) | | (mig 95) `lease_transfer` = pass phòng/sang nhượng; NULL = thuê thường/không rõ |
| audit_reason, audit_at | TEXT, TIMESTAMPTZ | | (mig 98) lý do tin bị loại bởi `app.cleaner.audit` (vi_tri_cap_phuong, da_go_khoi_nguon, ngoai_pham_vi, tin_mau, sai_duong, …); NULL = chưa bị loại |

**Enum `listing_status`:** `active` | `expired` | `flagged`
**`geocode_confidence` của nguồn `nhatot`:** toạ độ ≥ 2 tin dùng chung = điểm mặc định của phường do Chợ Tốt gán → `medium`; điểm riêng 1 tin = người đăng ghim → `high` (`crawler/repo.py:mark_shared_coords`).
**Index:** GIST(geom), (status,last_seen), (content_hash).

---

## Bảng `crawl_runs` — nhật ký crawl (health check + cursor)

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| source | VARCHAR(30) | NOT NULL | Nguồn crawl |
| mode | VARCHAR(12) | NOT NULL | incremental / full |
| started_at | TIMESTAMPTZ | DEFAULT now() | Bắt đầu |
| finished_at | TIMESTAMPTZ | | Kết thúc |
| fetched | INTEGER | DEFAULT 0 | Số trang fetch |
| new_count | INTEGER | DEFAULT 0 | Tin mới |
| updated_count | INTEGER | DEFAULT 0 | Tin cập nhật |
| expired_count | INTEGER | DEFAULT 0 | Tin chuyển expired |
| error | TEXT | | Lỗi (vd 403/429) |

---

## Bảng `users` — người dùng

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| email | VARCHAR(255) | UNIQUE NOT NULL | Email đăng nhập |
| password_hash | TEXT | | bcrypt; NULL nếu OAuth |
| name | VARCHAR(100) | | Họ tên |
| avatar_url | TEXT | | Ảnh đại diện |
| phone | VARCHAR(20) | | SĐT (lộ khi matching accept) |
| role | VARCHAR(20) | DEFAULT 'user' | guest/user/admin |
| preference_vector | VECTOR(384) | | Vector sở thích (T5 recommend) |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

---

## Bảng `roommate_profiles` — hồ sơ ở ghép

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| user_id | INTEGER | PK, FK→users | |
| sleep_time | INTEGER | | 0 sớm /1 thường /2 cú đêm |
| cleanliness | INTEGER | 1-5 | Mức sạch sẽ |
| smoke | BOOLEAN | | Hút thuốc |
| noise_tolerance | INTEGER | 1-5 | Chịu ồn |
| gender_pref | INTEGER | | 0 không quan tâm /1 nam /2 nữ |
| bio | TEXT | | Giới thiệu |
| matching_vector | VECTOR(384) | | Vector ghép (T7) |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

---

## Bảng `user_interactions` — hành vi (implicit feedback)

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| user_id | INTEGER | FK→users | |
| listing_id | INTEGER | FK→aggregated_listings | |
| type | VARCHAR(20) | | view/bookmark/click_source/click_phone |
| duration_ms | INTEGER | | Thời gian xem |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

---

## Bảng `reports` — báo cáo tin sai

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| listing_id | INTEGER | FK→aggregated_listings | |
| reporter_id | INTEGER | FK→users | |
| reason | VARCHAR(50) | | wrong_price/expired/scam/other |
| note | TEXT | | Ghi chú |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/reviewed/dismissed |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

---

## Bảng `match_requests` — lời mời ở ghép

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| from_user | INTEGER | FK→users | Người gửi |
| to_user | INTEGER | FK→users | Người nhận |
| score | REAL | | Điểm tương thích lúc gửi |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/accepted/rejected |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

---

## Bảng `pois` — tiện ích OSM (migration 95, dữ liệu 96)

| Cột | Kiểu | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| id | SERIAL | PK | |
| osm_type, osm_id | VARCHAR(8), BIGINT | UNIQUE cặp | node/way/relation + id OSM (id trùng được giữa các loại) |
| category | VARCHAR(20) | index | `cho` `sieu_thi` `atm` `nha_thuoc` `y_te` `xe_buyt` |
| name | TEXT | | tên OSM (hoặc brand) |
| geom | GEOMETRY(Point,4326) | GIST | tâm (way/relation lấy `out center`) |
| tags | JSONB | | chỉ giữ tag hiển thị (`KEEP_TAGS`) |
| fetched_at | TIMESTAMPTZ | | |

## Bảng `route_cache` — đường đi ORS đã tính (migration 95)

PK `(origin_lat, origin_lng, campus, profile)` — toạ độ gốc `NUMERIC(8,5)` (~1 m); `path` JSONB `[[lat,lng],…]`
(khu CTU → tin). ~140 toạ độ phân biệt × 3 khu ⇒ lưu hết được; demo không phụ thuộc quota ORS.

---

## Bảng `rec_eval_sessions` / `rec_eval_cards` — đánh giá mù gợi ý (migration 97)

`rec_eval_sessions`: 1 lượt chấm (`user_id`, `criteria` JSONB = tiêu chí đã nhập, `relaxed`, `algo_ver`, `completed_at`).
`rec_eval_cards`: PK `(session_id, listing_id)`; `card_code` UNIQUE (in trên thẻ); `display_pos`; `rank_proposed` /
`rank_price` / `rank_cosine` (1..10, NULL = hệ đó không xếp tin này); `utility` (điểm MAUT); `relevance` 0–2; `judged_at`.
`listing_id` cố ý KHÔNG khoá ngoại — tin bị gỡ sau buổi thử nghiệm thì phán đoán vẫn còn.

---

## Chatbot — migration 100 (`100_chatbot.sql`, ADR-023)

- `aggregated_listings` thêm `embedding_model`, `embedded_content_hash` (sha256 văn bản đã nhúng — `index_listings` chỉ nhúng
  lại tin đổi nội dung), `embedded_at`, `risk_evaluated_at` (luôn NULL ở repo này ⇒ risk "chưa đánh giá"). Vector ở
  `embedding_vector VECTOR(384)` có sẵn từ mig 20.
- `legal_documents` / `legal_chunks` (schema `public` = khung rỗng; corpus phục vụ ở schema **`legal_ctu_v1`**, cùng cột +
  `source_metadata` JSONB, `provision_id`, `parent_content` = nguyên văn điều khoản để trích dẫn đủ ngoại lệ). `content_tsv`
  là cột sinh (BM25/tsvector), `embedding_vector VECTOR(384)` E5. `admin_enabled` = admin tắt nguồn mà không xoá vector.
- `legal_corpus_releases` (schema → hash manifest, trạng thái), `legal_document_admin_audit` (trước/sau mỗi lần admin sửa).
- `chatbot_conversations` (UUID, `user_id` → users ON DELETE CASCADE) / `chatbot_turns` (`question`, `response` JSONB,
  `cache_key`/`cache_scope`/`cache_expires_at`); `chatbot_shared_answers` (cache dùng chung, không chứa dữ liệu cá nhân).
- `chatbot_events` (telemetry: intent, confidence, provider, latency — KHÔNG lưu nội dung câu hỏi), `chatbot_feedback`.

---

## Ghi chú hiện thực
- ✅ Đã có migration: `aggregated_listings`, `crawl_runs` (`20_listings.sql`); `users`, `roommate_profiles`, `user_interactions`, `reports`, `match_requests`, `saved_searches` (`30_users.sql`).
- `30_users.sql` cũng thêm cột `aggregated_listings.posted_by` (FK→users, cho tin UGC).
- `saved_searches`: tiêu chí tìm kiếm đã lưu (JSONB) → thông báo tin mới khớp (FR-8.1).

## Công cụ vận hành
- `python -m app.crawler.backfill` — re-geocode + re-extract area cho listing đã có, KHÔNG fetch lại nguồn (nhanh, dùng khi cải tiến logic geocode/area). Cập nhật `geom`/`distance_to_ctu`/`geocode_confidence`/`area`.
- `python -m app.crawler.smoke phongtro123` — smoke test net thật, in 3 listing đầu, không ghi DB.
- `python -m app.crawler.import_catalog [--apply] < CATALOG.jsonl` — nạp gói Chợ Tốt (chỉ tin chưa có, idempotent).
- `python -m app.cleaner.reclassify [--apply]` — áp classifier mới lên tin đã làm sạch (không đụng area/title).
- `python -m app.pois.fetch_overpass [--apply] [--sql]` — lấy lại tiện ích OSM / sinh seed 96.
- `python -m app.listings.route_cache_backfill [--apply]` — lưu sẵn đường đi mọi toạ độ × 3 khu.
- `python -m app.recommend.export_snapshot` / `export_judgments` — CSV cho notebook 01 (không PII).
