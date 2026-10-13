# Gotchas — Trọ CTU

Bẫy đã dính, tích lũy, KHÔNG xóa. Mỗi khi dính bẫy mới → append.

## Crawler 404 làm crash cả job (500)
- **Triệu chứng**: Một URL nguồn hỏng làm sập toàn bộ job crawl với lỗi 500.
- **Nguyên nhân**: Chỉ 403/429 được xử lý; 404/410/5xx lọt ra ngoài. URL `bds123` thiếu `.html` → 302 → 404.
- **Cách tránh/fix**: `pipeline.py` bắt `HTTPStatusError` (404/410/5xx) → skip nguồn, không crash. Nguồn: `docs/tech_specs/Crawler_Pipeline_Hardening.md:43`; `apps/api/app/crawler/fetcher.py:55`.

## Cleaner chỉ chạy theo lịch → data kẹt ở trạng thái `raw`
- **Triệu chứng**: Data crawl thủ công không bao giờ được clean, kẹt ở `cleaning_status='raw'`, bị loại khỏi search.
- **Nguyên nhân**: `run_cleaner` trước đây chỉ chạy trong scheduler.
- **Cách tránh/fix**: `POST /crawler/run` giờ gọi `run_cleaner` sau khi crawl. Nguồn: `docs/CHECKPOINT.md:36`; `Crawler_Pipeline_Hardening.md:47`.

## `source_id` quá dài làm tràn cột upsert
- **Triệu chứng**: Crawl crash khi `source_id` > 100 ký tự tràn `VARCHAR(100)`.
- **Nguyên nhân**: Vài nguồn sinh ID rất dài.
- **Cách tránh/fix**: Nếu > 100 ký tự → hash MD5 (32 ký tự). Nguồn: `Crawler_Pipeline_Hardening.md:46`.

## MinHash dedup chỉ trong 1 batch (dupe cross-batch lọt)
- **Triệu chứng**: ~37 tin near-duplicate còn tồn tại (348 rows / 311 unique content_hash).
- **Nguyên nhân**: `find_duplicates` chạy MinHashLSH chỉ trong một batch crawl, không so với các row đã có trong DB.
- **Cách tránh/fix**: Ngưỡng `JACCARD_THRESHOLD = 0.5` (bigram shingle) chỉnh cho text tiếng Việt ngắn — comment ghi "Tinh chỉnh trên tập gán nhãn khi có data thật". Kế hoạch: dedup so với DB. Nguồn: `apps/api/app/crawler/dedup.py:9-11,39`; `docs/tech_specs/Crawler_Data_Quality_Assessment.md:69`.

## Diện tích ước tính (imputed) không tin cậy cho ~43% tin
- **Triệu chứng**: Filter/gợi ý AI theo diện tích không đáng tin cho gần nửa data.
- **Nguyên nhân**: 138/324 (42.6%) diện tích là *đoán* từ bậc giá khi thiếu m² (`is_imputed_area=true`) — heuristic thô.
- **Cách tránh/fix**: Ưu tiên diện tích thật từ trang chi tiết; gắn cờ "ước tính" ở UI/AI. Nguồn: `Crawler_Data_Quality_Assessment.md:32-36`.

## Nominatim geocode fail ~7.8% + nhãn confidence lạc quan
- **Triệu chứng**: 27 tin không có toạ độ (không lên bản đồ / không tính được khoảng cách CTU); nhiều điểm gắn nhãn "high" thực ra là fallback cấp quận.
- **Nguyên nhân**: Nominatim trên địa chỉ tiếng Việt nhiễu; fallback `"{quận}, Cần Thơ"` khi địa chỉ fail.
- **Cách tránh/fix**: Rate limit ≤1 req/s + User-Agent định danh (chính sách Nominatim); cân nhắc bảng landmark/phường nội bộ. Nguồn: `apps/api/app/crawler/geocode.py:3,19-21`; `Crawler_Data_Quality_Assessment.md:62-64`.

