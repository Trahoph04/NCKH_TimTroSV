# Checkpoint — Trọ CTU

_Cập nhật: 2026-08-08_

> Nguồn suy trạng thái: `task.md` (stigmergy board), git log, cấu trúc `apps/api/app/` + `apps/web/src/app/`.
> Chi tiết từng module xem `docs/tech_specs/`.

## Đã xong

- **Crawler pipeline 6 nguồn** — `apps/api/app/crawler/` (phongtro123, mogi, tromoi, bds123, nhadatcantho, nhadatcantho247). Fetcher + parser + normalize + dedup + geocode + scheduler. Sources JSON ở `apps/api/app/crawler/sources/`. Chi tiết `docs/tech_specs/Crawler_Pipeline.md` + `Crawler_Pipeline_Hardening.md`.
- **Data cleaning pipeline 5 tầng** — `apps/api/app/cleaner/pipeline.py` (`run_cleaner`): classify (phong_tro/nha/mặt bằng/khác) → validate giá → resolve area → normalize → quality_score 0..1. Search mặc định chỉ trả `listing_type=phong_tro` sạch. Chi tiết `docs/tech_specs/Data_Cleaning_Pipeline_Design.md`.
- **Auth (backend + frontend)** — backend `apps/api/app/auth/` (JWT access+refresh, OAuth provider, `router.py`). Frontend `apps/web/src/app/{login,register,me}/` + Route Handler proxy `apps/web/src/app/api/auth/`, token httpOnly cookie, middleware bảo vệ route (`apps/web/src/middleware.ts`). Chi tiết `docs/tech_specs/Frontend_Auth.md`.
- **UGC Listing CRUD** — `apps/api/app/listings/router.py` (`POST/PUT/DELETE /listings`), kiểm tra chủ sở hữu, soft-delete `status='hidden'`. Chi tiết `docs/tech_specs/UGC_Listing_CRUD.md`.
- **Frontend Listing UI** — list+lọc (`apps/web/src/app/page.tsx`), chi tiết (`listings/[id]/page.tsx`), form đăng/sửa (`listings/new`, `listings/[id]/edit`). Chi tiết `docs/tech_specs/Frontend_Listing_UI.md`.
- **Bản đồ Leaflet tương tác** — `apps/web/src/app/map/` (`MapView.tsx` dynamic ssr:false → `MapInner.tsx` react-leaflet CircleMarker + Popup OSM). Thay bản danh-sách-khoảng-cách cũ. Deps: leaflet + react-leaflet 4.x.
- **Trang "Tin của tôi"** — backend `GET /listings/mine` (`listings/router.py`, khai TRƯỚC `/{listing_id}`; repo `by_owner`), FE `apps/web/src/app/listings/mine/page.tsx` (route bảo vệ).
- **Ảnh cho form đăng tin** — `ListingForm.tsx`: textarea nhiều URL (split/trim/filter → `images[]`).
- **API core** — `apps/api/app/main.py`: health, `/health/deps` (postgres/postgis/pgvector/redis), `/crawler/status`, `/crawler/run`. Scheduler bật (`CRAWLER_ENABLED=true`, ~12 job).
- **Badge rủi ro trung thực** — `risk_level()` (`apps/api/app/listings/schemas.py:16`) trả `unknown` khi `risk_score=0` (chưa có risk engine) thay vì `safe`. FE render badge xám "Chưa rõ". Verified live: crawler listings trả `(0.0, 'unknown')`.
- **Test** — `apps/api/tests/` (test_auth, test_crawler, test_cleaner, test_listings, test_listings_crud). 86 test pass; test_listings 9/9 sau sửa badge.
- **Map & Routing — nền tảng (2026-07-06)** — spec `docs/specs/Map_Routing.md` chốt (glossary + quyết định). Cột `route_time_campus REAL[]` (`infra/db/migrations/50_route_time.sql`, đã apply, verified). ORS client `apps/api/app/listings/routing.py` (`matrix_minutes` time + `route_geometry` polyline), self-check pass + verify call thật (campus I→I = 0.0 phút → gotcha `[lng,lat]` đúng). Config `ors_api_key` (`config.py:20`). 3 campus CTU chốt (khu I/II/III, xem spec bảng Campus).
- **Route backfill (2026-07-06)** — `apps/api/app/listings/route_backfill.py`, 1 call Matrix cho 414 tin có geom. Verified DB: 414/414 có `route_time_campus`, avg khu II = 12.4 phút. **CỜ ĐỎ: 3 tin `nhadatcantho247` geocode SAI thành phố** (id 999/1003 ra Hà Nội, 1007 ra HCM) → route 122–1238 phút. Root cause = geocode trả toạ độ SAI TỰ TIN (Nominatim match tên đường ra tỉnh khác, chỉ ràng `countrycodes=vn`), KHÔNG phải bug routing.
- **Map & Routing — auto-route + API + FE (2026-07-06)** — VIỆC 4/5/6 xong, chi tiết `docs/tech_specs/Map_Routing.md`. Auto-route tin mới sau crawl (`crawler/pipeline.py` cuối `run_source`, chỉ route `route_time_campus IS NULL`) + re-route khi user sửa address (`listings/router.py` `_route_one`). `GET /listings/{id}/route?campus=0|1|2` trả polyline. `ListingOut.route_time_campus` expose ở mọi endpoint đọc. FE `map/MapInner.tsx`: campus picker + "X phút tới trường" + click→vẽ Polyline + popup hiện **address text gốc** + nhãn "vị trí tương đối" khi geocode_confidence≠high (ADR-011). Verify end-to-end: cả 2 container rebuild (`up -d --build api/web`), `ORS_API_KEY` wired qua `.env`+`docker-compose.yml`. `/route` trả polyline thật 132 điểm HTTP 200; `/listings` trả `route_time_campus`; picker+phút xác nhận trên browser (ảnh user). ADR-010 (route thật) + ADR-011 (geocode trần cấp-phường, bác Google/hand-map, budget path Goong) ghi `docs/DECISIONS.md`.
- **Geocode bbox guard (2026-07-06)** — `crawler/geocode.py` `_in_cantho()` chặn Nominatim match tên đường ra tỉnh khác (bug: 3 tin ra Hà Nội/HCM). 3 tin bẩn đã NULL hóa. GOTCHAS.md có mục ORS `[lng,lat]` + bug này.
- **Nearby limit 50→300 (2026-07-06)** — `listings/repo.py:136` `nearby()` limit cũ 50 cắt mất tin (215 visible trong 3km chỉ hiện 50). Nâng 300. Verified endpoint trả 246. GOTCHA còn: `nearby()` CHƯA áp filter sạch như search (lọc mỗi expired/hidden) → map hiện cả tin raw/nhà/mặt bằng — chưa đồng bộ với list, chờ user quyết.
- **Landmark Hồ Bún Xáng (2026-07-06)** — `crawler/geocode.py` LANDMARKS thêm `"bun xang": (10.0318, 105.7641)` xếp TRƯỚC `"dai hoc can tho"` → tin "gần ĐH Cần Thơ" có "bún xáng" snap về hồ (rìa campus, ổ trọ SV thật) thay vì tâm Trường Nông Nghiệp. Tin 991 re-geocode + re-route xong (route `[5.6,7.0,6.7]`). Đây là ngoại lệ có chủ đích của ADR-011 cho 1 hotspot; nguyên tắc "không hand-add landmark diện rộng" vẫn giữ.
- **Marker cluster (2026-07-06)** — `map/MapInner.tsx`: `CircleMarker`→`Marker`+`divIcon` (chấm xanh giữ nguyên) bọc trong `MarkerClusterGroup` (dep `react-leaflet-cluster@2.1.0`, khớp react-leaflet 4.x — bản 4.x đòi react 19, KHÔNG dùng). Lý do: geocode trần cấp-đường/phường (ADR-011) làm ~230 tin dồn lên ~12 toạ độ trùng → marker chồng khít, mắt thấy "vài chấm", 70 tin dưới 1 điểm không bấm được. Cluster hiện badge số + click bung = truy cập được từng tin, KHÔNG gộp data (mỗi tin vẫn record riêng). Verify: `/map` HTTP 200, bundle có markercluster; CHƯA verify browser (không drive được từ CLI). GOTCHA: npm báo 2 vuln (1 critical) khi cài — chưa audit, flag để check sau.

