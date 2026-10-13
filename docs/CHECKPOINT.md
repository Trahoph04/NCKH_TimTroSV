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

- **Nền match tối thiểu + chat realtime (mockup 06)** — migration `92_matching_chat.sql` (swipes, conversations, conversation_members, messages, chat_media, user_reports, cột form v2 cho roommate_profiles; đã thêm vào `infra/db/Dockerfile`). Backend `apps/api/app/matching/` (`POST /matching/swipe` thích 2 chiều ⇒ match + hội thoại cùng transaction, `GET /matching/likes`) + `apps/api/app/chat/` (REST + WebSocket `/chat/ws` + hub Redis pub/sub, ảnh re-encode xoá EXIF, seed `python -m app.chat.seed_demo`). FE `/chat`: tab Đã ghép/Lời mời, dải "Mới ghép", đang nhập, online, đã xem, gửi ảnh, chia sẻ tin trọ, gợi ý nhanh, Thành đôi!, báo cáo, huỷ ghép, badge header, fallback polling. Verified: 14 test mới + 139/139 toàn bộ; kiểm tay 2 trình duyệt 20/20 (API 2 worker; script Playwright KHÔNG có trong repo — xem Chat_Realtime.md mục 7). Chi tiết `docs/tech_specs/Chat_Realtime.md`, ADR-012.
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

---

## Phiên 05–06/10/2026 — Hoàn thành `planning/ViecConLai_GhepBan_Chat.md` (trước code freeze 08/10)

Branch `feature/ghep-ban-chat` (từ `main`). Quyết định của nhóm: 1.3 = (a)+(b) · ảnh trong chat = giữ, sửa tài
liệu · 1.5 = trang `/roommate/rate` · cho phép dọn dữ liệu test trên DB dev.

### Đã xong
- **1.1 Commit**: toàn bộ việc các phiên trước vào 8 commit theo nhóm (trước đó chỉ có `Initial commit`). Gỡ
  `.git/index.lock` mồ côi từ 15/09. `_to_delete/`, `exports/` vào `.gitignore`. Tên SV thật trong
  `ViecConLai_GhepBan_Chat.md` thay bằng id trước khi commit.
- **1.2 Đăng nhập MSSV trên web**: tab MSSV/Email ở `/login` (mặc định MSSV; `?via=email`), Route Handler
  `/api/auth/login/ctu`. Kiểm: 10/10 tài khoản khảo sát đăng nhập được qua web (kể cả gõ chữ thường).
- **1.3** (ADR-017) hồ sơ thật trước, thẻ mô phỏng ≤ 50%. Deck SV nữ thật: 7/8 mô phỏng → **2 thật + 2 mô phỏng**.
- **1.4** `/roommate?mode=random` hoặc `ROOMMATE_DECK_MODE=random` (env của web, đọc lúc chạy) + dải "Buổi thử nghiệm".
- **1.5** Chấm làm mù 1–5: `GET/POST /matching/rate`, bảng `roommate_ratings` (mig 94), trang `/roommate/rate`,
  CSV `python -m app.matching.export_ratings` — schema cố định ghi trong file và notebook 06 mục 9.
- **1.6** `eval/notebooks/06_roommate_eval.ipynb` (sinh từ `eval/tools/build_nb06.py`, gọi đúng hàm sản phẩm qua
  `eval/roommate_lib.py`), venv `eval/.venv`. `eval/metrics.py` đã đối chiếu scipy (`eval/test_metrics.py`).
  Số đo: cosine ≥ 0,7 ở **91,4%** cặp cùng giới (93 cặp; tài liệu cũ ghi 93%); harmonic < cộng ở **84/93** cặp (9 cặp
  bằng nhau vì s_ab = s_ba); 1 tầng **6/19** → 2 tầng **16/19**; τ TB độ nhạy ±20% = **0,974** (tệ nhất 0,600);
  Stable Roommates: nữ có, nam không (2 blocking pair); Gini exposure 0,430 → 0,367 khi phạt; trần độ phủ 89,5%
  (người khai "ở một mình"). Mục 9 có khung + dữ liệu GIẢ ghi nhãn, chờ `ratings.csv`.
- **1.7** Dọn DB dev: swipe/match/hội thoại/deck_log của user 25 (giữ tài khoản + hồ sơ), 603 user pytest
  (`mt_ chat_ t3_ crud_`), 75 tin trọ test, 219 hội thoại rỗng. Phiếu in: `python3 eval/tools/print_slips.py` →
  `eval/data/phieu_dang_nhap.html` (gitignored, quyền 600).
- **2.1** ε-greedy 20% (`explore='epsilon'`) · **2.2** lọc thời điểm cần phòng (lệch > 2 tháng) · **2.3** thẻ độ tản
  (`explore='spread'`, chỉ nới tầng khả thi) · **2.4** `decided_ms` phía server · **2.5** lời mời kèm lời nhắn
  (`/matching/invite`, `/invites`, `/invites/{id}/respond`; nút "✉ Nhắn" trên thẻ; lời nhắn hiện ở tab Lời mời cả
  `/roommate` và `/chat`) · **2.6** ghép lại không ghi đè `unmatched` (mig 94 bỏ UNIQUE cũ, partial unique cặp đang
  hiệu lực) · **2.7** pass người đang ghép ⇒ huỷ ghép + xoá hội thoại · **2.9** rate limit (`app/ratelimit.py`).
- **Mục 3 (chat)**: toàn bộ Major + Minor — redirect vô hạn (`?reauth=1`), ảnh giữ chỗ w/h, `CHAT_WS_URL` chuẩn hoá
  + wss theo trang, đếm tin +2, "Thành đôi!" phía bị động, ngừng-nhập khi đổi hội thoại, rò object URL, badge
  gồm lời mời, `next` có query, TOCTOU 500→404, vé WS trước accept + 5 socket/user, cache typing, phân trang hội
  thoại, upload 413 ở ASGI, `media_gc`, hub Redis race + envelope hỏng, đối phương xoá tài khoản. Hai khẳng định
  chưa kiểm của `Chat_Realtime.md` (fan-out nhiều worker, Redis chết) giờ có test (`test_chat_hub.py`).
- **Mục 4**: 4.1 user 2/3 có gender + nhãn mô phỏng (mig 94) · 4.2 chú thích mật khẩu `secret` · 4.3
  `reset_and_seed` chờ qua TCP + bảng migration cuối · 4.4 pytest dùng `nckh_test` (ADR-018).
- **Mục 5 tài liệu**: SRS FR-5.1–5.6, API_Specification (matching, `/auth/login/ctu`, chat; chatbot RAG dời sang
  `/assistant` vì `/chat` đã dùng), KeHoach_NghiemThu 1.2 + kịch bản demo, Thuyet_Minh_Bo_Sung R12–R18,
  Matching_Messaging_Design (as-built 2 tầng, Stable Roommates, deck), Chat_Realtime, `ContactState` về `types.ts`.

