# Decisions (ADR) — Trọ CTU

Ghi quyết định kiến trúc quan trọng + LÝ DO. Không xóa cũ, chỉ append. Mỗi mục:

## ADR-001: Kiến trúc 3 tầng tách Frontend — Backend — Database
- **Ngày**: (trống)
- **Bối cảnh**: Hệ thống cần phục vụ nghiệp vụ web, thuật toán AI, và crawler dữ liệu.
- **Quyết định**: Tách Frontend (Next.js) — Backend (FastAPI) — Database (PostgreSQL + PostGIS + pgvector) — Cache (Redis). Nguồn: `docs/SRS.md:39`.
- **Lý do**: lý do chưa ghi nhận trong docs — nêu như lựa chọn đã chốt, không có so sánh phương án.
- **Đánh đổi**: Bản thiết kế sớm (`docs/03_ThietKe_KyThuat_Va_AI.md:11-12`) đề xuất tách backend làm 2 (Node.js+Express cho nghiệp vụ + FastAPI cho AI/crawler). SRS/API_Spec sau này hợp nhất về một backend FastAPI duy nhất — giảm chi phí vận hành nhưng gộp trách nhiệm.

## ADR-002: Backend framework — FastAPI (một backend Python)
- **Ngày**: (trống)
- **Bối cảnh**: Cần backend chung cho nghiệp vụ web + AI + crawler.
- **Quyết định**: FastAPI. Auto-docs `/docs` (OpenAPI) làm nguồn spec chính thức (`docs/API_Specification.md:172`).
- **Lý do**: lý do chưa ghi nhận trong docs (vì sao FastAPI thay vì framework khác không được nêu). Ngầm định: cùng ngôn ngữ Python với AI/crawler → một stack.
- **Đánh đổi**: Roadmap từng nhắc Scrapy cho crawler nhưng impl thật dùng `httpx` + `selectolax` (`docs/tech_specs/Crawler_Pipeline.md:78-79`) — spec/impl drift.

## ADR-003: Frontend — Next.js App Router
- **Ngày**: (trống)
- **Bối cảnh**: Web client cần bản đồ + UI auth + SSR.
- **Quyết định**: Next.js App Router (route handlers `src/app/api/...`), TailwindCSS, Leaflet.js. Nguồn: `docs/03_ThietKe_KyThuat_Va_AI.md:10`; App Router thấy ở `docs/tech_specs/Frontend_Auth.md:58` (`src/app/api/auth/login/route.ts`).
- **Lý do**: lý do chọn Next.js chưa ghi nhận trong docs. Lý do dùng App Router như proxy: xem ADR-005.
- **Đánh đổi**: (trống)

## ADR-004: Database — PostgreSQL 16 + PostGIS 3.4 + pgvector
- **Ngày**: (trống)
- **Bối cảnh**: Cần tính khoảng cách địa lý (gần trường/tiện ích) và semantic/embedding search cho AI, mà không trả phí map API runtime.
- **Quyết định**: PostgreSQL 16 + PostGIS 3.4 + pgvector. Cột `geom GEOMETRY(Point,4326)` GIST index, `embedding_vector VECTOR(384)`. Nguồn: `docs/Data_Dictionary.md:4,32,45`.
- **Lý do**: (ghi rõ trong docs) PostGIS để "phân tích dữ liệu không gian OSM" và tính khoảng cách nội bộ — `docs/Technical_Roadmap.md:90` "Tính khoảng cách bằng PostGIS `ST_Distance` trên dữ liệu nội bộ, không gọi API runtime" (nguyên tắc P1, chi phí = 0đ). pgvector "để lưu trữ vector AI" (`docs/03_ThietKe_KyThuat_Va_AI.md:13`).
- **Đánh đổi**: Tự vận hành geo/vector trong Postgres thay vì dịch vụ chuyên dụng — đổi tiện lợi lấy chi phí = 0đ (P1).