## Crawler bị chặn (403/429) → phải throttle + xoay User-Agent
- **Triệu chứng**: Nguồn chặn request.
- **Nguyên nhân**: Fetch quá dồn dập.
- **Cách tránh/fix**: 1 req / 5s (`RATE_LIMIT_SECONDS = 5.0`), xoay User-Agent, tenacity retry chỉ với `TransportError` tạm thời. Nguồn: `apps/api/app/crawler/fetcher.py:12,19,22-23,55`.

## JWT secret + DB creds mặc định không an toàn
- **Triệu chứng**: JWT/DB creds đoán được nếu `.env` không set → token có thể bị giả mạo.
- **Nguyên nhân**: Mặc định `jwt_secret="dev-insecure-change-me"`, `database_url` dùng `nckh:nckh`.
- **Cách tránh/fix**: Set secret mạnh trong `.env`; checklist cảnh báo rõ không dùng mặc định `nckh/nckh`. Nguồn: `apps/api/app/config.py:7,14`; `docs/Deployment_Guide.md:84`.

## Access token TTL ngắn — phụ thuộc refresh flow, HTTPBearer trả 403 không phải 401
- **Triệu chứng**: Access token hết hạn sau 15 phút; request 401 trừ khi refresh chạy được. Thiếu header Authorization trả **403** (không phải 401).
- **Nguyên nhân**: `access_token_ttl_min=15`, `refresh_token_ttl_days=30`; `HTTPBearer(auto_error=True)`.
- **Cách tránh/fix**: Frontend phải xử lý refresh (TC-AU-04). Chú ý khi assert status code trong test. Nguồn: `apps/api/app/config.py:16-17`; `apps/api/tests/test_listings_crud.py:72`.

## Thiếu district khi địa chỉ nguồn quá ngắn
- **Triệu chứng**: ~14 tin `nhadatcantho247` thiếu district → không lên bản đồ được.
- **Nguyên nhân**: `infer_district` quét 9 tên quận Cần Thơ; địa chỉ ngắn (vd "hẻm 9 Phạm Ngọc Hưng") không chứa tên nào.
- **Cách tránh/fix**: Cân nhắc suy district từ chuyên mục URL. Nguồn: `docs/CHECKPOINT.md:34`; `Crawler_Pipeline_Hardening.md:56-57`.

## Classifier bỏ tin không keyword vào `khac` → ẩn khỏi search
- **Triệu chứng**: Tin hợp lệ biến mất khỏi search mặc định.
- **Nguyên nhân**: Title không có keyword rõ → phân loại `khac`; search mặc định chỉ trả `phong_tro` sạch.
- **Cách tránh/fix**: Cân nhắc phân loại từ chuyên mục URL. Nguồn: `docs/CHECKPOINT.md:35`.

## `docker compose down -v` xoá sạch pgdata
- **Triệu chứng**: Mất toàn bộ data khi hạ stack.
- **Nguyên nhân**: Cờ `-v` xoá volume `pgdata`.
- **Cách tránh/fix**: Không dùng `-v` trừ khi cố tình reset DB. Nguồn: `docs/Deployment_Guide.md:38` "XÓA volume pgdata — mất hết data".

## Render free-tier ngủ khi idle → scheduler không đáng tin
- **Triệu chứng**: Job crawl theo lịch không chạy đúng hẹn khi service ngủ.
- **Nguyên nhân**: Free-tier sleep khi idle (đánh đổi của nguyên tắc P1 chi phí=0đ).
- **Cách tránh/fix**: Dùng external cron gọi thức dậy. Nguồn: `docs/Deployment_Guide.md:53`.