### Kiểm chứng
- `pytest`: **256 passed**, 2 skip (cần CSV trong container) — trên `nckh_test`; DB dev không đổi (45 user).
- `docker compose build web` (= `npm run build`, type-check) xanh.
- curl: cookie hỏng → 2 redirect → `/login` 200, cookie bị xoá; `next=/roommate?mode=random` giữ query;
  `next=//evil.com` → `/`.

### Còn lại / chờ
- 2.8 học trọng số từ swipe — **sau** buổi thử nghiệm (thiết kế 3.4).
- 4.5 test_simulate cần CSV trong container (giữ skip — CSV có PII, không đưa vào image).
- 4.6 test ngoài LAN: code đã sẵn (wss/chuẩn hoá URL), chưa chạy thử tunnel thật.
- UI ưu tiên thấp mục 3 (chú thích ảnh, avatar, kéo-thả/dán ảnh, kiểm dung lượng phía client, chặn từ tab Lời mời).
- Mục 6 (đạo đức, sau nghiệm thu) và các quyết định 7.2, 7.4 (rút lại T3), 7.5 (`scheduler.py`/`.env.example` read-only).

---

## Phiên 07/10/2026 — Bản đồ v2 (MapLibre + tiện ích OSM) + nạp gói Chợ Tốt 789

Quyết định của chủ nhiệm: code freeze lùi **10/10**; giữ ORS + lưu sẵn đường đi (không OSRM); ghép code các branch
nhóm (chatbot, risk, trang chi tiết) do **thành viên khác** phụ trách; nhà mini hiện kèm bộ lọc riêng. Spec
`docs/specs/Map_MapLibre_POI.md`, as-built `docs/tech_specs/Map_MapLibre_POI.md`, ADR-019/020.

### Đã xong
- **Bản đồ MapLibre** (`react-map-gl@8` + `maplibre-gl@5` + OpenFreeMap `liberty`), gỡ 4 gói Leaflet. Giữ toàn bộ hành
  vi cũ + cluster GeoJSON, bấm cluster không tách được ⇒ sidebar "N tin chung một vị trí", màu chấm theo `risk_level`.
- **Tiện ích OSM**: bảng `pois` (mig 95) + seed `96_pois_seed.sql` 1.113 điểm (6 nhóm), `GET /pois`, `/pois/summary`;
  card tin hiện "Tiện ích (quanh khu vực) trong 1 km" + bật/tắt lớp; popup tên + khoảng cách chim bay.
- **Gói Chợ Tốt 789** nạp qua `app.crawler.import_catalog` (không dùng DB cổng 5454): 435 trùng giữ nguyên, 354 mới.
  Tin hiển thị **805 → 1.323**; 3 km quanh khu II 418 → 691.
- **Toạ độ trung thực**: Chợ Tốt gán điểm mặc định của phường cho tin không ghim → toạ độ ≥ 2 tin dùng chung hạ
  `high → medium` (1.059 tin), áp cả cho crawler nhatot.
- **Classifier**: loại `nha_mini` (254 tin hiển thị), sửa bug "kho" khớp "không/Khoa", nhận "Trọ …", bỏ "phòng ngủ"
  khi xét phòng trọ; `offer_kind='lease_transfer'` (nhãn Sang nhượng). Phân loại lại bằng `cleaner.reclassify`.
  Khớp nhãn gói 785/789 (đo trên tập dùng để chỉnh — không phải độ chính xác tổng quát).
- **Lọc `housing`** ở `/listings`, `/listings/nearby`, trang chủ + bản đồ; nearby limit 300 → 1000 (cũ cắt mất tin).
- **Cache đường đi** `route_cache` + `route_cache_backfill` (dừng khi hết quota, ưu tiên khu II).
- **Sửa lỗi có sẵn**: nút vẽ đường trên bản đồ gọi thẳng FastAPI từ browser ⇒ bị CORS chặn âm thầm → chuyển qua
  Route Handler; nhãn "khu ii" → "khu II".

### Kiểm chứng
- `pytest` **282 passed**, 2 skip (DB `nckh_test`). `next build` xanh. DB dựng mới từ image (volume trống) nạp đủ
  mig 95 + 1.113 POI ở `nckh` và `nckh_test`.
- Trình duyệt thật: cluster → danh sách 277 tin chung toạ độ → chọn tin → đường đi + tiện ích + popup; tab Nhà mini
  (156 tin/3 km); đổi khu III; trang chủ `?housing=nha_mini` 254 tin có nhãn.
- Backup bảng `aggregated_listings` trước khi ghi: chỉ ở scratchpad phiên (không lưu repo).

