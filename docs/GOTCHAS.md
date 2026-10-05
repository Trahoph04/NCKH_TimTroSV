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