## CORS chưa cấu hình dù checklist yêu cầu
- **Triệu chứng**: Khoảng trống bảo mật — chưa giới hạn origin frontend.
- **Nguyên nhân**: `apps/api/app/main.py` chưa gắn CORS middleware (grep không thấy), trong khi checklist yêu cầu "CORS chỉ cho domain frontend".
- **Cách tránh/fix**: Thêm CORSMiddleware giới hạn origin trước khi deploy. Nguồn: `docs/Deployment_Guide.md:89`; `apps/api/app/main.py`.

## ORS dùng thứ tự [lon, lat] — ngược với DB [lat, lng]
- **Triệu chứng**: (chưa dính, ghi phòng) route time/geometry ra sai bét, điểm rơi tận đâu, KHÔNG crash → bug âm thầm.
- **Nguyên nhân**: OpenRouteService quy ước mọi coordinate array là `[lon, lat]` (docs "General Info"). DB lưu `ST_Y(geom)=lat, ST_X(geom)=lng` (`repo.py:15`) → bê thẳng vào ORS là đảo.
- **Cách tránh/fix**: Khi gọi Matrix/Directions phải xếp `[lng, lat]`, không phải `[lat, lng]`. Test bằng 1 cặp điểm đã biết khoảng cách thật trước khi backfill hàng loạt. Nguồn: `docs/specs/Map_Routing.md` (ràng buộc ORS).

## Nguồn lệch mục tiêu làm nhiễu tập học AI
- **Triệu chứng**: Tập data lẫn nhà/mặt bằng thương mại, không phải trọ SV.
- **Nguyên nhân**: mogi ~83%, nhadatcantho247 ~84% là nhà/thương mại.
- **Cách tránh/fix**: Lọc theo `listing_type=phong_tro` + `quality_score` trước khi train. Nguồn: `Crawler_Data_Quality_Assessment.md:39-50`.

## pytest ghi thẳng vào DB dev — phải dọn sau mỗi lần chạy

`apps/api/tests/` dùng **DATABASE_URL của chính app đang chạy** (không có DB test
riêng, không rollback cuối test). Mỗi lần `pytest` chạy, `test_chat.py` và
`test_matching.py` đăng ký ~60 user mới với email ngẫu nhiên — và **những user đó
có hồ sơ ở ghép giống hệt nhau**, nên chúng lọt vào `GET /matching/deck` của người
thật và đẩy "% tương thích" lên 100%.

Phát hiện 04/10/2026: DB tích tụ **459 user test** (292 từ các phiên trước), pool
ghép có 109 nam + 268 nữ trong khi dữ liệu thật chỉ có 6 nam + 3 nữ. Màn hình
demo khi đó toàn thẻ "SV · 100% tương thích" — trông như lỗi thuật toán.

Dọn sau mỗi lần chạy test (an toàn: chỉ khớp đúng 3 tiền tố email mà tests sinh ra (`mt_` test_matching, `chat_` test_chat, `t3_` test_chat_t3),
và loại trừ tài khoản demo):

```bash
docker compose exec -T db psql -U nckh -d nckh -c \
  "DELETE FROM users WHERE (email LIKE 'mt\_%@example.com' OR email LIKE 'chat\_%@example.com' \
   OR email LIKE 't3\_%@example.com') AND email NOT LIKE '%.demo@example.com';"
```

Kiểm lại pool thật: `SELECT src, gender, count(*) FROM roommate_profiles WHERE gender IS NOT NULL GROUP BY 1,2;`
— phải chỉ còn `form` (SV thật từ khảo sát) và `seed` (tài khoản demo).

Cách sửa triệt để (chưa làm): cho tests một database riêng qua biến môi trường,
hoặc bọc mỗi test trong transaction rollback. Cả hai đều đụng `conftest.py` và
cách `app.main` tạo engine ở import-time, nên để sau nghiệm thu.