### Còn lại / chờ
- **Route cache mới 61/140 toạ độ mỗi khu** (874/1.312 tin có đường tới khu II): ORS Directions trả 403 "Quota
  exceeded" ngày 07/10. Chạy lại sau 7h sáng: `docker compose run --rm --no-deps -T api python -m
  app.listings.route_cache_backfill --apply`. Nên chạy trước buổi tập demo.
- `nckh_test` trên DB đang chạy đã apply tay mig 95 + 96; máy khác: `create_test_db.sh --recreate` sau khi rebuild image db.
- Màu marker theo rủi ro + review/khiếu nại trên bản đồ (kịch bản demo bước 2) phụ thuộc nhánh risk của nhóm khi ghép.
- Chưa commit (chờ chủ nhiệm duyệt). Thư mục gói 789 đã gitignore.

---

## Phiên 07/10/2026 (2) — Gợi ý nhà trọ (module B)

Quyết định của chủ nhiệm: buổi thử nghiệm **09/10**; so **3 hệ** trong đánh giá mù; **bỏ yếu tố an ninh** (ghi hạn chế).
Spec `docs/specs/Recommendation.md`, as-built `docs/tech_specs/Recommendation.md`, ADR-021.

### Đã xong
- **Thuật toán** `app/recommend/core.py`: knowledge-based — lọc cứng + tự nới (báo rõ) → MAUT, trọng số = tần suất top-3
  của 31 SV khảo sát (an ninh bỏ) co rút về 3 yếu tố người dùng chọn, tiện ích "chưa rõ" θ = 0,5 → MMR λ = 0,7 → lý do
  + "nên hỏi chủ trọ". 2 hệ đối chứng: B-giá (lọc + sắp giá), B-cosine (thiết kế gốc 03).
- **Bằng chứng bác cosine** (DB thật): cosine thô ≥ 0,9999 ở 100% tin; cosine chuẩn hoá chỉ 35% top-10 thoả tiêu chí.
- **Offline 31 bộ tiêu chí**: đề xuất thoả 92% · ILS 0,28 · 9,9/10 vị trí khác nhau · độ phủ 66; B-giá độ phủ chỉ 20.
- **API** `/recommend`, `/recommend/prefill`, `/recommend/eval/{session,judge}`; mig **97** `rec_eval_*`.
- **Web** `/goi-y` (form theo đúng câu khảo sát, kết quả có %, lý do, cần hỏi, giải thích trọng số) + `/goi-y/danh-gia`
  (thẻ mù, chấm 0–2); header "Gợi ý", nút ở trang chủ; giá < 1 triệu hiện "750 nghìn" (trước "0.8 triệu").
- **Notebook 01** dựng lại từ `eval/tools/build_nb01.py` (gọi code sản phẩm): trọng số (assert khớp CSV), bác cosine,
  offline 3 hệ + biểu đồ, độ nhạy, khung online (P@10 chặt/lỏng, NDCG@10, KTC bootstrap, Wilcoxon) — đang chạy bằng
  dữ liệu giả có nhãn.

### Kiểm chứng
- `pytest` **298 passed**, 2 skip; `next build` xanh; trình duyệt: `/goi-y` và `/goi-y/danh-gia` (lượt thử đã xoá).

### Còn lại / chờ
- **09/10**: buổi thử nghiệm → `export_judgments` → chạy lại notebook 01 → số P@10/NDCG@10 thật cho chương 4.
- Trước buổi: chạy `route_cache_backfill` (quota ORS), không crawl/reclassify trong lúc thử nghiệm, chuẩn bị phiếu SUS.
- Chưa commit.

---

## Phiên 07/10/2026 (3) — Dọn dữ liệu: chỉ giữ tin sạch + chọn 5 tin demo

Chủ nhiệm: bản đồ vón cục; nhóm đang khảo sát để có bộ dữ liệu riêng ⇒ **loại hẳn mọi tin chưa sạch** (ADR-022).

### Đã xong
- Nguyên nhân vón cục: 840 tin Chợ Tốt dồn vào 6 điểm mặc định của phường; chỉ 78 tin có toạ độ riêng.
- `app.cleaner.audit` (mig 98 `audit_reason`): 1.323 → **18 tin** hiển thị. Loại: vị trí cấp phường 1.212 · ngoài phạm vi
  45 · đã gỡ khỏi nguồn 27 (`expired`) · không toạ độ 11 · sai đường 4 · tin mẫu 3 · giá bất thường 1 · thiếu ảnh 1 ·
  sang nhượng 1. Sao lưu trước khi ghi: scratchpad phiên (`aggregated_listings_before_audit.dump`).
- **5 tin demo** (đều: toạ độ người đăng tự ghim/số nhà, nằm đúng đường theo OSM, còn sống trên nguồn 07/10, diện tích
  thật, ≥ 6 ảnh): **#1598** phòng SV 108/31 CMT8 (2 tr · 25 m², điện/nước/cọc rõ) · **#1635** Nguyễn Trãi (2 tr · 16 m²,
  11 ảnh, 59 tiện ích/500 m) · **#4711** d20B Trần Khánh Dư (2,5 tr · 3 phút tới cả 3 khu) · **#1215** căn hộ dịch vụ
  1 Nguyễn Bỉnh Khiêm (nhà mini 3 tr, 41 ảnh) · **#4712** hẻm 309 Hoàng Quốc Việt (1,8 tr, gần khu I).
- Bắt thêm "Pass hợp đồng" là sang nhượng; test `test_audit.py`.

### Còn lại / chờ
- **Đường đi**: 7/18 tin có `route_cache` (2/5 tin demo: 4711, 4712). ORS Directions vẫn 403 lúc 12h20 ⇒ chạy lại
  `docker compose run --rm --no-deps -T api python -m app.listings.route_cache_backfill --apply --ids 1598,1635,1215,4711,4712`
  khi quota hồi (hoặc dùng key ORS khác trong `.env`).
- Buổi chấm mù gợi ý 09/10 trên 18 tin: pooling 3 hệ sẽ phủ gần hết danh mục ⇒ so sánh yếu. Nên nạp bộ dữ liệu khảo
  sát trước 09/10 (dùng lại đường `import_catalog` → `audit`), hoặc chấp nhận và ghi hạn chế.
- Notebook 01 offline đang là số của danh mục TRƯỚC rà soát (1.312 tin) — chạy lại khi có dữ liệu mới.
- Đừng crawl lại khi chưa muốn: tin cấp phường sẽ quay lại ⇒ phải chạy `audit` sau crawl.

---

## Phiên 07/10/2026 (4) — Thêm lại dữ liệu crawl, lọc "phù hợp", bản đồ chỉ cắm tin chính xác

Chủ nhiệm: 18 tin quá ít ⇒ thêm lại dữ liệu crawl, "lọc bớt cho phù hợp" (ADR-022 sửa đổi).

### Đã xong
- Khôi phục 1.229 tin thật bị ẩn vì vị trí; vẫn loại tin đã gỡ/tin mẫu/ngoài phạm vi/giá bất thường.
- Crawl Chợ Tốt full: 857 tin đang đăng, **126 mới**, 217 cập nhật. Sửa lỗ hổng: `run_nhatot` không tự tính phút tới
  trường ⇒ tách `crawler/pipeline.py:auto_route` dùng chung (126 tin mới đã có phút).
- `audit --policy system --network --nhatot-seen-since <mốc crawl>`: **1.005 tin** (21 vị trí chính xác, 984 cấp phường;
  204 nhà mini; 560 trong 3 km khu II). Loại 367: đã gỡ 298 (tin nhatot không thấy trong crawl — mẫu 29/30 = 404),
  thiếu ảnh/mô tả 38, trùng 11, không toạ độ 11, sang nhượng 6, giá 2, ngoài phạm vi 1.
- Mig **99** `location_precise`; API trả cờ này; `/map` mặc định chỉ cắm tin chính xác (13 trong 3 km) + ô "Hiện cả N tin vị
  trí gần đúng". 5 tin demo vẫn giữ, đều chính xác.
- Test: chế độ system giữ tin cấp phường nhưng vẫn loại tin bẩn cấp phường. Toàn bộ pytest xanh.

### Còn lại
- 180 tin nguồn khác (phongtro123…) kiểm sống bằng HTTP: 0 trả 404, nhưng các trang này có thể vẫn 200 dù tin đã hết hạn
  ⇒ chưa chắc còn phòng; crawl lại các nguồn HTML (`recrawl_all.sh`) rồi chạy `audit` nếu cần chắc chắn.
- Đường đi (`route_cache`) cho tin chính xác mới + 3 tin demo: chờ quota ORS Directions.
- Notebook 01: chạy lại `export_snapshot` + notebook với danh mục 1.005 tin.

---

## Phiên 07/10/2026 (5) — Nạp bộ dữ liệu khảo sát thực địa của nhóm (8 nhà trọ)

### Đã xong
- `app.crawler.import_survey` (đọc Excel bằng zip+XML, chạy lại được; khoá `survey`/`KS-<STT>`): giá "1tr7", "3,6tr - 4 tr"
  (lưu cận dưới, ghi nguyên văn khoảng giá vào mô tả), "950k"; toạ độ "lat, lng" → `high` + `location_precise`; quận từ
  địa chỉ hoặc tin gần nhất; tiêu đề ngắn ("M20B") ghép địa chỉ; liên hệ → `contact_*` (UI KHÔNG hiển thị).
- Ảnh: `eval/tools/prepare_survey_images.py` mã hoá lại (bỏ EXIF, ≤ 1600 px) → `apps/web/public/khao-sat/` (24 ảnh, 3,7 MB).
  File Excel gốc (có SĐT chủ trọ) để ngoài repo.
- Kết quả: **7/8 nhà hiển thị** (KS-003 thiếu giá → cleaner loại, chờ bổ sung); cả 7 có vị trí chính xác + phút tới 3
  khu; diện tích nhóm không đo thì để trống (không dùng số tự điền); 2 tin khảo sát lọt top-10 gợi ý (2 tr, khu II).
- `audit`: nguồn `survey` tính là vị trí chính xác, không kiểm "còn trên nguồn", miễn luật ≥ 3 ảnh (mô tả ≥ 20 ký tự).
- Sửa trích giờ giấc: "chìa khoá cổng riêng" bị hiểu là giới nghiêm; thêm "không quản lý giờ giấc" = tự do (sửa luôn
  3 tin crawl gắn nhầm).

### Còn lại
- KS-003 (Trọ Kiểu Tiên): bổ sung giá (và ảnh) vào Excel rồi chạy lại lệnh nạp. KS-003, KS-004 chưa có ảnh.
- Hỏi chủ trọ về việc công khai SĐT/Facebook trước khi hiện liên hệ trên trang chi tiết (NĐ 13/2023).

---

## Phiên 07/10/2026 (6) — Bản đồ hiện lại tin crawl (dữ liệu quá ít)

Chủ nhiệm: bản đồ chỉ còn tin chính xác thì quá ít (19 tin/3 km) ⇒ hiện lại tin crawl cấp phường.
- `/map` mặc định hiện **tất cả** (566 tin/3 km), 2 lớp MapLibre riêng: tin chính xác (chấm đặc + cụm xanh, nằm trên) và
  tin cấp phường (chấm rỗng + cụm xám, nằm dưới) — tin chính xác không bị nuốt vào cụm hàng trăm tin. Chú giải bằng hình
  dạng + chữ. Ô "Chỉ hiện N tin vị trí chính xác" cho lúc demo gọn. `isLocationPrecise` chuyển về `lib/format.ts`.
- Kiểm trên trình duyệt: cụm xám 228 (Hưng Lợi), 83, 51…; chấm xanh của tin chính xác + khảo sát vẫn tách riêng.

---

## Phiên 07/10/2026 (7) — Hiện liên hệ: có SĐT thì hiện, không thì "Xem tin gốc"

- `GET /listings/{id}/contact` (`ContactOut`: phone, zalo, facebook, source, source_url) — endpoint RIÊNG, số không nằm
  trong ListingOut nên không lấy hàng loạt qua /listings, /nearby; tin bị ẩn → 404. Route Handler `/api/listings/[id]/contact`.
- Trang chi tiết: khung "Liên hệ chủ trọ" — có số: nút gọi (tel:) + Zalo/Facebook nếu có + link tin gốc phụ; không số: nút
  "Xem tin gốc trên Chợ Tốt/Phongtro123 ↗". Thẻ tin trên bản đồ: dòng gọi / Facebook / tin gốc.
- Phủ dữ liệu (1.012 tin hiển thị): 105 có SĐT (phongtro123 97, khảo sát 6, Chợ Tốt 2), 2 Facebook, 1.005 có link nguồn.
- Sửa trích tiền điện ("diện tích" bị đọc thành "điện") — xem GOTCHAS. Toàn bộ pytest xanh.

---

## Phiên 07/10/2026 (8) — Sửa mất đường đi trên bản đồ + bản đồ nhỏ ở trang chi tiết

- **Nguyên nhân mất đường đi**: ORS Directions hết quota (403) và cache khu II chỉ có 39/102 toạ độ ⇒ tin chưa có cache
  không vẽ được đường. Sửa: OSRM công khai làm dự phòng (`routing.py:route_geometry_osrm`, profile cache `osrm-driving`),
  router đi theo thứ tự cache → ORS → OSRM; backfill `--engine osrm` (+ `--ids`). Sau backfill (185/186 lượt): khu I 102/102, khu II 102/102,
  khu III 101/102 toạ độ có sẵn đường. Card hiện "Đang vẽ đường đi…" / "Chưa vẽ được đường đi tới khu X lúc này".
- **Bản đồ nhỏ** (`listings/[id]/MiniMap.tsx` + `MiniMapCanvas.tsx`): hình tròn cố định góc dưới phải, khung vừa tin + khu
  CTU gần nhất (theo phút thật, `lib/campus.ts:nearestCampus`), chấm đặc/rỗng theo `location_precise`, dòng "N phút tới
  khu X"; nút × để ẩn. Bấm → `/map?radius=5000&focus=<id>&campus=<khu>`: bản đồ lớn chọn sẵn tin, đúng khu, vẽ đường.
- Kiểm trên trình duyệt (tin 1598 và tin đầu danh sách, khu I/II/III đều có đường). pytest **308 passed, 2 skip**.

### Còn lại
- Đường vẽ bằng OSRM có thể lệch nhẹ so với số phút ORS Matrix; ORS Directions vẫn hết quota.
- Bản đồ lớn chưa tự zoom vừa đường đi khi đổi khu (đường có thể chạy ra ngoài khung).

---

## Phiên 08/10/2026 — Ghép chatbot từ GitHub (branch `PHUC`) + nạp bộ khảo sát mở rộng (dataset 2)

**Dữ liệu khảo sát** (`~/dataset 2`: 20 nhà trọ, 73 ảnh — 8 nhà cũ trùng từng byte, thêm KS-009…KS-020):
- Ảnh qua `prepare_survey_images.py` (bỏ EXIF) → `apps/web/public/khao-sat/` 73 ảnh; `import_survey --apply`: 12 tin mới,
  12/12 cleaned + có phút tới 3 khu. **19/20 tin khảo sát hiển thị** (16 phòng trọ, 3 nhà mini); KS-003 vẫn loại vì thiếu giá.
- Sửa: quận suy từ tin lân cận lấy `district_norm` (trước ra "Ninh Kiều, Cần Thơ"); `classify(…, source)` — tin khảo sát
  chỉ có tên trọ xếp `phong_tro` thay vì `khac` (KS-011, KS-015, KS-016 trước đó bị ẩn); `reclassify` chỉ đổi đúng 3 tin.
- Tổng tin hiển thị: **1.024**.

**Chatbot** (ADR-023 — chỉ chatbot, không ghép risk/reports/admin/engagement của branch):
- Backend `app/room_service/{chatbot,legal_knowledge}` — `POST /chatbot/ask`, `GET|DELETE /chatbot/conversations[/{id}]`,
  `POST /chatbot/feedback`, `/admin/documents` (admin bật/tắt nguồn), `GET /health/ai`. Mig **100_chatbot.sql** (gộp phần
  chatbot của mig 90–101 bên PHUC), đã áp tay vào `nckh` và `nckh_test`.
- Corpus `apps/api/chatbot_corpus/` (44 JSON + manifest) → schema `legal_ctu_v1`: **44 tài liệu / 530 đoạn / 530 vector E5**;
  vector cho **1.024/1.024** tin đang hiển thị.
- Web: widget nổi ở `layout.tsx` (ẩn trên `/chat`; né nút zoom `/map`, sang góc trái ở trang chi tiết vì MiniMap), trang
  `/tro-ly` + mục "Trợ lý AI" trên header, proxy `/api/chatbot/[...path]`; chưa đăng nhập ⇒ nhắc đăng nhập.
- Image API cài torch CPU + sentence-transformers (`INSTALL_ML`, mặc định true), volume `models` cho cache E5.
- Kiểm: pytest **563 passed, 20 skip, 1 xfail** (xfail = `test_incomplete_exception_is_not_safe_evidence`, fail sẵn trên
  code PHUC gốc); test lịch sử DB opt-in 22/22. Hỏi thật qua HTTP: tìm phòng (hybrid, đúng bộ lọc giá/quận/máy lạnh; tin
  khảo sát KS-010 đứng #1 cho câu "Mậu Thân 2 triệu"), tiền điện (trích đúng K5 Đ12 TT 60/2025), KTX (đúng 3 nguồn CTU).
  Đã xoá hội thoại thử. Kiểm trên trình duyệt: widget, vị trí nút ở `/map` và trang chi tiết.

### Còn lại
- **Chưa có key Gemini** ⇒ câu pháp lý/KTX thường ra template/trích nguyên văn (qwen2.5:7b bị bộ kiểm chứng bác nháp).
  Thêm `GEMINI_API_KEY` vào `.env` rồi `docker compose up -d api`; muốn đúng flow PHUC đo 36 câu thì thêm
  `CHATBOT_AGENTS_ENABLED=true` (+ Graph RAG — chưa dựng ở repo này).
- Ollama phải chạy trên máy host (`ollama serve`); model mặc định `qwen2.5:7b-instruct` (PHUC dùng `qwen3.5:9b`).
- Trang admin `/admin/documents` mới có API, chưa có giao diện (repo chưa có khu admin).
- Sau mỗi lần crawl/import: `python -m app.room_service.chatbot.index_listings` để tin mới có vector.
- Báo Phúc: test `test_incomplete_exception_is_not_safe_evidence` fail trên branch PHUC.

**Logo mới (08/10, cùng phiên)** — ảnh gốc của nhóm (`~/Documents/Screenshot/logo.png`, nền trắng) tách thành
`apps/web/public/brand/{logo,logo-mark,logo-wordmark}.png` (nền trong suốt) + favicon `src/app/icon.png`, `apple-icon.png`.
Dùng ở header (hình nhà + chữ "NhàTrọ CTU"), đầu widget trợ lý, trên form đăng nhập/đăng ký. Tiêu đề trang và các
câu chữ vẫn ghi "Trọ CTU" — chưa đổi tên thương hiệu.

**Bỏ đăng tin + cẩm nang tạm (08/10, cùng phiên — ADR-024)**
- API ghi tin chỉ admin (`require_admin`), `GET /listings/managed` thay `/listings/mine`; sửa tin crawl/khảo sát ⇒ 409, ẩn
  thì được. Web: bỏ "Tin của tôi"/"Đăng tin miễn phí"; `/quan-ly/nha-tro` (admin), `/listings/new|[id]/edit` admin-only
  (khác ⇒ 404); trang chi tiết: nút Sửa (tin nhập tay) + "Ẩn tin" chỉ cho admin; `/listings/<không phải số>` ⇒ 404.
- `/cam-nang`: 3 mục (tìm phòng 6 thẻ, ở ghép 4 thẻ, pháp lý & hợp đồng 7 thẻ), ý pháp lý có căn cứ + link văn bản gốc
  (BLDS Đ328; Luật Nhà ở Đ163/170/172; Luật Cư trú Đ27–28; NĐ 58/2026; TT 60/2025 Đ12 k5; QĐ 215 Cần Thơ; Luật PCCC Đ20;
  cảnh báo Bộ Công an). Số liệu thực tế từ tin trên hệ thống: điện 4.000đ/kWh (581 tin), nước 10–12k/m³ (441) hoặc
  70–100k/người (116), cọc 1 tháng (503). Bài nhaminhbach.com/tips và bài H.Mai được viết lại, ghi nguồn, không chép.
- pytest **567 passed**, 20 skip, 1 xfail. Hiện chỉ `admin@ctu.edu.vn` (seed) là admin.

**Chatbot — Gemini đã bật (08/10, tối)** — khoá nhóm dạng `AQ.…` hợp lệ (45 mô hình; `gemini-3.5-flash-lite` và `3.1-flash-lite` có thật). Cấu hình
chọn: Gemini sinh trực tiếp (`gemini-3.5-flash-lite`), Qwen local dự phòng, **tắt** luồng nhiều tác nhân. Đo bằng 36 câu pháp lý/KTX của
Phúc qua HTTP thật (mỗi câu một hội thoại): 0 lỗi; 27 đầy đủ / 9 một phần theo cờ của chính hệ thống (KHÔNG phải chấm theo đáp án chuẩn);
trung vị 14,9 s (p90 20 s, tổng 8 phút) so với 70–85 s/hay rơi template khi chỉ có Qwen. Luồng nhiều tác nhân kém hơn: trên 14 câu, 12 một
phần (trực tiếp 9) và làm hỏng 4/5 câu vốn tốt ⇒ không bật. Bộ kiểm tra thứ 2 (17 ca): tìm phòng thỏa ràng buộc giá/quận/tiện ích; không bịa
số liệu; từ chối soạn hợp đồng; không lộ SĐT chủ trọ. Lỗi còn lại: câu ngoài khu vực ("phòng ở Hà Nội") vẫn trả tin Cần Thơ không báo; tình huống
khẩn cấp ("bị chủ trọ đe doạ") bị coi là tìm phòng; "mức phạt…" trả đoạn luật không liên quan; "rẻ hơn" ở lượt sau không hiểu; corpus thiếu biểu giá
điện/mức phạt. Không cần huấn luyện lại mô hình — sửa định tuyến câu hỏi + bổ sung nguồn.

**Chatbot — sửa lỗi sau đánh giá (08/10, đêm)** — KHÔNG huấn luyện lại mô hình (hệ thống chỉ dùng mô hình có sẵn); sửa quy tắc và nội dung:
- Mới `chatbot/scope.py` (+ `tests/test_chatbot_scope.py`): tình huống khẩn cấp (bạo lực/cháy/y tế/tự làm hại → 113/114/115, đi trước mọi bước, xét trên tin nhắn gốc);
  ngoài khu vực ("phòng ở Hà Nội" → báo chưa có dữ liệu; Sóc Trăng/Hậu Giang tính là Cần Thơ); "rẻ hơn/gần hơn/rộng hơn" so với tin lượt trước (`repo.shown_stats`).
- Kho: nạp Nghị định 282/2025/NĐ-CP (xử phạt VPHC, có cư trú; 41 đoạn, nguyên văn từ Word, dựng bằng `chatbot_corpus/tools/build_word_source.py`) ⇒ 45 tài liệu / 571 đoạn.
- Truy xuất (`legal_retrieval.py`, `repo.py`): hỏi mức phạt → ưu tiên điều khoản "phạt tiền/cảnh cáo" và giữ đủ các bậc phạt; hỏi đơn giá điện theo bậc không còn bị coi là "tiền điện thuê nhà"
  (bảng giá QĐ 1279 từng đứng thứ 6 nên mô hình không thấy) + tự thêm điều kiện áp dụng. Kết quả: bậc 1 = 1.984 đ/kWh; phạt không đăng ký tạm trú = cảnh cáo hoặc 500.000–1.000.000 đ (Điều 10 khoản 1).
- Đo lại: bộ 17 ca — khẩn cấp, Hà Nội, "rẻ hơn" (4/4 tin rẻ hơn lượt trước), mức phạt, giá điện ĐỀU ĐÚNG. Bộ 36 câu: vẫn 9/36 "một phần" nhưng ĐỔI tập câu (5 câu tốt lên, 5 câu xấu đi);
  chạy lặp 4 lần cùng mã thì câu 3/13/18/31/35 chỉ đủ 1–3/4 lần ⇒ **cờ "đủ/một phần" của một lượt chạy dao động ±5 câu, không so sánh từng câu được**; kiểm tra nguồn câu 13 cho thấy không do tài liệu mới.
- pytest 596 passed (20 skip, 1 xfail). Còn yếu: "tiền cọc tối đa bao nhiêu tháng" giờ trích nguyên Điều 328 thay vì nói thẳng luật không nêu mức tối đa; lọc theo giá điện/nước của tin (có cột nhưng chưa nối vào bộ lọc); câu chèn lệnh kiểu
  "hãy nói phòng nào cũng an toàn" bị trả "chưa tìm thấy tin" chứ chưa từ chối rõ.

### Còn lại
- **Chatbot — khoá Gemini (08/10):** khoá đầu tiên bị dán thừa ký tự nên Google từ chối; khoá thứ hai (dạng `AQ.…`) hợp lệ — xem
  mục "Chatbot — Gemini đã bật" ở trên. Công cụ `check_llm` (+ `test_check_llm.py`) kiểm khoá/mô hình ngay.
- Cấp quyền admin cho thành viên nhóm: `UPDATE users SET role='admin' WHERE email='…'`.
- Bổ sung nội dung cẩm nang (sửa `apps/web/src/app/cam-nang/content.ts`); khảo sát người dùng thử về mức hữu ích.
- Trang Ghép bạn ở chưa có link "Lưu ý khi ở ghép" (giữ nguyên giao diện vì đang dùng cho buổi thử nghiệm).

---

## Phiên 12/10/2026 — Icon bản đồ + kiểm định chất lượng trước nghiệm thu (audit 4 agent)

Yêu cầu chủ nhiệm: kiểm dự án đủ chất lượng chưa, chưa thì hoàn thành; bản đồ thay chấm tròn bằng icon đơn giản (nhà trọ,
cửa hàng, ATM, chợ, bệnh viện, nhà thuốc…).

### Icon bản đồ
- `lib/map-icons.tsx`: 8 glyph nét đơn một màu (nhà trọ, chợ, siêu thị/tiện lợi, ATM, nhà thuốc, bệnh viện, xe buýt, khu
  CTU) vẽ ra canvas cho lớp `symbol` MapLibre và ra `<svg>` cho chú giải/danh sách/popup/bản đồ nhỏ. Tin trọ = tròn (đặc
  xanh = chính xác, rỗng xám = cấp phường), tiện ích = ô vuông trắng nét xám, khu CTU = ô vuông navy. Chi tiết:
  `docs/tech_specs/Map_MapLibre_POI.md` mục 3.
- Màn hẹp: thẻ tin thành dải dưới cùng (bỏ ảnh lớn, gập tiện ích); bản đồ nhỏ trang chi tiết nằm trong dòng nội dung.

### Kiểm định (theo `~/Downloads/dynamic_workflow_4_agents.md`)
Tech Lead + Haiku (cấu hình/CI/docs/smoke 19 trang) + Sonnet (frontend, 17 phát hiện) + Opus (phân quyền/bảo mật, 8 phát
hiện). 94 nghìn token đầu ra; lần thử trước với 8 agent song song bị chặn 2 lần vì hết hạn mức phiên.
- Dữ liệu: 1.115 tin hiển thị, 0 thiếu giá/toạ độ, 0 ngoài Cần Thơ, 0 giá/diện tích bất thường, 0 trùng, 1 thiếu ảnh;
  5 tin demo còn sống, vị trí chính xác.

### Đã sửa
- **Bảo mật/dữ liệu**: `POST /crawler/run` chỉ admin + whitelist nguồn + 1 lượt/nguồn (CLI `app.crawler.run_once`,
  `recrawl_all.sh` đổi theo); lượt full lỗi/thiếu tin không quét expired; crawl không hồi sinh tin bị audit loại, không
  đụng tin `hidden`; Postgres/Redis chỉ mở `127.0.0.1` (docker-compose); route `[id]` chỉ nhận id số; open redirect
  `/login?next=/\evil.com`.
- **Dữ liệu sai**: lọc quận qua `district_norm` (Bình Thủy 8 → 39 tin); đổi toạ độ thì xoá phút tới trường cũ + route lại 21
  tin (9 tin sai thật, vd. #1017 `{4,0,3.4}` → `{3.8,3.4,0.1}`; bản sao lưu ở scratchpad phiên); "0 phút" → "quanh khu II".
- **Frontend**: trang chủ 500 khi URL sai kiểu; menu điện thoại (trước không có đường tới bản đồ/chat trên điện thoại);
  `/api/auth/me` trả `role` ⇒ link "Quản lý" hiện cho admin; bộ lọc trang chủ đồng bộ URL; form đăng ký/tin sập khi 422;
  nhãn ngân sách/giờ ngủ trong chat khớp form ghép bạn; "vị trí tương đối" cùng tiêu chí `location_precise`; bản đồ nhỏ
  của tin > 5 km mở đúng tin; ghi/sửa/ẩn tin tự refresh token; tab ghép bạn (Đổi ý, Thử lại, hết thẻ tự tải); đổi khu nhanh
  không vẽ nhầm đường; IME tiếng Việt trong trợ lý; giá "750 nghìn" thống nhất; aria-label nút icon.
- Kiểm: pytest **604 passed**, 20 skip, 1 xfail; `tsc` sạch; `next build` xanh; trình duyệt (desktop + khung 390 px).

### Quản lý người dùng (cùng ngày, chủ nhiệm đồng ý làm — thuyết minh dòng 4)
- Mig **101** `users.locked_at` (COPY `98d-user-admin.sql`; đã áp tay `nckh` + `nckh_test`). Module `app/admin_users`:
  `GET /admin/users` (tìm email/tên/MSSV, lọc admin/bị khoá), `PATCH /admin/users/{id}` (quyền, khoá). Khoá có hiệu lực
  ngay (deps đọc DB mỗi request), chặn login/login MSSV/Google/refresh; không tự khoá/tự hạ quyền, luôn còn ≥ 1 admin.
- Web `/quan-ly/nguoi-dung` + tab "Nhà trọ | Người dùng"; thao tác bấm 2 lần để xác nhận. Không xoá tài khoản (giữ lịch sử
  chat/chấm mù làm số liệu). Test `test_admin_users.py` (6 ca). pytest **611 passed**.

### Đánh giá nhà trọ (cùng ngày — thuyết minh dòng 6, ADR-025)
- Mig **102** (unique 1 đánh giá/tài khoản/tin, `updated_at`; COPY `98e-reviews-ugc.sql`, đã áp `nckh` + `nckh_test`).
  Module `app/reviews`: `GET/POST /listings/{id}/reviews`, `GET|DELETE …/reviews/mine`, `GET|PATCH /admin/reviews`.
  `ListingOut.rating_avg/rating_count`. Tên người viết rút gọn ("Phú T.H.").
- Web: khu "Đánh giá của sinh viên" ở trang chi tiết (tóm tắt, phân bố sao, tag, cảnh báo khi ≥ 2 người báo cùng tag xấu,
  form sao + "Bạn là" + 12 tag + nhận xét); "★ 4,2 (5)" ở thẻ tin, danh sách + thẻ bản đồ; `/quan-ly/danh-gia` ẩn/hiện.
- Thử end-to-end trên production bằng tài khoản mẫu (gửi → điểm 4,0 hiện → chặn SĐT → xoá về 0).
- Rà soát (1 agent Sonnet) + sửa: regex SĐT không chặn nhầm khoảng giá/năm; đánh giá bị ẩn không xoá được (409) để thoát
  kiểm duyệt; chủ tin không tự đánh giá; tài khoản bị khoá: WebSocket chat từ chối + socket đang mở bị đóng 4403 (sự kiện
  `account.locked` qua hub), ra khỏi bộ thẻ ghép bạn; ô tìm admin escape `%`/`_`; "Xem thêm đánh giá", xoá bấm 2 lần.
  pytest **621 passed**, 20 skip, 1 xfail.

### Còn lại / chờ quyết định
- **Đánh giá chưa có dữ liệu**: nhóm cần thu đánh giá THẬT trước nghiệm thu (thành viên đã khảo sát 20 nhà ghi theo quan
  sát thực địa — chọn "Đã đi xem phòng"; SV đang thuê). Không tạo đánh giá mẫu.
- SĐT chủ trọ thu qua khảo sát: chủ nhiệm xác nhận 12/10 đã có đồng ý của chủ trọ cho công khai.
- `.env.example` (read-only) thiếu biến chatbot/Gemini/`COOKIE_SECURE`… — đã có mặc định trong compose; ghi ở Deployment
  Guide nếu cần. `Diagrams/tools/plantuml.jar` 22 MB nằm trong git (chỉ là vệ sinh repo).
- Sau khi kéo code: `docker compose up -d --build` (đổi cổng db/redis cần tạo lại 2 container này).

### Giao diện (cùng ngày, theo đề nghị chủ nhiệm)
- Bản đồ: cụm tin cấp phường hết màu xám — mọi cụm là nhãn "🏠 + số" họ xanh (đậm = vị trí chính xác, nhạt = cấp phường),
  chấm tin lẻ cấp phường đổi xanh nhạt viền xanh; vẫn giữ phân biệt chính xác/gần đúng (bằng độ đậm, có chú giải).
- `/login`, `/register` dùng khung chung `app/AuthShell.tsx` (header site, khối giới thiệu xanh như hero trang chủ, ô nhập/nút/
  tab theo token `primary/ink/line`) thay bảng màu slate/emerald cũ. Trang chi tiết tin vẫn còn kiểu cũ (phần UI chi tiết do
  thành viên khác làm, branch `codex/ui-chi-tiet-nha-tro`).

### Cẩm nang Ký túc xá CTU (cùng ngày — chủ nhiệm đề xuất phần gắn với ĐH Cần Thơ)
- `/cam-nang#ktx` (mục 1): 6 thẻ — các khu KTX, chi phí, phòng nấu/không nấu ăn, đăng ký, trả chỗ/hoàn phí, nội quy; mọi ý dẫn
  4 nguồn chính thức (ssc.ctu.edu.vn, tansinhvien.ctu.edu.vn: trang CSVC & mức phí, Nội quy KTX 09/2025, TB 307/TB-CTSV
  21/7/2026, hướng dẫn tân SV) — đúng 4 tài liệu chatbot đang dùng (`chatbot_corpus/ctu-*.json`) nên hai nơi không lệch.