## ADR-005: Auth — JWT + httpOnly cookie qua Next.js Route Handler proxy
- **Ngày**: (trống)
- **Bối cảnh**: Đăng nhập an toàn, bảo vệ token khỏi XSS.
- **Quyết định**: JWT (access ngắn hạn + refresh), lưu trong httpOnly cookie, đi qua Next.js Route Handler proxy thay vì để JS client giữ token. bcrypt salt ≥10 cho mật khẩu (`docs/Technical_Specification.md:34`). Nguồn: `docs/SRS.md:60,143`; `docs/tech_specs/Frontend_Auth.md`.
- **Lý do**: (ghi rõ trong docs) localStorage bị loại vì "JavaScript đọc được token → mã độc XSS đánh cắp được" (`Frontend_Auth.md:14-16`). httpOnly được chọn; proxy giúp "Token không bao giờ chạm tới JavaScript phía client... Không cần cấu hình CORS phức tạp" (`Frontend_Auth.md:40-43`).
- **Đánh đổi**: Next.js chỉ ghi được cookie trong Route Handler/Server Action, không ghi khi render Server Component — "ràng buộc của framework" (`Frontend_Auth.md:70-73`). **Mâu thuẫn TTL refresh**: SRS ghi 7 ngày (`SRS.md:143`), impl config ghi 30 ngày (`apps/api/app/config.py:17`, `Frontend_Auth.md:54`) — cần thống nhất.

## ADR-006: Crawler — pipeline đa nguồn, config-driven, 4 lớp chống chặn
- **Ngày**: (trống)
- **Bối cảnh**: Nguồn HTTP trả 403/429 chặn; nguồn đổi layout âm thầm làm parser chết (`docs/Technical_Roadmap.md:45`).
- **Quyết định**: Pipeline đa pha config-driven, 6 nguồn (phongtro123, mogi, tromoi, bds123, nhadatcantho, nhadatcantho247). Fetcher `httpx.AsyncClient`, parser `selectolax`, lịch APScheduler (incremental mỗi 5h + full sweep 3h sáng). Parser định nghĩa bằng JSON trong `apps/api/app/crawler/sources/`. Nguồn: `docs/tech_specs/Crawler_Pipeline.md:72,78-79`.
- **Lý do**: (ghi rõ trong docs) 4 lớp — "1req/5s, xoay User-Agent"; "Parser plugin JSON... không hard-code CSS"; "Raw backup... re-parse offline"; "Health check... new_count < 10 → alert" (`Technical_Roadmap.md:47-52`). Nguyên tắc P5: "Trang nguồn đổi layout → chỉ sửa JSON, không sửa code" (`Technical_Roadmap.md:17`).
- **Đánh đổi**: Config-driven linh hoạt nhưng cần bảo trì file JSON cho mỗi nguồn.

## ADR-007: Khử trùng lặp — MinHash/LSH (datasketch)
- **Ngày**: (trống)
- **Bối cảnh**: Cùng một phòng đăng trên nhiều nguồn với mô tả khác nhau (`docs/Technical_Roadmap.md:103`).
- **Quyết định**: MinHash + LSH trên nội dung (title+address+description), bigram shingle, Jaccard ≥ ngưỡng → coi là trùng, giữ bản mới nhất. Lib `datasketch` (MinHashLSH), cột `minhash BYTEA`. Nguồn: `apps/api/app/crawler/dedup.py`; `docs/Data_Dictionary.md:39`.
- **Lý do**: (ghi rõ trong docs + code) bắt cross-source near-dup. Comment code: bigram + ngưỡng 0.5 để "bắt near-dup tiếng Việt ngắn... mà vẫn tách tin khác phòng" (`dedup.py:9-11`).
- **Đánh đổi**: **Ngưỡng không nhất quán trên tài liệu**: `03_ThietKe_KyThuat_Va_AI.md:23` ghi ">75%", `Technical_Roadmap.md:105-107` ghi "≥0.8", nhưng code thật `JACCARD_THRESHOLD = 0.5` (`dedup.py:11`). Code là nguồn chuẩn. Dedup chạy trong 1 batch, chưa so với DB cũ (xem GOTCHAS).

## ADR-008: Data cleaning — pipeline 5 tầng, idempotent, không phá dữ liệu gốc
- **Ngày**: (trống)
- **Bối cảnh**: (ghi rõ) "(1) lẫn nhà/mặt bằng không phải trọ, (2) 42.6% diện tích là đoán, (3) không có thước đo sạch" (`docs/tech_specs/Data_Cleaning_Pipeline_Design.md:8-9`).
- **Quyết định**: 5 tầng CLASSIFY → VALIDATE → AREA → NORMALIZE → SCORE; thêm cột `listing_type`, `quality_score`, `is_imputed_area`. Search mặc định chỉ trả `listing_type=phong_tro` sạch. Nguồn: `docs/tech_specs/Data_Cleaning_Pipeline_Design.md`.
- **Lý do**: (ghi rõ) nguyên tắc "Idempotent", "Không phá dữ liệu gốc... gắn cờ, không ghi đè mù", "Minh bạch cho AI" (`Data_Cleaning_Pipeline_Design.md:14-20`). Kết quả đã kiểm chứng: 313 tin → 299 cleaned / 14 rejected, avg quality_score = 0.84 (`:113-116`).
- **Đánh đổi**: (ghi rõ) classifier mogi/nhadatcantho247 yếu, nhóm `khac` lớn — "Chấp nhận được" (`:127-131`).

