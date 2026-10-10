# Bản đồ v2 — as-built (07/10/2026)

Thiết kế: `docs/specs/Map_MapLibre_POI.md` · Quyết định: ADR-019 (MapLibre/ORS), ADR-020 (gói Chợ Tốt, `nha_mini`).
Thay thế phần hiển thị của `Map_Routing.md` (Leaflet); phần route time/ORS Matrix ở đó vẫn đúng.

## 1. Dữ liệu sau phiên

| Chỉ số | Trước | Sau |
|---|---|---|
| Tin hiển thị (`GET /listings` total) | 805 | **1.323** (phòng trọ 1.069 · nhà mini 254) |
| Trong 3 km quanh khu II | 418 | **691** |
| Toạ độ phân biệt của tin hiển thị | 119 | 140 |
| Tin `nhatot` gắn `high` | 610 | 51 (điểm do người đăng ghim); 1.059 tin `medium` |
| Tiện ích OSM (`pois`) | 0 | **1.113** — xe buýt 488 · ATM 189 · y tế 151 · nhà thuốc 146 · siêu thị/tiện lợi 102 · chợ 37 |

**Gói Chợ Tốt 789** (`import_catalog`): 435 đã có (không ghi đè), **354 chèn mới** → cleaner xếp 280 phòng trọ /
72 nhà mini / 2 khác; 352 tin có phút tới 3 khu; 2 tin sang nhượng gắn `offer_kind`. 1.059 tin `nhatot` hạ
`high → medium` (toạ độ dùng chung).

**Phân loại lại** (`reclassify`, 2 lượt): khac→nha_mini 140, phong_tro→nha_mini 42, khac→phong_tro 19,
mat_bang→phong_tro 13 (bug "kho" khớp "không/Khoa"), 10 nhà nguyên căn/chung cư "2 phòng ngủ" rời khỏi phòng trọ.

**Độ khớp classifier với nhãn rà soát của gói** (789 tin): 785/789 = 99,5%; phòng trọ P = 0,995 R = 1,000; nhà mini
P = 1,000 R = 0,982. ⚠ Từ khoá được chỉnh trên chính tập này và nhãn gói là rà soát bằng AI → **độ khớp, không phải
độ chính xác tổng quát**; muốn có số cho báo cáo phải gán nhãn tay một mẫu tin của nguồn khác.

## 2. Backend

| Thành phần | File |
|---|---|
| Migration: enum `nha_mini`, cột `offer_kind`, bảng `pois`, `route_cache` | `infra/db/migrations/95_map_v2.sql` |
| Snapshot tiện ích OSM (1 câu INSERT, idempotent) | `infra/db/migrations/96_pois_seed.sql` |
| Classifier `nha_mini`, `detect_offer_kind`, `reclassify()` | `apps/api/app/cleaner/pipeline.py`, `cleaner/reclassify.py` |
| Nạp gói Chợ Tốt | `apps/api/app/crawler/import_catalog.py` |
| Hạ nhãn toạ độ dùng chung (gọi cuối `run_nhatot` + import) | `crawler/repo.py:mark_shared_coords` |
| Lọc `housing`, `visible_clause()` dùng chung search/nearby, nearby limit 1000 | `apps/api/app/listings/repo.py` |
| Cache đường đi + backfill | `listings/repo.py:RouteCacheRepo`, `listings/route_cache_backfill.py`, `listings/router.py` |
| Module tiện ích (`/pois`, `/pois/summary`, fetch Overpass) | `apps/api/app/pois/` |

Test: `apps/api/tests/test_map_v2.py` (26 ca: classifier, offer_kind, lọc housing, toạ độ dùng chung, reclassify giữ
cờ impute, mapping + nạp idempotent gói, POI endpoint, route từ cache không cần ORS). Toàn bộ: **282 passed, 2 skip**.

**Cache đường đi + OSRM dự phòng (cập nhật 07/10 phiên 8)**: ORS Directions hết quota (`403 Quota exceeded`, cửa sổ
trượt, không hồi lúc 0h UTC) ⇒ `GET /listings/{id}/route` đi theo thứ tự: `route_cache` (cả profile `driving-car` của ORS
lẫn `osrm-driving`) → ORS (nếu có key) → OSRM công khai `router.project-osrm.org` (`routing.py:route_geometry_osrm`) →
lỗi hết mới trả 502. Đường lấy được ghi cache theo profile của engine đã trả. Backfill bằng OSRM:
`docker compose run --rm --no-deps -T api python -m app.listings.route_cache_backfill --engine osrm --apply`
(`--ids` để ưu tiên tin demo). Đo 07/10 sau backfill: 102/102, 102/102, 101/102 toạ độ tin đang hiển thị có sẵn đường tới khu I/II/III (1 lượt OSRM lỗi, lúc bấm sẽ gọi lại).
Số phút trên card vẫn lấy từ ORS Matrix (quota riêng) — đường vẽ bằng OSRM có thể lệch nhẹ so với số phút đó.