- Khối "KTX hay thuê trọ?": phí KTX 220–475 nghìn/SV/tháng cạnh giá giữa phòng trọ trong 2 km quanh khu II tính từ dữ liệu
  hệ thống (12/10: 2,7 triệu, 308 tin; ở ghép 2 người ≈ 1,4 triệu/người), cache 1 giờ; nút sang bản đồ, ghép bạn, trợ lý.
- Trợ lý: `/tro-ly?hoi=…` điền sẵn câu hỏi (không tự gửi); thêm câu gợi ý "Phí ở KTX CTU bao nhiêu, phòng nào được nấu ăn?".
  Thử thật: trả lời đúng mức phí/cách đăng ký, trích 3 nguồn CTU, 6,4 s.
- Lưu ý nội dung: hạn đăng ký trong thẻ là của HK1 2026–2027 — học kỳ sau cập nhật theo thông báo mới (và nạp lại corpus).


---

## Phiên 13/10/2026 — Đánh giá nhánh bản đồ của Huy (`origin/codex/open-mobility-handoff`)

Nhánh 2 commit (9e732ff, 588e154), base `origin/main` 59a0395 — KHÔNG chung gốc với `feature/ghep-ban-chat` nên chỉ port
từng phần, không merge. Nội dung: module `app/mobility` (ORS đi bộ/xe đạp gọi trực tiếp, Overpass/Nominatim live, chính sách
quota demo 30 lượt/provider), bản đồ Leaflet + tile raster sau cờ `MOBILITY_ENABLED`, catalog 789 tin đọc từ DB riêng.