**Cập nhật 06/10/2026 — đã sửa triệt để:** pytest giờ chạy trên DB riêng `nckh_test`.
`tests/conftest.py` đổi `DATABASE_URL` sang `<tên>_test` TRƯỚC khi import `app` (engine
tạo ở import-time nên phải đứng đầu conftest). DB dựng mới tự có `nckh_test`
(`99-test-db.sh` trong initdb); DB đang chạy: `docker compose exec -T db bash
/usr/local/bin/create_test_db.sh` (cần image db đã build lại; `--recreate` để dựng lại sau
khi thêm migration). Thiếu `nckh_test` ⇒ pytest báo `database "nckh_test" does not exist`.
Lệnh dọn ở trên chỉ còn cần cho DB dev bẩn từ trước — lần dọn 06/10 phải thêm tiền tố
`crud_` (test_listings) và xoá 75 tin trọ "Phong tro test …"/"Updated title …" do các
user đó đăng (đang **active**, hiện trên trang tìm kiếm), cùng 219 hội thoại không còn
thành viên (`python -m app.chat.media_gc`).

## Khoá FOR SHARE rồi UPDATE cùng dòng ⇒ deadlock khi hai request song song (06/10/2026)

`ChatRepo.create_message` khoá dòng `conversation_members` để chặn huỷ ghép xen giữa
kiểm quyền và ghi (TOCTOU). Bản đầu dùng `FOR SHARE`, nhưng cuối transaction lại
`UPDATE` chính dòng đó (con trỏ đã đọc) ⇒ hai lần gửi song song cùng giữ SHARE rồi cùng
xin nâng khoá ⇒ `DeadlockDetected` (test_concurrent_same_client_id bắt được). Dùng
`FOR NO KEY UPDATE`: vẫn chặn DELETE (cascade), còn hai lần gửi thì xếp hàng.

## WebSocket từ chối trước `accept()` ⇒ TestClient ném lỗi ở `websocket_connect`, không ở `receive` (06/10/2026)

Kiểm vé trước `accept()` (không cấp socket cho kẻ không có vé). Hệ quả cho test:
`WebSocketDisconnect` nổ ngay khi VÀO `with client.websocket_connect(...)`, nên
`pytest.raises` phải bọc NGOÀI khối `with`, không đặt bên trong. Trình duyệt thật thấy
lỗi kết nối (HTTP 403), không thấy mã 4401 — FE không dựa vào mã đóng nên không sao.

## `app.matching` import vòng với `app.chat` (06/10/2026)

`chat/repo.py` import `matching.repo` ở cấp module; `matching/__init__.py` import
`matching/router.py`. Router matching mà import `chat.repo` ở đầu file ⇒ `ImportError:
cannot import name 'ChatRepo' from partially initialized module` và **api không khởi
động**. Import muộn bên trong hàm (`_publish_swipe`). Notebook eval né cả `__init__`
bằng package rỗng trong `sys.modules` (`eval/roommate_lib.py`).

## `.env.example` đang read-only (06/10/2026)

`-r--r--r--` giống `scheduler.py` trước đây. Không tự đổi quyền; biến mới
(`ROOMMATE_DECK_MODE`, `CHAT_WS_URL`) có giá trị mặc định trong `docker-compose.yml`.
Nếu read-only không cố ý: `chmod u+w .env.example` rồi thêm hai biến đó.

## `maplibre-gl@6` + Next 14: "Worker failed to load" — bản đồ trắng (07/10/2026)

Bản 6 chỉ phát hành ESM, file worker (`maplibre-gl-worker.mjs`) được tìm theo `import.meta.url` lúc chạy;
webpack của Next 14 không copy file đó. Ghim `maplibre-gl@^5` (worker nhúng sẵn trong bundle). Muốn lên 6 phải tự
copy worker vào `public/` + `setWorkerUrl()`.

## Bản đồ MapLibre trống khi tab chạy nền / ảnh chụp tự động (07/10/2026)

Trình duyệt dừng `requestAnimationFrame` ở tab không hiển thị ⇒ tile và lớp GeoJSON về rồi nhưng chưa vẽ; ảnh chụp
bằng extension trông như bản đồ hỏng. Tương tác 1 lần (cuộn/zoom) là vẽ đủ. Không phải lỗi app.