## Đã đóng (phiên 2026-10-01) — Chat realtime giữa SV đã ghép

- **Nền match tối thiểu + chat realtime (mockup 06)** — migration `92_matching_chat.sql` (swipes, conversations, conversation_members, messages, chat_media, user_reports, cột form v2 cho roommate_profiles; đã thêm vào `infra/db/Dockerfile`). Backend `apps/api/app/matching/` (`POST /matching/swipe` thích 2 chiều ⇒ match + hội thoại cùng transaction, `GET /matching/likes`) + `apps/api/app/chat/` (REST + WebSocket `/chat/ws` + hub Redis pub/sub, ảnh re-encode xoá EXIF, seed `python -m app.chat.seed_demo`). FE `/chat`: tab Đã ghép/Lời mời, dải "Mới ghép", đang nhập, online, đã xem, gửi ảnh, chia sẻ tin trọ, gợi ý nhanh, Thành đôi!, báo cáo, huỷ ghép, badge header, fallback polling. Verified: 14 test mới + 139/139 toàn bộ; e2e Playwright 2 trình duyệt 20/20 (API 2 worker). Chi tiết `docs/tech_specs/Chat_Realtime.md`, ADR-012.
- **GOTCHA**: DB volume cũ KHÔNG tự có bảng mới ⇒ apply tay `92_matching_chat.sql` (idempotent). Mật khẩu 4 tài khoản trong `80_seeds.sql` thật ra là `secret`, KHÔNG phải `123456` như `reset_and_seed.sh` in ra (đã kiểm bằng bcrypt). Tài khoản demo chat: `*.demo@example.com` / `demo1234`.
- **Chưa làm (matching core)**: `GET /matching/deck` + thuật toán (lọc cứng → Gower → harmonic), form hồ sơ 12 câu, `import_survey.py`. Mọi đường sinh match mới chỉ cần gọi `matching.repo.create_match()` trong transaction.

