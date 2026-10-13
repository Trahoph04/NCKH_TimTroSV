# Đặc tả kỹ thuật — Làm mượt Crawler Pipeline

> Ngày: 2026-07-03 · Trạng thái: **Hoàn tất, verified 6/6 nguồn có data sạch trong DB**

## 1. Bối cảnh & vấn đề

Trước khi làm frontend/AI, hệ thống cần **dữ liệu sạch thật sự** trong database.
Kiểm tra thực tế cho thấy pipeline "trông như chạy" nhưng nhiều lỗ:

- **3/6 nguồn không có một dòng dữ liệu nào:** `bds123`, `mogi`, `nhadatcantho`.
- Một nguồn (`bds123`) làm **crash toàn bộ job** (lỗi 500) khi URL sai.
- Bước làm sạch dữ liệu (cleaner) **chỉ chạy theo lịch**, không chạy khi kích hoạt tay
  → dữ liệu test kẹt mãi ở trạng thái `raw`.
- Nhiều tin thiếu **quận/huyện** và **toạ độ** → không lên được bản đồ / tìm quanh.

## 2. Luồng pipeline (sau khi sửa)

```
[Lịch/Kích hoạt tay]
   │
   ▼
run_source(nguồn, mode):
   1. Lấy các trang danh sách (fetcher: 1 request/5s, xoay User-Agent)
   2. Phân tích HTML → chuẩn hoá (giá, diện tích, quận, tiện ích) → khử trùng lặp
   3. Lấy trang chi tiết (bổ sung địa chỉ, ảnh, mô tả)
   4. Geocode: địa chỉ → toạ độ; nếu thất bại → fallback theo quận
   5. Upsert vào DB (INSERT hoặc UPDATE nếu nội dung đổi)
   6. (full sweep) đánh dấu tin biến mất là 'expired'
   │
   ▼
run_cleaner(engine):  ← giờ chạy cả khi kích hoạt tay
   - Lọc tin rác (giá bất thường < 400k hoặc > 20tr) → 'rejected'
   - Nội suy diện tích thiếu (regex mô tả → nếu không có, đoán theo giá)
   - Chuẩn hoá tiêu đề quá ngắn
   - Đánh dấu 'cleaned'
```

## 3. Danh sách các lỗi đã sửa (7 lỗi)

| # | Lỗi | Sửa |
|---|-----|-----|
| 1 | `bds123` URL thiếu đuôi `.html` → 302 → 404 | Thêm `.html` vào `list_url` |
| 2 | 404 làm **crash cả job** (500) — chỉ 403/429 được xử lý | `pipeline.py` bắt thêm `HTTPStatusError` (404/410/5xx) → bỏ nguồn, không crash |
| 3 | `nhadatcantho` URL sai (`/pN.html`) → 404, 0 dòng | Sửa về URL gốc + `?page={page}` |
| 4 | Tin cập nhật giữ mãi dữ liệu đã-làm-sạch cũ (cleaner bỏ qua) | Upsert reset `cleaning_status='raw'` khi nội dung đổi → được làm sạch lại |
| 5 | `source_id` quá dài làm tràn cột `VARCHAR(100)` → crash | Nếu > 100 ký tự → băm MD5 (32 ký tự) |
| 6a | Cleaner **không chạy** khi kích hoạt tay → data kẹt `raw` | `POST /crawler/run` giờ gọi `run_cleaner` sau khi crawl |
| 6b | Migration `60_data_cleaning.sql` thiếu trong Dockerfile | Thêm dòng `COPY` (init sạch sau tự chạy) |
| 7 | Nhiều tin thiếu quận & toạ độ (không lên bản đồ được) | (a) suy ra quận từ địa chỉ; (b) geocode fallback theo quận khi địa chỉ hỏng; (c) upsert backfill quận độc lập |

## 4. Hai kỹ thuật "cứu dữ liệu" đáng chú ý

### 4.1 Suy ra quận từ địa chỉ (`infer_district`)
Nguồn `nhadatcantho247` không có ô "quận" trong HTML. Thay vì để trống, hệ thống dò
tên 9 quận/huyện Cần Thơ (Ninh Kiều, Bình Thủy, Cái Răng, ...) trong địa chỉ/tiêu đề.
Áp dụng cho **mọi nguồn** thiếu quận. Giới hạn: nếu địa chỉ quá ngắn (vd "hẻm 9 Phạm
Ngọc Hưng") không chứa tên quận thì đành để trống.

### 4.2 Geocode fallback theo quận
`bds123` (địa chỉ hỏng — bắt nhầm banner "Xin chào Khách") và `mogi` (địa chỉ trống)
geocode thất bại → 0 toạ độ → biến mất khỏi bản đồ. Fix: khi geocode địa chỉ thất bại,
thử lại với `"{quận}, Cần Thơ"` → có toạ độ cấp quận để tin vẫn hiển thị được.

## 5. Kết quả kiểm chứng (DB thật, sau khi sửa)

| Nguồn | Số tin | Có giá | Có DT | Có quận | Có toạ độ |
|-------|--------|--------|-------|---------|-----------|
| phongtro123 | 235 | 231 | 233 | 235 | 235 |
| mogi | 30 | 27 | 25 | 27 | 27 |
| nhadatcantho247 | 19 | 19 | 19 | 5 | 12 |
| tromoi | 18 | 18 | 18 | 18 | 18 |
| bds123 | 9 | 8 | 9 | 9 | 9 |
| nhadatcantho | 2 | 2 | 2 | 2 | 2 |

- Trạng thái làm sạch: **324 cleaned / 14 rejected · 0 tin kẹt `raw`**.
- **Cả 6 nguồn giờ đều có dữ liệu** (trước: 3 nguồn = 0 dòng).
- Test: **59 pass** (chạy trong container để có DB thật).

## 6. Việc còn lại (chất lượng data)

- ✅ `bds123` selector `address` đã sửa (`address.line-row-1`) — DB xác nhận địa chỉ thật (Quận Ninh Kiều/Bình Thủy), không còn bắt banner.
- ~14 tin `nhadatcantho247` vẫn thiếu quận (địa chỉ nguồn quá ngắn — không có gì để suy ra).
- (Tùy chọn) Proxy/Anti-bot cho `fetcher.py` nếu nguồn siết chặn hơn.

## 7. Ghi chú vận hành

- Kích hoạt tay 1 nguồn: `python -m app.crawler.run_once --source <tên> --mode incremental` trong container, hoặc
  `POST /crawler/run` với token admin (từ 12/10; tự làm sạch luôn). Lượt `full` chỉ đánh dấu tin vắng mặt khi không lỗi và
  thấy ≥ 50% số tin đang hiện của nguồn (`pipeline.MIN_SWEEP_RATIO`).
- Lịch tự động: incremental mỗi 5h, full sweep 3h sáng (Asia/Ho_Chi_Minh).
- Nguồn đang bật: phongtro123, tromoi, mogi, bds123, nhadatcantho, nhadatcantho247.
