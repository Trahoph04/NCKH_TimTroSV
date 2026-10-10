# Bản đồ v2 — MapLibre, tiện ích xung quanh, dữ liệu Chợ Tốt 789

_Lập 07/10/2026 · nối tiếp `Map_Routing.md` (v1, Leaflet + ORS) · nguồn ý tưởng: `de-xuat-chuc-nang-map.md` (06/10)_

## Mục tiêu
Đổi bản đồ sang **MapLibre GL + OpenFreeMap** (vector tile, không key), thêm lớp **tiện ích xung quanh**
(OSM/Overpass lưu PostGIS), lưu sẵn đường đi tới 3 khu CTU để demo không phụ thuộc quota ORS, và nạp gói
dữ liệu Chợ Tốt 789 tin vào DB hiện có — kèm nhãn toạ độ trung thực và loại chỗ ở **nhà mini**.
Phục vụ trực tiếp nội dung đã đăng ký "Phần 4: tích hợp bản đồ số — đánh giá vị trí, khoảng cách, khả năng
di chuyển" (Thuyết minh mục 15.1) và mục tiêu 12.2 "mức độ thuận tiện".

## Yêu cầu

**Dữ liệu**
- [x] D1 Nạp `student-housing-789-Docker-INTERNAL/catalog/CATALOG.jsonl` vào `aggregated_listings` (KHÔNG dựng DB
      riêng cổng 5454): chỉ chèn tin chưa có theo `(source='nhatot', source_id)`; 435 tin trùng KHÔNG ghi đè
      (giữ extras/contact/address đã trích). `last_seen` lấy từ thời điểm quan sát thật của gói, không `now()`.
      Idempotent: chạy lại không đổi gì.
- [x] D2 Toạ độ Chợ Tốt: điểm dùng chung bởi ≥ 2 tin = toạ độ mặc định của phường do sàn gán → `medium`
      ("vị trí tương đối"); điểm riêng 1 tin = người đăng tự ghim → giữ `high`. Áp cả cho crawler nhatot.
- [x] D3 Loại chỗ ở mới `nha_mini` (minihouse / căn hộ mini / studio / căn hộ dịch vụ) trong classifier.
- [x] D4 Sửa classifier: từ khoá mặt bằng khớp theo **từ** (`kho` đang khớp "không", "khoa"); nhận tiêu đề
      "Trọ …" không có chữ "phòng".
- [x] D5 Phân loại lại tin đã `cleaned` **không** chạy lại toàn pipeline (re-run resolve_area sẽ biến diện tích
      đã impute thành diện tích thật) — chỉ tính lại `listing_type`, validate giá, `quality_score`.
- [x] D6 `offer_kind='lease_transfer'` (pass phòng / sang nhượng) → nhãn "Sang nhượng" trên card + bản đồ.

**Tìm kiếm**
- [x] S1 Tin hiển thị = `source='user' OR (cleaned AND listing_type IN ('phong_tro','nha_mini'))`.
- [x] S2 Param `housing=phong_tro|nha_mini` cho `GET /listings` và `GET /listings/nearby`; bỏ trống = cả hai.
- [x] S3 Bộ lọc "Loại chỗ ở" ở trang chủ + bản đồ.

**Bản đồ (FE)**
- [x] M1 `react-map-gl/maplibre` + `maplibre-gl`, style `https://tiles.openfreemap.org/styles/liberty`; gỡ
      `leaflet`, `react-leaflet`, `react-leaflet-cluster`, `@types/leaflet`. Giữ attribution OSM/OpenFreeMap.
- [x] M2 Giữ nguyên hành vi màn `/map` hiện có: sidebar, tab 3 khu, slider bán kính (URL `?radius=`), vòng bán
      kính nét đứt, campus vuông navy, card tin đang chọn, flyTo, vẽ đường đi.
- [x] M3 Cluster bằng GeoJSON source của MapLibre. Bấm cluster → zoom vào; nếu cluster không tách được nữa
      (nhiều tin chung 1 toạ độ) → sidebar lọc còn đúng các tin đó + dòng "N tin chung vị trí (gần đúng)".
- [x] M4 Màu marker theo `risk_level` (unknown = xanh như cũ) — để khi module rủi ro của nhóm được ghép vào,
      bản đồ tự đổi màu, không phải sửa lại.
- [x] M5 Bật/tắt lớp tiện ích theo nhóm; tin đang chọn hiện "Trong 1 km: …" + tiện ích gần nhất mỗi nhóm.