## ADR-009: Nguyên tắc xuyên suốt (P1–P5)
- **Ngày**: (trống)
- **Bối cảnh**: Ràng buộc chi phí (đề tài SV) + độ tin cậy AI + bền vững parser.
- **Quyết định + Lý do**: (ghi rõ ở `docs/Technical_Roadmap.md:11-17`) P1 chi phí = 0đ (free-tier); P2 không bao giờ auto-delete (chỉ ẩn/gắn cờ); P3 AI fail-safe theo ngưỡng confidence; P4 đo lường định lượng; P5 parser bằng config không phải code.
- **Đánh đổi**: Ưu tiên chi phí = 0đ giới hạn lựa chọn hạ tầng (xem GOTCHAS: Render free-tier ngủ khi idle).

## ADR-010: Route time thật (ORS) precompute-all thay vì đường chim bay
- **Ngày**: 2026-07-06
- **Bối cảnh**: Cần đo "gần trường bao xa" cho SV. Chim bay (`haversine`) SAI hệ thống ở Cần Thơ vì sông + cầu (2 điểm sát nhau nhưng phải vòng qua cầu). Hội đồng NCKH sẽ bẻ "đề xuất theo khoảng cách không phản ánh thực tế đi lại".
- **Quyết định**: Precompute route time THẬT tới 3 campus CTU (khu I/II/III) cho MỌI tin, lưu cột `route_time_campus REAL[]`. Engine = OpenRouteService (ORS), Matrix endpoint (1 call nhiều điểm). Route GEOMETRY (polyline vẽ đường) fetch on-demand khi user click. Chi tiết `docs/specs/Map_Routing.md` + `docs/tech_specs/Map_Routing.md`.
- **Lý do**: Dataset bé (domain trọ-quanh-CTU chặn phồng, trần vài nghìn tin). Rank bằng metric thật = metric hiển thị → không lệch thứ tự. ORS ăn cùng data OSM như geocoder (Nominatim) → khớp. Route time TĨNH → lưu cột DB, KHÔNG cache layer (cột DB là cache vĩnh viễn). Cost tỉ lệ *tin mới* (auto-route sau crawl), không phải *tổng tin*.
- **Đánh đổi**: Phụ thuộc ORS API key (free tier). BÁC các nước sau: (1) proxy chim bay + rerank-sau-route — vẫn lọc top-K bằng chim bay TRƯỚC route → tin tốt bị loại sớm; (2) route cả list view — N call vô nghĩa khi user chưa chọn; chỉ route AI-top-K + click. GOTCHA: ORS dùng `[lng,lat]` ngược DB `[lat,lng]`.

## ADR-011: Geocode trần cấp-phường — KHÔNG mua map, KHÔNG hand-map, budget path Goong
- **Ngày**: 2026-07-06
- **Bối cảnh**: String địa chỉ crawl về kiểu "hẻm 3 Hồ Bún Xáng gần ĐH Cần Thơ" (không phường, không số nhà) → geocode ra khu vực rộng hơn được không? User có kinh phí, hỏi 3 hướng: hand-map OSM / mua Google / gắn landmark tay.
- **Quyết định**: KHÔNG làm cả 3. Giữ geocode 4 tầng Nominatim hiện có (trần cấp-phường/đường). Đảm bảo popup hiện **address text gốc verbatim** + nhãn confidence trung thực ("vị trí tương đối" cho pin low/medium). Chi tiết `docs/specs/Map_Routing.md` (Ràng buộc + Quyết định).
- **Lý do**: (a) Trần chính xác nằm ở **string nguồn**, không ở engine — "hẻm 3 Hồ Bún Xáng" vô-thông-tin, KHÔNG engine nào (kể cả Google) định vị số nhà được. (b) Đếm data 2026-07-06 (446 tin): mọi từ khoá tần suất cao đã cover (Xuân Khánh 63, NVC 37, 3/2 20); Bún Xáng chỉ 4 tin; bug pin-in-school chỉ 1 tin → hand-add landmark = churn ROI thấp. (c) Nominatim test rỗng cho "Hồ Bún Xáng"/"chợ Xuân Khánh" → free map MÙ landmark local CT. (d) Use case SV = lọc khu (cấp phường đủ) → đọc text gốc → gọi chủ trọ → tới xem. KHÔNG đòi cấp số nhà. (e) Hand-map OSM: reindex chậm hàng ngày + kể cả có mốc thì "hẻm 3" vẫn chỉ ra cấp khu vực = bằng ward centroid đã có.
- **Đánh đổi**: Chấp nhận trần cấp-phường + 1 tin pin-in-school. **Budget path khi thật cần** (UGC user đăng địa chỉ đầy đủ, hoặc hội đồng đòi): **Goong (goong.io) TRƯỚC** — data đường/hẻm/số nhà + kho POI local VN tốt hơn OSM, rẻ hơn Google; Google SAU (đắt nhất, đổi ràng buộc P1 cost=0đ). Lý do trả tiền = mua **kho landmark local**, KHÔNG phải mua độ chính xác số nhà (bất khả với string cụt).