## Đã đóng (phiên 2026-08-09)

- **Giao diện mới theo UI_NCKH.html — Trang chủ (mockup 01)** — `apps/web/src/app/page.tsx` viết lại toàn bộ: topbar navy giới thiệu đề tài + SiteHeader + hero xanh (badge số tin THẬT, h1, ô tìm kiếm form GET giữ filter đang bật qua hidden inputs, 5 chip gợi ý map vào filter thật, panel "Dữ liệu hệ thống" fetch số thật qua Promise.allSettled: total + nearby 3km + giá trung vị) + section kết quả (sidebar `HomeControls.tsx` mới: giá min–max nhập TRIỆU đổi ra VND, chip khoảng cách `max_distance_ctu` 1/2/3km, quận/huyện single-select, diện tích tối thiểu; SortSelect giữ nguyên params) + pagination số trang + footer navy. `ListingCard.tsx` restyle theme mới (badge risk trên ảnh, giá xanh + "/ tháng", footer phút tới khu II hoặc freshness). `ListingFilters.tsx` cũ XÓA (thay bằng HomeControls). Block "Thời gian tới trường" trong mockup đổi thành "Khoảng cách tới CTU" vì backend CHƯA có filter theo phút route. Bỏ (chờ module AI): gợi ý cá nhân hóa, chatbot FAB. Verified browser: hero + stats thật (44 tin/24 gần CTU/2.6tr), chip "Dưới 1.5 triệu"→URL→"23 phòng trọ phù hợp"+ô giá tự điền, card đủ ảnh/badge/giá/meta/freshness. GOTCHA pane browser: screenshot hay trả frame trắng sau JS-scroll (compositor lag) — DOM/app không lỗi, chụp cả trang bằng cách resize viewport cao rồi chụp từ scroll 0.
- **Còn theme cũ:** chi tiết tin (`listings/[id]`), form đăng/sửa, login/register, tin của tôi — làm tiếp theo mockup 02.