**Tiện ích (POI)**
- [x] P1 Bảng `pois` (migration 95), nạp 1 lần từ Overpass quanh 3 khu CTU, lưu `osm_type/osm_id` + tags.
- [x] P2 6 nhóm cho SV: chợ, siêu thị/cửa hàng tiện lợi, ATM/ngân hàng, nhà thuốc, bệnh viện/phòng khám,
      trạm xe buýt. Map tag OSM → nhóm nằm ở 1 chỗ trong code.
- [x] P3 `GET /pois?lat&lng&radius&category` và `GET /listings/{id}/pois?radius=` (đếm theo nhóm + gần nhất).
      Khoảng cách = **đường chim bay** (ghi rõ trên UI); tin vị trí tương đối → nhãn "quanh khu vực".
- [x] P4 Máy dựng mới vẫn có POI: snapshot nạp vào DB qua seed SQL sinh từ lần fetch thật.

**Đường đi**
- [x] R1 Bảng `route_cache` (điểm gốc làm tròn 5 chữ số, khu, profile) — `GET /listings/{id}/route` đọc cache
      trước, gọi ORS khi thiếu rồi ghi lại.
- [~] R2 (lệnh xong; dữ liệu 61/140 toạ độ — hết quota ORS 07/10, xem tech_specs) Lệnh backfill: mọi toạ độ phân biệt của tin đang hiển thị × 3 khu (~120 × 3 lời gọi, trong quota
      ORS free 2.000/ngày).

## Ràng buộc
- Toạ độ thật của dữ liệu chỉ tới **cấp phường** cho phần lớn tin (805 tin hiển thị nằm trên 119 điểm). Mọi
  con số "gần/xa", "tiện ích quanh" phải hiện kèm nhãn mức chính xác — đúng ADR-011.
- Gói 789: `source_rights=UNVERIFIED`, chỉ dùng nội bộ/demo; không thêm SĐT, không bỏ chuỗi
  "[Liên hệ qua nguồn]" trong mô tả đã che; liên hệ qua `source_url`.
- OpenFreeMap + ORS + ảnh CDN đều cần Internet khi demo (đã cần sẵn) → video dự phòng giữ nguyên.
- Overpass/OSM: ODbL — ghi nguồn "© OpenStreetMap contributors" trên bản đồ và trong báo cáo.
- Next 14.2.35 + React 18: chọn phiên bản `react-map-gl` tương thích, không nâng React/Next.
- Không đụng trang chi tiết tin (`listings/[id]`) ngoài nhãn tối thiểu — nhóm đang thiết kế lại ở branch khác.

## Quyết định
- **MapLibre thay Leaflet** (ADR-019): vector tile render GPU, cluster có sẵn trong source (bỏ 3 gói Leaflet),
  style đẹp hơn tile raster; `tile.openstreetmap.org` cấm dùng nặng cho ứng dụng. Google Maps loại vì Việt Nam
  thuộc danh sách lãnh thổ cấm của Google Maps Platform — giải thích cho việc Thuyết minh 13.1 ghi "Google Maps API".
- **Giữ ORS, không tự host OSRM** (quyết định 07/10): ORS đang chạy, 1.120 tin đã có phút tới trường; số toạ độ
  phân biệt nhỏ → lưu sẵn đường đi là đủ ổn định khi demo.
- **Không tạo bảng `lodgings`** như đề xuất: trùng `aggregated_listings`, phải làm lại toàn pipeline.
- **Mặc định hiện cả phòng trọ + nhà mini** (khác phương án ban đầu "mặc định chỉ phòng trọ"): dry-run phân loại
  lại trên DB 07/10 — 41 tin đang hiển thị là minihouse lọt vào `phong_tro` nhờ luật dự phòng giá/diện tích, 140
  minihouse đang bị ẩn ở `khac`; mặc định chỉ phòng trọ sẽ làm 41 tin đang thấy biến mất khỏi UI.
- Classifier đo bằng nhãn rà soát văn bản của gói 789 (housing_type) làm đối chứng.

## Ngoài phạm vi
- Vùng rủi ro `risk_zones` (ngập/an ninh): không có dữ liệu thật → ghi "Hạn chế & hướng phát triển".
- OSRM tự host, pgRouting, khảo sát thực địa xác minh toạ độ, ô tìm địa chỉ Goong.
- Ghép code nhánh nhóm (chatbot, risk engine, trang chi tiết mới) — thành viên khác phụ trách.
- Chỉ đường tới từng tiện ích (chỉ hiện khoảng cách chim bay).