## 3. Frontend

- `map/MapCanvas.tsx` — `react-map-gl/maplibre`, style `tiles.openfreemap.org/styles/liberty`. Lớp: vòng bán kính
  (đa giác 64 đỉnh), đường đi (viền trắng + xanh), tiện ích (chấm màu theo nhóm, bấm → popup tên + khoảng cách),
  cluster tin (`clusterMaxZoom = 18`, source `maxzoom = 20`), chấm tin màu theo `risk_level` (unknown = xanh — tự đổi
  màu khi module rủi ro ghi `risk_score`). Campus và tin đang chọn là `Marker` HTML (luôn thấy dù tin trong cluster).
- Bấm cluster: zoom tới mức tách được; nếu không tách được nữa (tin chung toạ độ) → sidebar chỉ còn các tin đó,
  tiêu đề "N tin chung một vị trí" + giải thích vị trí gần đúng.
- `map/MapScreen.tsx` — tab Tất cả / Phòng trọ / Nhà mini (URL `?housing=`), tab 3 khu, slider bán kính, card tin:
  nhãn Nhà mini / Sang nhượng, phút tới khu, "Vị trí tương đối" khi confidence ≠ high, bảng **Tiện ích (quanh khu
  vực) trong 1 km**: 6 nhóm × số lượng × gần nhất, bấm từng dòng để ẩn/hiện lớp trên bản đồ.
- `map/page.tsx` — bỏ mô tả + ảnh thứ 2 trở đi trước khi đưa xuống client (trang 1,9 MB → 1,2 MB).
- Trang chủ: nhóm lọc "Loại chỗ ở", card có nhãn Nhà mini / Sang nhượng (`lib/format.ts:listingTags`).
- Route Handler proxy: `/api/listings/[id]/route`, `/api/pois`, `/api/pois/summary`.
- Dependency: + `maplibre-gl@^5.24`, `react-map-gl@^8.1.3`; − `leaflet`, `react-leaflet`, `react-leaflet-cluster`,
  `@types/leaflet`.

## 4. Kiểm chứng (07/10, trình duyệt thật)

`/map`: nền vector + cluster (277 tin tại điểm mặc định phường Hưng Lợi) → bấm cluster ra danh sách 277 tin →
chọn tin → bay tới, vẽ đường từ khu II, 6 nhóm tiện ích (vd. nhà thuốc 15, gần nhất 130 m), bấm chấm tiện ích →
"PharmaCity · Nhà thuốc · 150 m chim bay"; tab Nhà mini → URL `?housing=nha_mini`, 156 tin; đổi khu III → phút
cập nhật. Trang chủ `?housing=nha_mini` → 254 tin, card có nhãn. `GET /listings/{id}/route` lần 1 1,9 s (ORS), lần 2
3 ms (cache). DB dựng mới từ image (volume trống) nạp đủ migration 95 + 1.113 POI ở cả `nckh` và `nckh_test`.

## 5. Đưa vào báo cáo / slide

- **Vì sao không dùng Google Maps như thuyết minh 13.1**: Việt Nam nằm trong danh sách Prohibited Territories của
  Google Maps Platform; điều khoản cấm phân phối ứng dụng dùng Core Services tại đó và cấm lưu/cào dữ liệu Maps →
  dùng hệ OpenStreetMap: bản đồ nền OpenFreeMap (MapLibre GL), geocode Nominatim, chỉ đường OpenRouteService, tiện
  ích Overpass. Toàn bộ miễn phí, cùng một nguồn dữ liệu nên khớp nhau.
- **Thuật toán đường đi**: ORS (đồ thị OSM, Contraction Hierarchies) cho thời gian theo đường sá thật; precompute phút
  tới 3 khu cho mọi tin (Matrix), polyline lưu sẵn cho ~140 toạ độ.
- **Hạn chế phải ghi**: toạ độ đa số tin chỉ tới cấp phường (nguồn không cho số nhà) → "tiện ích quanh khu vực",
  "vị trí tương đối"; khoảng cách tiện ích là chim bay; OSM ở Cần Thơ có thể thiếu điểm mới; OpenFreeMap không SLA;
  không có profile xe máy; vùng rủi ro (ngập/an ninh) chưa làm vì không có dữ liệu thật.