## Đã đóng (phiên 2026-08-08)

- **Giao diện mới theo UI_NCKH.html — màn Bản đồ (mockup 03)** — theme xanh dương + trắng: token màu `apps/web/tailwind.config.ts` (primary #0b4d8f / bright #1069bd / navy #06305c, ink/line/paper/tint), font Be Vietnam Pro qua `next/font` (`layout.tsx`), header dùng chung `apps/web/src/app/SiteHeader.tsx` (nav Tìm trọ/Bản đồ/Tin của tôi, "Ghép bạn ở" placeholder). Màn `/map` tái cấu trúc: `MapView.tsx`+`MapInner.tsx` XÓA, thay bằng `MapScreen.tsx` (client: sidebar 400px danh sách tin + tabs 3 khu + slider bán kính sync URL `?radius=` qua router.replace + card tin đang chọn nổi trên map) + `MapCanvas.tsx` (Leaflet: divIcon chấm xanh/cluster tròn xanh custom/campus vuông navy + nhãn, vòng bán kính nét đứt, flyTo khi chọn, Polyline route). Card overlay THAY Popup Leaflet — lý do: nhiều tin trùng toạ độ nằm trong cluster, popup không mở được từ danh sách. Verified browser đầy đủ: click list → flyTo + card; click marker → chọn + card; đổi khu → tab + hint + campus marker; slider → refetch server; "Xem chi tiết" → `/listings/{id}`; empty state. Trang chủ + chi tiết CHƯA áp theme mới (còn emerald cũ).
- **Máy mới, DB volume trống — dựng lại môi trường** — Docker chưa bật + volume `pgdata` mới ⇒ 0 tin, thiếu cột `route_time_campus` (migration `50_route_time.sql` trước giờ chỉ apply thủ công, KHÔNG nằm trong init scripts). Fix: apply thủ công vào DB đang chạy + **thêm COPY vào `infra/db/Dockerfile`** để volume mới tự có. Crawl 3 nguồn lấy data thật: phongtro123 37 + mogi 28 + tromoi 17 = 82 tin, nearby 3km = 24 tin.
- **GOTCHA môi trường: chưa có `.env`** — `ORS_API_KEY` trống ⇒ route_time_campus NULL toàn bộ (sidebar/card hiện "Chưa có thời gian di chuyển", không hiện phút) + `GET /listings/{id}/route` fail êm (FE catch, không vẽ đường). Muốn bật: tạo `.env` từ `.env.example` điền ORS_API_KEY rồi `docker compose up -d api` + chạy `route_backfill`.

## Phân công (scope)

- **Lane Claude + user = crawler + data sạch.** Về cơ bản đã bàn giao.
- **Lane team user = 4 module AI** (Recommendation, RAG Chatbot, Roommate Matching, Risk Detection). Schema đã dựng sẵn: cột vector `embedding/preference/matching_vector`, bảng `roommate_profiles/match_requests/user_interactions`. Data đã có `quality_score` + `listing_type` để lọc tập học sạch.

## Đang làm

- **Marker cluster chờ verify browser** — `map/MapInner.tsx` đã wire xong + bundle có markercluster, nhưng CHƯA thấy tận mắt badge số + click bung (không drive browser từ CLI). User cần hard-refresh `localhost:3000/map` xác nhận.
- Working-tree changes chưa commit (`git status`) là toàn bộ công các phiên gần đây (crawler hardening, cleaner 5 tầng, FE listing, badge fix, Map & Routing, 2 fix dưới) — chưa commit.

## Tiếp theo

- (Team) 4 module AI — xem phần Phân công.
- (Nợ, làm trước deploy public) Nâng `next` 14→16 để hết sạch vuln. HIỆN dừng ở `14.2.35` (còn 1 high + 1 moderate, đều DoS/cache-poison/SSRF/smuggling — chỉ dính khi app deploy public hứng traffic; app đang local nên bề mặt ~0). KHÔNG `npm audit fix --force` lúc này: nhảy 2 major (14→16) breaking App Router + middleware auth, rủi ro > lợi khi chưa deploy. Nâng khi lên prod, có thời gian test.

## Đã đóng (phiên 2026-07-08)

- **Filter sạch cho `nearby()` (map = list)** — `listings/repo.py:144` thêm clause `(source='user' OR (cleaning_status='cleaned' AND listing_type='phong_tro'))` khớp `search()`. Trước: map hiện cả nhà/mặt bằng/raw. Verified: 3km quanh CTU 284→190 tin (loại 94 tin không-phải-trọ-sạch); endpoint `/listings/nearby?radius=3000` trả đúng 190 khớp DB. GOTCHA gọi API: param tên `radius` (KHÔNG phải `radius_m`), default 2000m.
- **npm vuln (SỬA THÔNG TIN SAI cũ: vuln KHÔNG từ `react-leaflet-cluster` mà từ `next`)** — bump `next` 14.2.18→14.2.35 (cùng major, không breaking): critical→high. Web verify sau bump: home/map/login đều HTTP 200. Còn nợ nâng next 16 (xem Tiếp theo).

## Gotcha đã dính

- ~14 tin `nhadatcantho247` thiếu district (address nguồn quá ngắn — giới hạn nguồn, không fix được phía mình).
- Classifier `khac`: đã xác minh **0 tin phòng trọ thật lọt `khac`** — bucket toàn nhà riêng/homestay/chung cư/mặt bằng (đúng cần loại). KHÔNG phải bug, không sửa.
- Cần chạy `run_cleaner` cả khi trigger crawler thủ công (`/crawler/run`) để data không kẹt ở trạng thái `raw` — đã xử lý trong `main.py`.

Xem thêm: `DECISIONS.md` (quyết định kiến trúc + lý do), `GOTCHAS.md` (bẫy kỹ thuật tích lũy).

---

## Phiên 04/10/2026 — Hoàn thiện Ghép bạn ở + sửa defect Chat realtime

### Đã xong

**Ghép bạn ở (từ 269 LOC chỉ có swipe → module đầy đủ)**
- Tầng thuật toán THUẦN (không chạm DB/FastAPI, test được không cần Postgres):
  `matching/profile.py` (hằng số form v2 + chuẩn hoá), `filters.py` (lọc cứng 2
  tầng), `score.py` (Gower + điểm có hướng + harmonic mean), `weights.py` (trọng
  số dẫn từ khảo sát, ghi rõ nguồn từng số), `stable.py` (Stable Roommates).
- `survey_map.py` + `import_survey.py`: nạp khảo sát thật → tài khoản + hồ sơ.
  `eval/tools/survey_xlsx_to_csv.py` chuẩn hoá xlsx → CSV (container không có openpyxl).
- API mới: `GET/POST /matching/profile`, `GET /matching/deck`, `GET /matching/passed`.
- `POST /auth/login/ctu` — đăng nhập bằng MSSV (`verify_ctu` không còn là stub).
- Migration `93_matching_deck.sql`: bảng `deck_log` + cột `need_from`/`roommate_status` + index.
- FE `/roommate`: form 12 câu, bộ thẻ có %/3 lý do/1 lưu ý, cảnh báo deal-breaker
  mềm, màn "Thành đôi!", tab Lời mời / Đã bỏ qua. Nav + middleware đã nối.
- `tests/test_matching.py`: 51 test (thuật toán thuần + API).

**Dữ liệu thật đã nạp**: 33 phản hồi khảo sát → **10 tài khoản** (có MSSV), trong đó
**9 vào pool ghép** (nam 6 / nữ 3). Mật khẩu ở `eval/data/.credentials.csv` (gitignored, chmod 600).

**Defect Chat realtime đã sửa**
- BLOCKER: `crawler/scheduler.py` + `/crawler/run` gọi `run_cleaner` đồng bộ trong
  `async def` ⇒ chặn event loop giữ MỌI WebSocket chat. Đã chuyển qua `run_in_threadpool`.
- `chat/repo.py`: idempotency `client_id` từ check-then-insert → `ON CONFLICT DO
  NOTHING` + re-select (hai request song song trước đây ra 500).
- `chat/hub.py`: `publish()` không để lỗi giao realtime thoát ra request path;
  `heartbeat()` dựng lại presence key đã hết hạn (trước đây user online bị báo
  offline vĩnh viễn); `unregister()` dùng `_get_redis()`.
- `chat/router.py`: phát sự kiện `read` sau khi gửi tin ("Đã xem" của đối phương
  trước đây đứng ở tin cũ).
- `matching/repo.py`: **lọc cứng ở đường GHI** — trước đây `swipe` chỉ kiểm "user
  tồn tại" nên POST thẳng `target_id` là ghép được khác giới.

### Kiểm chứng
- `pytest`: **193 passed** (trước phiên: 190, trong đó test_chat phải sửa `_user()`
  vì swipe giờ bắt buộc có hồ sơ — đúng hành vi mong muốn).
- `docker compose build web`: type-check CI xanh, route `/roommate` 6.96 kB.
- Chạy thật trên browser bằng tài khoản demo: deck trả 5 thẻ, điểm 70/65/62/61/52%.
- Thuật toán kiểm trên 19 hồ sơ thật: xem ADR-013/014.
- `stable.py` kiểm bằng brute-force 400 instance ngẫu nhiên: **0 sai**.

### Tiếp theo
- Notebook `eval/notebooks/06_roommate_eval`: P@3/NDCG@3, Wilcoxon, bảng ablation,
  đường cong độ phủ theo N (bootstrap), ILS, Gini exposure.
- Sinh hồ sơ mô phỏng có nhãn bằng bootstrap (pool nữ chỉ 3 người thật).
- Tầng T3 (lộ liên hệ sau 2 lần đồng ý): mới có cột `contact_consent`, chưa có endpoint/UI.
- Các defect FE chat chưa sửa: thread kẹt "Đang tải tin nhắn…" khi 1 request lỗi
  (`ChatApp.tsx`), latch `connecting` trong `useChatSocket.ts` chặn reconnect vĩnh viễn.

---

## Phiên 05/10/2026 — Hồ sơ mô phỏng có nhãn (bootstrap)

`apps/api/app/matching/simulate.py` + `apps/api/tests/test_simulate.py` (23 test).

**Vì sao**: pool nữ thật chỉ 3 người ⇒ mỗi SV nữ thấy pool 2 người trước lọc cứng,
buổi thử nghiệm sẽ ra 0 match ở phía nữ. Thiết kế mục 2.8 ý 3 cho phép đúng việc này.

**Cách làm**: bootstrap **resample nguyên người** rồi nhiễu nhẹ — KHÔNG lấy mẫu độc
lập từng cột (sẽ đúng marginal nhưng phá tương quan giữa các câu, và bảng chéo 2 cột
là lộ). Ba ràng buộc của phép nhiễu:
1. Nhảy một bậc trong **mức thật của form**, không ±1 trên thang số (thang
   `cleanliness` thiếu mức 3, `noise_tolerance` thiếu mức 4).
2. Không tạo tác nhân lọc **cứng** mà donor không có (không đẩy vào vùng "ở bẩn",
   không bật `smoke_in_room`) — sinh ra là sinh rác không ghép được với ai.
3. Deal-breaker chỉ bật/tắt trong tầng **mềm**.

**An toàn / đạo đức**:
- `is_simulated=TRUE` và `src='sim'` là **literal trong câu SQL**, không phải tham số
  ⇒ không có đường sinh ra hàng thiếu nhãn. Nhãn cũng lặp lại bằng chữ trong `bio`.
- Email `sim+<giới><n>@simulated.invalid` (RFC 2606), `password_hash=NULL`, không tạo
  `user_identities` ⇒ không đăng nhập được vào hồ sơ mô phỏng.
- `don_vi` lấy mẫu độc lập và chỉ từ Trường/Khoa có ≥2 người (đơn vị n=1 + giới tính
  + lối sống là đủ nhận ra một người cụ thể). Tên ghép từ hằng số, không lấy từ CSV.
- Tất định theo `--seed`; `--count 30` chứa đúng 20 hàng đầu của `--count 20`.

**Lệnh**:
```
docker cp eval/data/survey_v2.csv "$(docker compose ps -q api)":/tmp/survey.csv
docker compose exec -T api python -m app.matching.simulate --count 24 --dry-run
docker compose exec -T api python -m app.matching.simulate --count 24
docker compose exec -T api python -m app.matching.simulate --reset --count 0
```

**Đo được**: 17 donor (11 nam / 6 nữ; đã loại 2 người khai "ở một mình" vì hồ sơ sinh
ra sẽ bị lọc cứng loại với tất cả). Sinh 24 hồ sơ → qua lọc cứng 134/228 cặp (58,8%),
**0 hồ sơ mô phỏng bị cô lập**. Pool nữ của mỗi SV thật: **2 → 18**. `pytest`: **216 passed**.

**CẦN QUYẾT TRƯỚC BUỔI THỬ NGHIỆM**: deck của SV nữ thật giờ có 7/8 thẻ là mô phỏng
(12 mô phỏng so với 3 thật). Hồ sơ mô phỏng không bao giờ thích lại ⇒ SV quẹt nhiều
mà không ra match thật. Ba hướng: (a) ưu tiên hồ sơ thật khi xếp deck, (b) giới hạn
tỉ lệ thẻ mô phỏng mỗi deck, (c) đặt trước quyết định swipe cho hồ sơ mô phỏng
(thiết kế mục 3.5 ý 5). Chưa làm cái nào.


---

## Phiên 05/10/2026 — Sửa defect FE chat (ChatApp.tsx + useChatSocket.ts)

**Đã sửa và KIỂM CHỨC NĂNG trên browser thật** (không chỉ đọc code):

1. **Thread kẹt "Đang tải tin nhắn…" vĩnh viễn** khi 1 GET `/messages` lỗi. Cờ
   `loadingThread[id]` giờ nhả trong `finally`; lỗi lưu theo từng hội thoại và hiện
   `ThreadErrorState` (lý do + "Tin nhắn vẫn nằm nguyên trên máy chủ" + nút Thử lại).
   *Kiểm*: chặn đúng request `/messages` bằng override `fetch` → hiện màn lỗi, không
   spinner; gỡ chặn → bấm Thử lại → thread nạp bình thường (chứng tỏ cờ đã được nhả).
2. **Reconnect chết vĩnh viễn** khi constructor `WebSocket` throw (URL sai, scheme bị
   chặn, mixed content). Đường throw giờ nhả cờ `connecting`, báo offline, vẫn
   `schedule()`. *Kiểm*: thay `WebSocket` bằng hàm luôn throw rồi đóng socket thật →
   thử lại tại **1.0s / 3.0s / 7.1s** (đúng backoff; bản lỗi dừng ở 1 lần). Trả lại
   `WebSocket` thật + phát `online` → `wake()` nối lại ngay, socket mới `readyState=1`.

Cùng gốc, cùng file (đọc code, CHƯA kiểm chức năng):
3. Lỗi tải danh sách không còn hiện thành "Chưa có ai ghép đôi với bạn" — có dải cảnh
   báo + `EmptyState` nói rõ "đây là lỗi tải dữ liệu".
4. `loadOlder` ("Xem tin cũ hơn") có catch → toast, không còn unhandled rejection.
5. Tin `message.new` tới lúc GET lịch sử đang bay được ĐỆM rồi gộp vào, thay vì bị bỏ
   khỏi thread mà vẫn +1 badge chưa đọc (badge ảo không tắt được).

`docker compose build web`: type-check xanh.

**Bài học quy trình**: báo cáo đầu phiên sai rằng 2 việc này "chưa đụng tới" vì kiểm
bằng `git diff` — mà `apps/web/src/app/chat/`, `apps/web/src/lib/chat/`,
`apps/api/app/chat/` đều đang UNTRACKED, `git diff` không hiện thay đổi trên file
untracked. Kiểm file untracked phải dùng mtime hoặc đọc trực tiếp.

---

## Phiên 05/10/2026 — Tầng T3: lộ liên hệ khi CẢ HAI cùng đồng ý

Thực hiện lời hứa trong form khảo sát: "MSSV và thông tin liên hệ của bạn CHỈ hiện ra
sau khi CẢ HAI BÊN cùng bấm đồng ý kết nối". T3 là lần đồng ý THỨ HAI, tách khỏi
match: với UX vuốt, match rất rẻ — gắn việc lộ liên hệ vào match là phát email cho
năm người lạ sau năm cái vuốt.

**API**
- `GET  /chat/conversations/{id}/contact-consent` → `{mine, theirs, unlocked, waiting_for_other, partner}`
- `POST /chat/conversations/{id}/contact-consent` → bật đồng ý cho CHÍNH người gọi; idempotent
- `GET  /chat/conversations/{id}` cũng kèm khối `contact` cùng hình dạng
- Sự kiện realtime `contact.consent` chỉ là TÍN HIỆU (`user_id`, `unlocked`), không mang email/SĐT

**Lộ gì**: email (luôn có) · SĐT + deep link `zalo.me/<số>` (chỉ khi người đó tự nhập
số — khảo sát không thu SĐT nên hôm nay NULL với mọi hồ sơ thật; không có số thì KHÔNG
vẽ nút Zalo chết). **MSSV không bao giờ lộ**: câu SQL cố ý không JOIN `user_identities`.
Chặt hơn lời hứa (lời hứa nói "chỉ sau khi", không nói "phải") — người ở ghép không cần
MSSV của nhau, và rò mã định danh SV thì không thu lại được.

**Cổng khoá nằm trong SQL** (`chat/repo.py:_CONTACT_SQL`), không ở FE: `NOT EXISTS` thành
viên chưa đồng ý, CỘNG điều kiện người gọi phải là thành viên — thiếu điều kiện sau thì
người lạ gọi thẳng API xem được liên hệ của một cặp đã mở T3.

**Kiểm chứng**
- `tests/test_chat_t3.py`: 11 test (một bên đồng ý không lộ gì · người chưa đồng ý không
  xem được dù bên kia đã đồng ý · người ngoài 404 · MSSV không xuất hiện ở BẤT KỲ body nào
  của 5 endpoint — test gắn MSSV thật trước để assert phủ định không xanh rỗng, và kiểm
  ngược rằng email ĐÃ lộ). `pytest`: **225 passed** (2 skip = test cần CSV trong container).
- Browser thật (hội thoại #4, hai tài khoản demo): Hân bấm → trạng thái chờ, không lộ email
  Thư; Thư bấm qua API → panel của Hân đổi sang đã mở **sau 38 ms** (đường realtime; poll
  là 15s); không SĐT ⇒ không có nút Zalo; gán số giả ⇒ nút "Mở Zalo" → `zalo.me/<số>`,
  `target=_blank rel=noreferrer noopener`. Đã trả dữ liệu demo về như cũ.

**Bổ sung trong phiên** (ngoài phần agent viết): nối sự kiện `contact.consent` vào
`ChatApp.onEvent` (→ `loadDetail`) và thêm vào union `ChatEvent` — trước đó backend
phát sự kiện nhưng FE bỏ qua, người đồng ý trước phải chờ nhịp poll 15s.

**Còn lại**: chưa có endpoint RÚT LẠI đồng ý (thiết kế coi đồng ý là một chiều); kiểu
`ContactState` khai cục bộ trong `ProfilePanel.tsx` thay vì `lib/chat/types.ts` (do lúc
viết agent không được sửa file dùng chung — có thể dời về `types.ts` cho gọn).
