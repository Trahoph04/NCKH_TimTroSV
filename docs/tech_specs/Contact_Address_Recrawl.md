# Bổ sung liên hệ + địa chỉ rõ ràng + review Google (2026-09-15)

Trả lời 3 yêu cầu: **số điện thoại/liên hệ**, **review người dùng trên Google Maps**, **địa chỉ rõ ràng**.
Chạy lại toàn bộ bằng `bash recrawl_all.sh`.

## 1. Liên hệ — `app/crawler/contact.py` + migration 91

Cột mới trên `aggregated_listings`: `contact_phone`, `contact_phone_alt`, `contact_zalo`,
`contact_name`, `contact_facebook`, `contact_source`, `contact_extracted_at`.

| Mô tả gốc | Kết quả |
|---|---|
| "LH: Chị Hạnh 0909.123.456 (Zalo 0987654321)" | phone=0909123456, zalo=0987654321, name="Chị Hạnh" |
| "+84 909 123 456" | 0909123456 (chuẩn hoá về 0…) |
| "0292 3831 530" | 02923831530 (cố định Cần Thơ) |
| "Liên hệ: \*\*\*" (Chợ Tốt che số) | NULL — **không đoán, không bỏ qua cơ chế che số** |
| "Giá 1.800.000/tháng" | NULL (số tiền không phải SĐT) |

Chỉ nhận đầu số di động VN có thật + cố định 0292; số nằm cạnh `***`/`xxx`/"bấm để hiện"
bị loại. `contact_source` ghi rõ nguồn: `description` | `detail_page` | `listing_field` | `google_places`.

**Hotline của chính trang rao vặt** sẽ lặp ở mọi tin → sau lần crawl đầu, mở
`exports/phone_duplicates.csv`, số nào xuất hiện hàng chục tin thì thêm vào
`"ignore_phones": ["09xxxxxxxx"]` trong `app/crawler/sources/<nguồn>.json`, rồi backfill lại.

**Pháp lý (nên viết vào báo cáo):** SĐT là dữ liệu cá nhân theo NĐ 13/2023. Hệ thống chỉ
lưu số người đăng **tự công khai** trong tin (và SĐT doanh nghiệp do Google Places trả về),
dùng để khử trùng tin và liên hệ; UI không nên hiện số cho khách chưa đăng nhập — nên để
nút "xem tin gốc". Nguồn nào che số thì tôn trọng, không lấy.

## 2. Địa chỉ rõ ràng — `app/crawler/address.py` + migration 91

Trước đây: `district` là text tự do, **14 biến thể cho 3 quận**, 39% tin không có `address`.

Cột mới: `address_full`, `street`, `ward`, `district_norm`, `address_confidence`, `address_source`.

```
"Quận Ninh Kiều , Thành phố Cần Thơ" ┐
"Ninh Kieu"                          ├─→ district_norm = "Ninh Kiều"
"Q. Ninh Kiều"                       ┘
"85/26 Đường Phạm Ngũ Lão, Phường Thới Bình, Quận Ninh Kiều, Cần Thơ"
   → street="85/26 Đường Phạm Ngũ Lão", ward="Thới Bình", district_norm="Ninh Kiều"
   → address_full="85/26 Đường Phạm Ngũ Lão, P. Thới Bình, Q. Ninh Kiều, Cần Thơ"  (exact)
"phòng trọ hẻm 51 đường 3/2"  → street="Hẻm 51 Đường 3/2"                          (street)
```

`address_confidence`: `exact` (có số nhà) > `street` > `ward` > `district` > `none`.
`repo.set_address()` **không hạ cấp** địa chỉ đang có — địa chỉ mới phải tốt hơn hoặc bằng.

Tin có toạ độ thật nhưng địa chỉ yếu (chủ yếu nhatot) được **reverse geocode** qua Nominatim
(1 req/s) trong `backfill_contact_address.py`; nhatot thì lấy thẳng `street_number/street_name/
ward_name/area_name` của Chợ Tốt nên thường đã `exact` mà không cần gọi mạng.

## 3. Review + SĐT từ Google Maps — `app/reviews_crawl/google_places.py`

- Field mask thêm: `nationalPhoneNumber`, `internationalPhoneNumber`, `websiteUri`,
  `businessStatus`, `regularOpeningHours`, `addressComponents` → bảng `places` có thêm
  `phone`, `phone_intl`, `website`, `business_status`, `opening_hours`, `ward`, `district_norm`.
- Place ghép được với tin đăng (≤60 m) mà tin **chưa có SĐT** → điền `contact_phone` cho tin,
  `contact_source='google_places'`.
- `--grid`: quét thêm vành đai 4 điểm cách mỗi khu CTU ~1,5 km (3 điểm → tối đa 15 điểm).
  Số request: 15 điểm × 5 query × ≤3 trang ≈ ≤225 request/lần, vẫn trong hạn mức miễn phí tháng.
- Lỗi UNIQUE của migration 90 đã sửa: review không có `provider_review_id` từng bị nhân bản
  mỗi lần chạy, nay có unique index theo (place, tác giả, thời điểm).

Hạn chế giữ nguyên như spec trước: review nhà trọ trên Google Maps ở Cần Thơ **thưa**, nguồn
review chính vẫn là UGC của sinh viên; Google Maps là lớp bổ sung có trích nguồn.

## 4. Lỗi cũ đã sửa trong lần này

| File | Lỗi | Hậu quả trước đây |
|---|---|---|
| `crawler/repo.py` | `RETURNING (content_hash = :content_hash AND xmax<>0)` luôn true | `updated_count` đếm cả tin không đổi, `upsert()` không bao giờ trả `'seen'` |
| `crawler/extras.py` | `_NO_DEPOSIT` thiếu word boundary | "nước 20k cọc 1 tháng" → hiểu thành "không cọc" |
| `migrations/90` | `UNIQUE(provider_review_id)` với NULL | review Google thiếu id bị nhân bản mỗi lần chạy |

## 5. Chạy lại

```bash
bash recrawl_all.sh                 # build api → migration → crawl full 7 nguồn → backfill → Google → export CSV
bash recrawl_all.sh --no-google     # chưa có GOOGLE_PLACES_API_KEY
bash recrawl_all.sh --quick         # crawl incremental cho nhanh
docker compose exec api pytest -q   # 31 test (extras 14 + contact 10 + address 7)
```