## GeoJSON cluster: `maxzoom` của source phải > `clusterMaxZoom` (07/10/2026)

Mặc định `maxzoom` = 18; đặt `clusterMaxZoom` = 18 (để các tin chung 1 toạ độ luôn là bong bóng có số) mà không
nâng `maxzoom` thì MapLibre cảnh báo và lớp tin có thể không vẽ. `MapCanvas.tsx` đặt `maxzoom = MAX_ZOOM + 2`.

## Browser gọi thẳng FastAPI :8000 bị chặn CORS (07/10/2026)

FastAPI không bật CORS; `apiFetch` luôn gửi `Content-Type: application/json` ⇒ request từ client component bị
preflight chặn (trước đây nút vẽ đường trên bản đồ hỏng âm thầm vì lỗi bị nuốt). Mọi lời gọi từ browser đi qua
Route Handler (`/api/listings/[id]/route`, `/api/pois`, `/api/pois/summary`).

## Chạy lại `run_cleaner` trên tin đã `cleaned` làm hỏng cờ diện tích (07/10/2026)

Tầng `resolve_area` GHI ĐÈ `area` bằng số impute (`is_imputed_area=true`). Set `cleaning_status='raw'` rồi chạy lại ⇒
số impute bị coi là diện tích thật. Đổi classifier thì dùng `python -m app.cleaner.reclassify` (chỉ tính lại loại/
điểm từ cột đã lưu; tin `rejected` thì an toàn để về `raw` vì nhánh reject không ghi area).

## Overpass trả 406 khi thiếu User-Agent, 504 khi quá tải (07/10/2026)

`curl` mặc định bị 406; gọi phải kèm UA định danh. Máy chủ chính và các mirror có lúc cùng 504 hàng chục phút —
`fetch_overpass.py` thử lần lượt các mirror; vẫn hỏng thì dùng snapshot `96_pois_seed.sql` có sẵn (hoặc lọc PBF
Geofabrik ra JSON rồi `--from-file`).

## ORS Directions hết quota trong ngày ⇒ 403 "Quota exceeded" (07/10/2026)

Key ORS hiện tại hết quota Directions sau ~180 lượt ngày 07/10 (Matrix là quota riêng, vẫn chạy). Lỗi là **403**,
không phải 429. Quota hồi lúc 0h UTC. `route_cache_backfill` dừng ngay khi gặp 403; tránh gọi Directions thừa
(mọi đường đi đã tính nằm trong `route_cache`).

## Build lại container `api` giết job đang `exec` trong nó (07/10/2026)

`docker compose up -d --build api` tạo container mới ⇒ job dài chạy bằng `docker compose exec api …` (vd.
`route_cache_backfill --apply`, ~15 phút) chết giữa chừng. Job dài chạy bằng `docker compose run --rm --no-deps -T api …`
(container riêng); script tự bỏ qua phần đã làm.

## Bấm nút trước khi trang Next hydrate thì mất cú bấm (07/10/2026)

Trang client (`/goi-y`, `/goi-y/danh-gia`) render sẵn HTML phía server; nút đã hiện nhưng chưa có handler tới khi JS
hydrate xong ⇒ bấm ngay sau khi tải không có tác dụng, không báo lỗi (dính khi test bằng trình duyệt tự động). Buổi thử
nghiệm trên mạng trường chậm: dặn SV chờ trang tải hẳn. Kiểm bằng log API: không có request = cú bấm rơi trước hydrate.

## nhatot.com chặn bot (403) — kiểm tin còn sống qua gateway JSON (07/10/2026)