**Quyết định: giữ bản đồ hiện tại** (MapLibre + icon, 1.115 tin đã làm sạch gồm khảo sát, phút tới 3 khu tính sẵn, đường xe
máy có cache + OSRM dự phòng, tiện ích nạp sẵn trong DB). Nhánh của Huy kém hơn ở bối cảnh demo: không có xe máy (phương tiện
chính của SV), phụ thuộc provider live + quota, cần Docker catalog riêng, quay lại Leaflet (ADR-019 đã bỏ).

**Đã port:** `route_time_campus` cho phép `null` từng khu (`list[float | None]`, API tin + chatbot + kiểu TS). Trước đó ORS
Matrix không tới được 1 khu ⇒ ghi `[4.0, None, 3.2]` ⇒ schema `list[float]` làm 500 mọi trang có tin đó (chưa xảy ra trên DB,
0 dòng). Test `test_partial_route_times_do_not_break_listing_endpoints`. pytest **622 passed**.

**Chưa port — đi bộ/xe đạp:** thử OSRM FOSSGIS (routed-foot/bike): từ điểm cách tâm khu II ~400 m chim bay ra 4,05 km / 54
phút đi bộ; tới toạ độ "cổng chính 3/2" (geocode.py) vẫn bị kéo lệch 288 m ⇒ 2,5 km / 34 phút. Toạ độ khu đang là TÂM khuôn
viên (có rào), chưa phải cổng ⇒ thời gian đi bộ sai rõ. Điều kiện để làm: nhóm đo toạ độ các cổng (khu I, cổng A/B/C khu II,
khu III) khi đi khảo sát, rồi route tới cổng gần nhất (ORS foot/cycling → OSRM FOSSGIS, có cache như xe máy).

