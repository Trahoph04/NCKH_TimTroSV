# Dữ liệu bổ sung: điện/nước/giới tính + review nhà trọ (2026-09-13)

Phục vụ module A (bản đồ + review + cảnh báo rủi ro) và chatbot. Gồm 3 phần độc lập.

## 1. Nguồn mới `nhatot` (JSON gateway) — `app/crawler/nhatot.py`

| | HTML sources cũ | nhatot |
|---|---|---|
| Toạ độ | geocode Nominatim, trần cấp phường (ADR-011) | **lat/lng thật** người đăng ghim → `geocode_confidence='high'` |
| Cọc | không | field `deposit` |
| Request | list + 1 detail/tin | 1 request = 50 tin, không cần detail |
| Ước lượng | — | Cần Thơ ~680 tin phòng trọ; Ninh Kiều là phần lớn |

Endpoint: `GET https://gateway.chotot.com/v1/public/ad-listing?region_v2=5027&area_v2=502701&cg=1050&limit=50&o=<offset>` (5027 = Cần Thơ, 502701 = Ninh Kiều, 1050 = Phòng trọ). SĐT bị che, không lấy.

- `incremental`: Ninh Kiều, 2 trang (100 tin mới nhất). `full`: Ninh Kiều + Bình Thuỷ + Cái Răng, hết trang, đánh dấu expired.
- Đã đăng ký trong `ENABLED_SOURCES` (scheduler) và `/crawler/run?source=nhatot`.
- Không qua `run_source()` (HTML) — có `run_nhatot()` riêng, cùng contract trả về.

## 2. Thuộc tính mềm `extras` — `app/crawler/extras.py` + migration 90

Regex trên `title + description` (bỏ dấu), chạy cho **mọi nguồn** ngay sau upsert, và backfill cho tin cũ:

```
docker compose exec -T db psql -U nckh -d nckh < infra/db/migrations/90_extras_reviews.sql
docker compose exec api python -m app.crawler.backfill_extras          # tin chưa trích
docker compose exec api python -m app.crawler.backfill_extras --all    # trích lại hết (sau khi sửa regex)
```

Cột mới trên `aggregated_listings`:

| Cột | Ví dụ mô tả gốc | Giá trị |
|---|---|---|
| `electricity_price` | "điện 3k5/kw", "3.500đ/kWh" | 3500 (VND/kWh, hợp lệ 1.500–6.000) |
| `water_price`, `water_unit` | "nước 20k/người", "15.000/khối", "100k/tháng" | 20000/person, 15000/m3, 100000/month |
| `utility_state_price` | "điện nước giá nhà nước" | true |
| `deposit_amount` / `deposit_months` | "cọc 2 triệu" / "cọc 1 tháng" / "không cọc" | 2000000 / 1.0 / months=0 |
| `gender_only` | "chỉ nhận nữ", "trọ nữ", "ưu tiên nam" | 'nu' / 'nam'; "nam nữ" → NULL |
| `curfew_hour`, `free_hours` | "khoá cổng 23h" / "giờ giấc tự do" | 23,false / NULL,true |

Nguyên tắc: **không tìm thấy → NULL, không đoán**; UI/chatbot phải hiện "chưa rõ". `set_extras()` dùng COALESCE nên lần trích sau ra NULL không xoá giá trị cũ. Test: `tests/test_extras.py` (14 ca), `tests/test_nhatot.py` (5 ca).

Bẫy đã xử lý: "chị Nữ" (tên người) ≠ "chỉ nữ" — thay đại từ *chị* trước khi bỏ dấu; "điện thoại" không thành giá điện (ràng khoảng 1.500–6.000); "3k5" = 3.500.

## 3. Review từ Google Maps — `app/reviews_crawl/google_places.py` + bảng `places`, `place_reviews`

Dùng **Places API (New) Text Search** (chính thức, có ToS) chứ không cào giao diện Maps. 5 query ("nhà trọ", "phòng trọ", "nhà trọ sinh viên", "khu trọ", "ký túc xá") × 3 khu × ≤3 trang ≈ ≤45 request/lần — nằm trong hạn mức miễn phí hàng tháng của SKU Enterprise+Atmosphere. API trả tối đa **5 review/place**.

```
# .env: GOOGLE_PLACES_API_KEY=...   (Cloud Console → bật "Places API (New)")
docker compose exec api python -m app.reviews_crawl.google_places --dry-run   # xem số liệu + CSV, chưa ghi DB
docker compose exec api python -m app.reviews_crawl.google_places             # ghi DB
docker compose cp api:/app/google_reviews.csv eval/data/google_reviews.csv    # đưa CSV vào eval/data
```

- `places` = nhà trọ vật lý trên Maps (khác `aggregated_listings` = tin đăng). Ghép `listing_id` với tin gần nhất ≤ 60 m (ưu tiên tin toạ độ 'high'). Place không ghép được vẫn hiển thị trên bản đồ như marker riêng.
- `place_reviews.sentiment`: ≤2 sao = `negative` → risk engine đếm nhanh.
- `reviews` (UGC của SV) tạo sẵn trong migration 90, có `tags` chuẩn hoá (`coc_khong_tra`, `gia_khong_dung`, `dien_nuoc_cao`, `an_ninh_kem`, `on_ao`, `ngap_nuoc`, `chu_kho_chiu`, `chu_tot`, `sach_se`, `yen_tinh`) — API/UI làm ở việc tiếp theo.

### Hạn chế phải ghi vào báo cáo
Review nhà trọ trên Google Maps ở Cần Thơ **thưa** (nhiều trọ 0–3 review, đa số là trọ lớn/KTX tư nhân). Phản hồi tiêu cực thật chủ yếu nằm trong group Facebook — không cào được hợp lệ. Vì vậy nguồn review chính của hệ thống là **UGC từ sinh viên** (form khảo sát câu B5 + form review trong web), Google Maps chỉ là lớp bổ sung có trích nguồn. Đây là lập luận trả lời câu "dữ liệu review lấy đâu ra, có tin được không".

## Rủi ro risk engine (việc tiếp theo)
`risk_score = 0.5·review_signal + 0.3·price_anomaly + 0.2·content_rule`, trong đó `review_signal` lấy từ `reviews` (UGC, trọng số cao) + `place_reviews.sentiment='negative'` (trọng số thấp hơn vì không xác thực được người viết là SV).