GET trang `www.nhatot.com/<id>.htm` / `chotot.com` từ script luôn 403 (chống bot) ⇒ KHÔNG kết luận được tin đã gỡ. Dùng
`https://gateway.chotot.com/v1/public/ad-listing/<list_id>`: 200 = còn, 404 = đã gỡ. Đo 07/10: 14/24 ứng viên Chợ Tốt
crawl 15–18/09 đã 404 sau ~3 tuần — dữ liệu sàn "chết" rất nhanh, phải kiểm trước mỗi buổi demo.

## Tên phường trong tin ≠ tên phường OSM sau sáp nhập 2025 (07/10/2026)

Tin ghi phường cũ (Thới Bình, Xuân Khánh, Hưng Lợi…), OSM đã đổi sang phường mới sau sáp nhập (Phường Ninh Kiều, Tân An,
Cái Khế…). So khớp vị trí bằng tên PHƯỜNG sẽ báo sai hàng loạt — `cleaner/audit.py` chỉ so tên ĐƯỜNG.

## Quota ORS Directions không hồi lúc 0h UTC như tưởng (07/10/2026)

Hết quota ~01h 07/10, tới 12h20 vẫn 403 ⇒ nhiều khả năng cửa sổ 24 giờ trượt tính từ lúc dùng. Matrix là quota riêng nên
phút tới trường không bị ảnh hưởng; chỉ không vẽ được đường cho tin chưa có trong `route_cache`.

## `docker cp apps/api/tests …:/app/tests` lần 2 tạo `tests/tests/` ⇒ pytest báo hàng loạt ERROR (07/10/2026)

Lần đầu (container mới build) thư mục đích chưa có nên chép đúng chỗ; lần sau `/app/tests` đã tồn tại ⇒ docker chép VÀO
trong, sinh `tests/tests/*` trùng tên module ⇒ "19 errors" lúc thu thập test, không phải lỗi code. Chép nội dung thay vì
thư mục: `docker cp apps/api/tests/. "$(docker compose ps -q api)":/app/tests/`.

## Bỏ dấu làm "diện tích" trùng "điện" ⇒ tiền điện sai (07/10/2026)

`_fold` bỏ dấu và đổi đ→d nên "Diện tích: 5x5m" thành "dien tich: 5x5m" — regex tiền điện `dien…<số>` đọc "5" thành 5.000đ
(tin demo 1598 ghi "điện 3.500đ/kw" nhưng lưu 5.000). Đã chặn `dien tich|thoai|may` bằng lookahead và tính lại 68 tin
(đa số là số rác từ "diện tích 3.000m²", "trạm điện 560 KVA" → nay NULL). Regex nào chạy trên text đã bỏ dấu phải
nghĩ tới các từ trùng mặt chữ sau khi bỏ dấu.

## ORS hết quota Directions ⇒ bấm tin trên bản đồ không còn đường đi (07/10/2026)

Triệu chứng: bấm tin chưa có trong `route_cache` thì card hiện số phút nhưng không có đường (API 502 vì ORS trả 403). Số
phút không mất vì Matrix là quota riêng nên dễ tưởng chức năng vẫn chạy. Đã thêm OSRM công khai làm dự phòng (profile
cache `osrm-driving`). Lưu ý: server demo OSRM chỉ cho dùng nhẹ (khoảng 1 req/s, không SLA), chỉ có profile ô tô; đừng
dùng cho tải thật — backfill trước buổi demo để lúc trình bày đọc cache.

## Chatbot: hỏi trước khi có model E5 ⇒ embedder "nhiễm" lỗi tới lúc restart API (08/10/2026)

`E5EmbeddingProvider._load_once` ghi `_load_error` ở lần nạp hỏng đầu tiên và không thử lại. API chỉ đọc model từ cache
local (`local_files_only`), model chỉ được tải bởi `index_corpus`/`index_listings` (vào volume `models`). Nếu có người hỏi
chatbot TRƯỚC khi chạy index lần đầu ⇒ API chạy BM25 (`degraded`) mãi. Chạy index xong mà `/chatbot/ask` vẫn báo
"embedding model unavailable" ⇒ `docker compose restart api`. Xoá volume `models` cũng gây lại đúng lỗi này.