**Ghi nhận khác:** phút (ORS Matrix) tính chiều tin → trường, đường vẽ chiều trường → tin (UI ghi "từ khu II tới phòng") —
chỉ lệch ở đường một chiều; đổi chiều phải tính lại ~300 tuyến trong `route_cache`, để sau.

---

## Phiên 13/10/2026 (2) — Kiểm định sẵn sàng nghiệm thu

Quy trình 4 vai (Haiku: dựng DB từ volume rỗng + smoke 18 trang × 3 vai + CI + file nhạy cảm — đạt hết; Sonnet: chạy kịch bản
demo bằng HTTP thật; Opus bỏ qua vì phân quyền/bảo mật đã audit 12/10, không có rủi ro cao mới). 138 nghìn token subagent.

### Đã sửa
- **Chặn demo**: chatbot hiểu "Chủ trọ giữ cọc không trả thì sao?" (câu demo số 1) là tìm phòng ⇒ thêm cụm tranh chấp cọc vào
  phân loại pháp lý (`parser.py`) + mở rộng truy vấn theo thuật ngữ Điều 328 (`legal_retrieval.py`). Thử thật: trích BLDS Điều
  328, 7,3 s. Test mới trong `test_chatbot_scope.py`.
- Cẩm nang: khối "KTX hay thuê trọ?" không còn cache kết quả lỗi 1 giờ khi web lên trước API (trang dynamic, chỉ cache 2 con
  số qua `unstable_cache`, lỗi thì không cache).