## ADR-012: Chat giữa SV đã ghép — WebSocket + Redis pub/sub, polling chỉ là dự phòng
- **Ngày**: 2026-10-01
- **Bối cảnh**: `Matching_Messaging_Design.md` (26/09) chọn polling 3s vì sợ socket rớt khi demo + đụng tầng auth. Mockup 06 và yêu cầu "chat realtime kiểu Tinder" cần đang nhập / online / đã xem tức thì — polling 3s làm các tín hiệu này trông giả.
- **Quyết định**: WebSocket `/chat/ws` (FastAPI) chỉ để ĐẨY sự kiện; mọi thao tác GHI vẫn qua REST (lưu DB trước rồi publish). Fan-out nhiều worker qua Redis `chat:u:<id>`. Auth WS bằng vé JWT `type=ws` 60s xin qua Route Handler (không đụng `HTTPBearer` hiện có). FE tự chuyển polling 3s khi socket không mở. Chi tiết `docs/tech_specs/Chat_Realtime.md`.
- **Lý do**: Giữ được cả hai: realtime thật (đo e2e ≈40ms) và rủi ro demo thấp như polling (rớt socket ⇒ banner + polling, không mất tin vì tin luôn ở DB; Redis chết ⇒ local-only). Lộ danh tính vẫn theo 3 tầng của thiết kế cũ: chỉ cặp đã thích 2 chiều mới có hội thoại.
- **Đánh đổi**: Thêm 1 đường hạ tầng (WS + Redis) và cổng 8000 phải mở cho browser (đã mở sẵn). Không có metric NCKH mới. Lộ liên hệ T3, chat nhóm, push notification để sau.

## ADR-013: Ghép bạn ở — Reciprocal Recommender (Gower + harmonic), KHÔNG collaborative filtering
- **Ngày**: 2026-10-04
- **Bối cảnh**: SRS FR-5.2 ghi "Weighted Cosine Similarity ≥ 0.7"; `03_ThietKe_KyThuat_Va_AI.md` ghi trọng số 25/20/15/15/10 không nguồn. Khảo sát thật thu được 33 phản hồi, trong đó **19 có phần lối sống** và **9 vừa có MSSV vừa có phần D** (nam 6 / nữ 3). Ma trận tương tác rỗng.
- **Quyết định**: Dùng **Reciprocal Recommender System** — lọc cứng 2 tầng → khoảng cách Gower có trọng số theo kiểu dữ liệu → điểm CÓ HƯỚNG → gộp bằng **harmonic mean** [R12] → top-K kèm 3 lý do + 1 lưu ý. Thêm tầng **Stable Roommates** (Irving pha 1 + tìm kiếm vét chính xác ở n ≤ 20) cho đánh giá. Code: `apps/api/app/matching/{profile,filters,score,weights,stable}.py` (thuần, không chạm DB).
- **Lý do**:
  - **Bác CF**: ma trận `swipes` rỗng, item CHÍNH LÀ user (bài toán hai chiều), và N=19 thì không ước lượng được latent factor. Sai họ bài toán, không phải thiếu dữ liệu.
  - **Bác cosine-ngưỡng-0.7** bằng SỐ ĐO trên 19 hồ sơ thật: cosine rơi vào [0.402, 0.991] (sd 0.106) và **ngưỡng 0.7 cho 93% cặp đi qua** ⇒ vô dụng làm bộ lọc. Gower có trọng số cho [0.134, 0.894], dải rộng hơn (0.76 vs 0.59).
  - **Harmonic mean** chống cặp một chiều: đo được harmonic ≤ trung bình cộng ở **171/171 cặp**; cặp lệch nhất bị hạ 0.062.
  - **Trọng số dẫn từ dữ liệu**: tần suất chọn deal-breaker trên 19 hồ sơ (ở bẩn 0.79, ồn khuya 0.63…). Chiều không có câu hỏi đo độ quan trọng được ghi rõ `source='design'` thay vì giả vờ là số đo; bù bằng kiểm tra độ nhạy ±20%.