## Chatbot ghép từ branch PHUC: key tiện ích và giới tính khác crawler repo này (08/10/2026)

Catalog của PHUC dùng `private_bathroom`/`refrigerator`/`flexible_hours`/`mezzanine`/`pets_allowed` và
`parsed_amenities->>'gender'`; crawler repo này ghi `private_wc`/`fridge`/`free_hours` (không có gác, thú cưng) và giới tính
ở cột `gender_only` ('nam'/'nu'). Lọc theo key không tồn tại KHÔNG lỗi mà trả 0 tin ("có gác" ⇒ không có phòng nào).
Đã đổi trong `chatbot/parser.py:AMENITIES` + `repo.py`; khi đồng bộ lại code từ branch PHUC phải giữ các chỗ này.

## Tin khảo sát chỉ có tên trọ ("TT HOME", "2T House") bị xếp `khac` ⇒ biến khỏi UI (08/10/2026)

`classify` chỉ đọc tiêu đề; tin khảo sát không đo diện tích nên luật giá/diện tích cũng không bắt. Đã cho
`source='survey'` rơi về `phong_tro` ở cuối `classify` (luật mặt bằng/nhà mini/nguyên căn vẫn ưu tiên). Nạp khảo sát xong
nên xem `listing_type` của các tin mới — tin `khac`/`nha_nguyen_can` không hiện trên tìm kiếm/bản đồ.

## Khoá Gemini sai vẫn "chạy": chatbot lặng lẽ rơi sang Qwen/template (08/10/2026)

`FallbackResponseGenerator` nuốt lỗi của từng nhà cung cấp, nên khoá sai/hết hạn không làm API lỗi — chỉ thấy chatbot chậm
(70–85 s) và hay ra câu trả lời mẫu. Khoá gửi bằng header `x-goog-api-key` tới `generativelanguage.googleapis.com`. **Khoá
Gemini API hiện có cả dạng cũ `AIza…` lẫn dạng mới `AQ.…` (Google đổi từ 2026)** — đừng kết luận khoá sai chỉ vì hình dạng;
(08/10 mình từng nhầm `AQ.` là khoá Vertex, sai). Khoá bị từ chối lần đầu vì chuỗi dán dính ký tự thừa ở hai đầu: lỗi 400
"API key not valid" (khoá nguyên bản) và 401 "cần OAuth" (đã cắt một phần). Sau khi đặt khoá luôn chạy `python -m app.room_service.chatbot.check_llm --call` — nó báo khoá có dùng được không và tên
`GEMINI_MODEL` có tồn tại với khoá đó không (tên mặc định do Phúc chọn, chưa kiểm với khoá của nhóm). Đã gặp: chuỗi dán từ
trình duyệt kèm ký tự thừa ở đầu/cuối ⇒ bị từ chối. Không dán khoá vào chat/docs/commit; chỉ đặt ở `.env` (đã gitignore).

## Có khoá Gemini thật trong container ⇒ pytest chậm 16 phút và có test hỏng giả (08/10/2026)

Các test tích hợp gọi `/chatbot/ask` thật; khi `GEMINI_API_KEY` có giá trị thì chúng gọi Gemini (giãn cách 5 s/lần) và Qwen, bộ test từ ~1 phút thành ~16 phút; `test_numbered_credentials…` còn đọc nhầm khoá thật vào danh sách khoá. Chạy test với khoá tắt:
`docker compose exec -T -e GEMINI_API_KEY= api python -m pytest -q` (596 passed, 68 s). Test mới về khoá phải truyền `gemini_api_key=""` để cô lập khỏi môi trường.

## Đánh giá chatbot bằng một lần chạy là nhiễu (08/10/2026)