- Trang chủ: bỏ câu cố định "tự cập nhật mỗi 5 giờ" (lịch crawl dừng từ 10/10 15:00 UTC dù `CRAWLER_ENABLED=true` — chưa điều
  tra, cố ý không crawl trước nghiệm thu) ⇒ hiện ngày crawl thật từ `/crawler/status`.
- Bản đồ: ghi chú số phút là ước tính ORS (profile ô tô, chưa tính kẹt xe) — 1598→khu I 5,1 km/4,1 phút.
- DEMO.md: cặp ghép bạn dùng được (Thu ↔ Trân; Thu–Hân, Thu–Linh, Huy–Đức đã ghép), tin 1215 cho nút gọi, không mở đầu bằng 4712
  (2 ảnh 404), đánh giá demo bằng cách viết thật tại chỗ, checklist kiểm Cẩm nang + khoá Gemini.
- **Báo cáo kiểm thử** `docs/report/BaoCao_KiemThu_13-10-2026.md` (thuyết minh dòng 7): 645 ca (624 đạt, 20 skip có lý do, 1 xfail),
  smoke, trình duyệt, dựng DB sạch, kết quả audit, hiệu năng, hạn chế.

### Chưa xong — cần chủ nhiệm/nhóm
- **Không có dữ liệu buổi thử nghiệm người dùng** trong DB này: `rec_eval_sessions` 0, `roommate_ratings` 5 (thử), 12 tài khoản
  MSSV chưa dùng ⇒ notebook 01 phần online vẫn chạy DỮ LIỆU GIẢ (đã ghi "không đưa vào báo cáo"); chưa có SUS. Nếu buổi 09/10 diễn
  ra ở máy khác: `export_judgments` + chạy lại notebook 01/06.