- **Đánh đổi**: `matching_vector VECTOR(384)` giữ cho tương thích lược đồ nhưng KHÔNG dùng tính điểm (nhúng 12 câu có cấu trúc sẽ phá tính thứ bậc và giết khả năng giải thích). Bỏ Elo/"độ hấp dẫn" kiểu Tinder: sai mục đích (ghép là tương thích cặp) và sai đạo đức.

## ADR-014: Deal-breaker 2 tầng — chỉ an toàn mới là lọc CỨNG
- **Ngày**: 2026-10-04
- **Bối cảnh**: Thiết kế gốc coi mọi deal-breaker được khai là veto tuyệt đối. Đo trên 19 hồ sơ thật: chỉ **2,3% cặp có hướng đi qua**, **13/19 người pool RỖNG**. Nguyên nhân là số học — trung bình mỗi người khai **4,63/9** deal-breaker và tự khai làm **3,26** hành vi.
- **Quyết định**: Tầng **CỨNG** chỉ gồm `Hút thuốc trong phòng` (cột `smoke_in_room`) và `Ở bẩn` (`cleanliness ≤ 2`). Sáu deal-breaker hành vi còn lại thành tầng **MỀM**: không loại, mà vào chiều `deal_breaker_soft` (trọng số cao nhất 0.85) và **hiện rõ chữ** trên thẻ ("bạn ấy có N điều bạn từng nói không chấp nhận: …").
- **Lý do**: Tiêu chí chia tầng là *bản chất*, không phải tinh chỉnh ngưỡng cho đẹp số: khói thuốc là ngoại ứng sức khoẻ và vệ sinh là ngưỡng không thương lượng được trong thời gian thuê; còn "dẫn bạn về / người yêu ngủ lại / ồn khuya / nhậu / thú cưng / đi khuya" là **nội quy nhà mà bạn ở ghép thật vẫn thoả thuận được**. Kết quả đo: người có pool > 0 tăng **6/19 → 16/19**, tỉ lệ cặp đi qua 2,3% → **25,1%**. Quyền quyết định vẫn ở người dùng vì cảnh báo hiện rõ — trung thực hơn là im lặng loại họ khỏi pool.
- **Đánh đổi**: Người khai nhiều deal-breaker sẽ thấy thẻ có cảnh báo thay vì không thấy thẻ nào. Cần nói rõ trong form (đã ghi ở `ProfileForm.tsx`). Bộ tầng cứng nằm ở `filters.HARD_DEAL_BREAKERS`, đổi được bằng một dòng nếu hội đồng muốn so sánh.

## ADR-015: Telemetry deck do SERVER ghi (bảng `deck_log`), không nhận từ client
- **Ngày**: 2026-10-04
- **Bối cảnh**: `POST /matching/swipe` nhận `deck_position`/`deck_mode`/`score` từ body do FE gửi. Đó đúng là dữ liệu dùng để chứng minh đã khử thiên lệch vị trí (Matching_Messaging_Design.md 3.6).
- **Quyết định**: `GET /matching/deck` ghi `deck_log` (vị trí, điểm, s_ab/s_ba, snapshot `{d_k}`, deck_mode, weights_ver); `POST /matching/swipe` ĐỌC lại từ đó và bỏ qua mọi trường client gửi. Migration `93_matching_deck.sql`.
- **Lý do**: Để client tự khai vị trí thẻ thì bằng chứng khử thiên lệch mất giá trị và client sửa được số liệu nghiên cứu. `deck_log` đồng thời là nguồn đo **congestion** (số người đã thấy mỗi hồ sơ) — ở pool nhỏ vài hồ sơ "trung tính mọi chiều" hứng hết lời mời, nên deck hạ ưu tiên theo exposure (tham chiếu Fair Reciprocal Recommendation, RecSys 2024).
- **Đánh đổi**: Mỗi lần phục vụ deck ghi thêm N dòng. Điểm HIỂN THỊ là điểm thật, còn THỨ TỰ áp hình phạt exposure — hai số có thể lệch nhau, phải nói rõ khi trình bày.