Gemini không tất định: cùng mã, cùng câu hỏi, cờ `partial_answer` đổi giữa lần chạy (câu 13: 1/4 lần đủ). So sánh trước/sau trên 36 câu phải chạy nhiều lượt (≥ 3) rồi so TỶ LỆ, không so từng câu; và đừng gộp nhiều câu hỏi vào một hội thoại khi đo (lịch sử bị lẫn, từng làm câu "rẻ hơn" trả lời bằng nội dung câu khẩn cấp trước đó).

## `route_time_campus` không tự tính lại khi toạ độ đổi (12/10/2026)

`auto_route` chỉ route tin có `route_time_campus IS NULL`, còn upsert crawler/backfill ghi toạ độ mới mà giữ phút cũ ⇒ tin
nằm cạnh khu III vẫn mang `{4, 0, 3.4}` của toạ độ khu II, hiện "0 phút" ngay đầu danh sách bản đồ. Đã sửa: upsert và
`backfill.py` đặt `route_time_campus = NULL` khi toạ độ dời > ~5 m. Dữ liệu cũ: so phút với khoảng cách chim bay (phút < km
là bất khả thi) để tìm tin cần route lại. Lưu ý: 4 tin có địa chỉ "Đường 3/2, phường Tân An" đúng là **tâm phường** trùng
khu II (không phải lỗi geocode) — UI ghi "quanh khu II" thay vì "0 phút" (`lib/campus.ts:minutesToCampusText`).

## Lọc quận bằng cột `district` thô trượt vì "Thủy"/"Thuỷ" (12/10/2026)

`district` lưu nguyên văn nguồn ("Quận Bình Thuỷ , Thành phố Cần Thơ", dấu trên u); trang chủ gửi "Bình Thủy" ⇒ `ILIKE`
chỉ khớp 8/39 tin. API tin giờ lọc và trả `COALESCE(NULLIF(district_norm,''), district)`. Thêm nguồn mới thì phải điền
`district_norm` (crawler/address.py), nếu không tin sẽ rơi về chuỗi thô.

## `POST /crawler/run` cần token admin (12/10/2026)

Trước đây không đòi đăng nhập ⇒ máy nào trong LAN demo cũng kích crawl full (site ngoài, Nominatim, quota ORS). Giờ chỉ
admin, `source` theo whitelist `ENABLED_SOURCES`, một nguồn một lượt (trùng ⇒ 409). Script/terminal dùng
`docker compose exec -T api python -m app.crawler.run_once --source <tên> --mode incremental|full`. Lượt `full` lỗi trang
danh sách hoặc thấy < 50% số tin đang hiện thì KHÔNG đánh dấu tin vắng mặt (trước đây 2 lượt lỗi liên tiếp làm expired toàn
bộ tin của nguồn). Crawl gặp lại tin có `audit_reason` không bật lại `active`; `mark_misses` không đụng tin `hidden`.

## Thẻ trong khung `flex-col` + `max-h` cắt mất chữ (12/10/2026)

Item của flex co lại khi container chạm `max-h`; đoạn có `line-clamp` (overflow hidden) bị cắt nửa trên. Thẻ tin trên
bản đồ (màn hẹp) dùng bố cục block + `overflow-y-auto` thay vì `flex flex-col`.


## Toạ độ "khu I/II/III" là tâm khuôn viên, không phải cổng — đừng route đi bộ tới đó (13/10/2026)

`CAMPUSES` (routing.py, lib/campus.ts) là tâm khu có tường rào. Xe máy thì lệch ít (phút ORS vẫn dùng được), nhưng router
đi bộ/xe đạp tìm đường vòng tới điểm gần tâm nhất: phòng cách khu II ~400 m ra "đi bộ 54 phút". Làm chế độ đi bộ phải có toạ độ
cổng đã đo thực địa. Nhánh `codex/open-mobility-handoff` của Huy cũng gắn cờ "ENTRANCE_UNVERIFIED" vì lý do này.