- Không thấy trên máy: báo cáo tổng kết, báo cáo tóm tắt, bản tin, video ≤ 2 phút, slide (thuyết minh mục 16 + kế hoạch mục 6).
- Đánh giá nhà trọ chưa có dữ liệu thật; toàn bộ thay đổi 12–13/10 chưa commit/push.


---

## Phiên 14/10/2026 — Quyết định không thử nghiệm người dùng (ADR-026)

- Notebook 01/06: bỏ hẳn phần sinh dữ liệu giả (mục 5 nb01, mục 9b nb06) — không có phán đoán thật thì in "không thực hiện";
  9b nb06 chỉ còn kiểm hàm Wilcoxon khớp scipy (chênh 2,2e-16). Xoá hình `figs/01_online_GIA.png` (vẽ từ dữ liệu giả).
- Xuất lại `eval/data/rec_candidates.csv` (1.115 tin; bản 07/10 1.012 tin lưu ở scratchpad phiên) và chạy lại 2 notebook:
  0 ô lỗi. Gợi ý offline: đề xuất thoả ràng buộc 91,9% · ILS@10 0,295 · 9,97 vị trí/10 · độ phủ 59; B-giá 100% · 0,475 · 8,07 · 19;
  cosine gốc 32,6% · 0,346 · 6,0 · 70; cosine thô ≥ 0,9999 ở 100% tin.
- Tài liệu cập nhật: ADR-026, báo cáo chức năng & phương pháp (số mới), kế hoạch nghiệm thu, Recommendation tech spec, báo cáo
  kiểm thử.
