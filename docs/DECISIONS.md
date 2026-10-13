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

## ADR-016: Chat có gửi ảnh — đảo cam kết "text-only" của thiết kế 1.7
- **Ngày**: 2026-10-05
- **Bối cảnh**: Matching_Messaging_Design.md 1.7 hứa chat text-only; code đã có gửi ảnh (re-encode, xoá EXIF). Tài liệu và sản phẩm mâu thuẫn — hội đồng hỏi là lộ.
- **Quyết định**: Giữ gửi ảnh, sửa tài liệu (chọn của nhóm, 05/10).
- **Lý do**: SV bàn thuê chung cần gửi ảnh phòng/hợp đồng; cấm ảnh thì họ chuyển sang Zalo sớm — dữ liệu sang bên thứ ba và mất lớp T3. Rủi ro riêng tư lớn nhất của ảnh điện thoại là toạ độ GPS trong EXIF — đã xoá phía server; ảnh chỉ thành viên hội thoại tải được; huỷ ghép xoá file; dọn mồ côi bằng `media_gc`; xoá toàn bộ sau nghiệm thu.
- **Đánh đổi**: Lưu nhiều dữ liệu cá nhân hơn text-only; volume `media` phải nằm trong quy trình xoá sau nghiệm thu (ViecConLai mục 6).

## ADR-017: Deck ưu tiên hồ sơ thật, thẻ mô phỏng ≤ 50%
- **Ngày**: 2026-10-05
- **Bối cảnh**: Deck của SV nữ thật 7/8 thẻ là hồ sơ mô phỏng (12 mô phỏng / 3 thật). Hồ sơ mô phỏng không bao giờ thích lại ⇒ buổi thử nghiệm không sinh dữ liệu match.
- **Quyết định**: (a)+(b): chọn hồ sơ thật trước; thẻ mô phỏng ≤ số thẻ thật, sàn 2 thẻ khi không có hồ sơ thật. KHÔNG làm (c) "đặt sẵn swipe cho hồ sơ mô phỏng".
- **Lý do**: (c) tạo ra lượt quan tâm không ai bày tỏ — dù gắn nhãn vẫn là dữ liệu bịa nằm cạnh dữ liệu thật. (a)+(b) chỉ đổi việc *chọn* thẻ, không đổi điểm; thứ tự hiển thị vẫn theo điểm (ranked) hoặc xáo (random).
- **Đánh đổi**: Deck ngắn hơn (SV nữ: 4 thẻ thay vì 8). Ưu tiên theo "thật/mô phỏng" là một tín hiệu ngoài điểm — notebook phải tách `is_simulated` khi đo.

## ADR-018: Pytest chạy trên database riêng `nckh_test`
- **Ngày**: 2026-10-06
- **Bối cảnh**: Test cần Postgres thật (không mock) và từng ghi thẳng vào DB dev: 603 user rác + 75 tin trọ test đang active trên trang tìm kiếm + deck toàn "SV · 100%".
- **Quyết định**: `conftest.py` đổi `DATABASE_URL` → `<db>_test` trước khi import `app`; `infra/db/create_test_db.sh` dựng `nckh_test` từ đúng các file initdb (cùng nguồn lược đồ với DB dev). Thoát hiểm: `PYTEST_USE_DEV_DB=1`.
- **Lý do**: Rẻ hơn rollback-mỗi-test (engine tạo ở import-time, nhiều test dùng nhiều connection/thread/WebSocket — bọc transaction không phủ được). CI dựng DB mới mỗi lần nên tự có `nckh_test`.
- **Đánh đổi**: `nckh_test` không tự nhận migration mới trên DB đang chạy — phải `create_test_db.sh --recreate` (giống quy tắc apply tay migration cho DB dev).

## ADR-019: Bản đồ MapLibre GL + OpenFreeMap thay Leaflet + tile OSM; giữ ORS, không tự host OSRM
- **Ngày**: 2026-10-07
- **Bối cảnh**: Thuyết minh 13.1 ghi "Google Maps API", nhưng Việt Nam thuộc danh sách lãnh thổ cấm của Google Maps
  Platform (điều khoản cấm phân phối ứng dụng dùng Core Services tại đó, cấm lưu/cào dữ liệu Maps). Bản v1 dùng
  Leaflet + `tile.openstreetmap.org` (chính sách tile OSM không cho ứng dụng dùng nặng) + `react-leaflet-cluster`.
  Đề xuất `de-xuat-chuc-nang-map.md` (06/10) gợi ý MapLibre + OpenFreeMap theo mô hình nhaminhbach.com.
- **Quyết định**: `react-map-gl@8` (`react-map-gl/maplibre`) + `maplibre-gl@5` + style OpenFreeMap `liberty` (vector
  tile, không key). Cluster bằng GeoJSON source của MapLibre (gỡ 4 gói Leaflet). Routing GIỮ ORS + bảng
  `route_cache` (spec `docs/specs/Map_MapLibre_POI.md`). Tiện ích lấy 1 lần từ OSM/Overpass vào bảng `pois`.
- **Lý do**: Vector tile render GPU, cluster có sẵn, style đẹp hơn raster; cùng hệ dữ liệu OSM với geocode (Nominatim)
  và routing (ORS) → khớp nhau. OSRM tự host bị bác: tốn ~½ ngày + ~300 MB dữ liệu mỗi máy thành viên, trong khi
  dữ liệu chỉ có ~140 toạ độ phân biệt ⇒ lưu sẵn mọi đường đi ORS là đủ ổn định khi demo; bản đồ nền đã cần
  Internet nên ORS không thêm rủi ro mới.
- **Đánh đổi**: `maplibre-gl@6` chỉ có bản ESM, worker tìm theo `import.meta.url` → webpack của Next 14 không copy
  ⇒ ghim 5.x. OpenFreeMap là dịch vụ cộng đồng không SLA (deploy thật: tự host PMTiles). Không có profile xe máy
  (ORS `driving-car` xấp xỉ). Khoảng cách tới tiện ích là đường chim bay.

## ADR-020: Nạp gói Chợ Tốt 789 vào DB hiện có; toạ độ dùng chung = cấp phường; thêm loại `nha_mini`
- **Ngày**: 2026-10-07
- **Bối cảnh**: Gói `student-housing-789-Docker-INTERNAL` (02/10) kèm DB Docker riêng (cổng 5454, lược đồ 33 cột,
  id 803–1597). Đối chiếu: 435/789 tin đã có trong DB (nguồn `nhatot`, cùng toạ độ, 432 cùng giá) → mới 354 tin.
  787 tin chỉ nằm trên 54 toạ độ; DB đang gắn `high` cho 610 tin nhatot trên 61 toạ độ (1 điểm Hưng Lợi gom 183 tin).
  168 tin "minihouse" (3–4,5 tr, đủ nội thất) bị classifier dồn vào `khac` (ẩn) hoặc lọt `phong_tro`.
- **Quyết định**: (1) Không chạy DB của gói; đọc `CATALOG.jsonl` qua `app.crawler.import_catalog`, chỉ chèn tin chưa
  có, `last_seen` = thời điểm quan sát thật trong gói, bỏ tin không có bằng chứng còn tồn tại. (2) Toạ độ ≥ 2 tin
  cùng nguồn dùng chung → `medium` (`mark_shared_coords`, chạy sau mỗi lần crawl nhatot). (3) Enum `nha_mini`;
  search mặc định trả cả `phong_tro` + `nha_mini`, param `housing` để lọc. (4) Sửa classifier: từ khoá mặt bằng
  khớp theo từ, nhận "Trọ …", bỏ "phòng ngủ/khách/tắm" trước khi xét "phòng"; phân loại lại bằng `reclassify`
  (không chạy lại `resolve_area`).
- **Lý do**: DB của gói thiếu toàn bộ cột/bảng các module khác dùng; nạp vào DB chung giữ một nguồn sự thật. Nhãn
  `high` cho điểm mặc định của phường là sai sự thật (ADR-011: phải hiện "vị trí tương đối"). Mặc định chỉ phòng trọ
  sẽ làm 41 tin đang hiển thị biến mất khi chúng được phân loại đúng là nhà mini.
- **Đánh đổi**: Tin hiển thị 805 → 1.323 nhưng vẫn chỉ ~140 toạ độ phân biệt — "tiện ích quanh tin" thực chất là
  quanh khu vực (UI ghi rõ). Đo classifier với nhãn rà soát của gói: khớp 785/789 (99,5%) — trên CHÍNH tập dùng để
  chỉnh từ khoá và nhãn gói do AI rà văn bản, nên là độ khớp, không phải độ chính xác tổng quát. Gói
  `source_rights=UNVERIFIED`: chỉ dùng nội bộ/demo, thư mục gói nằm trong `.gitignore`.

## ADR-021: Gợi ý nhà trọ = knowledge-based (lọc + MAUT + MMR), KHÔNG cosine; đánh giá bằng phán đoán mù có pooling
- **Ngày**: 2026-10-07
- **Bối cảnh**: `planning/03_ThietKe` Module 2 ghi "Content-Based Cosine" giữa vector SV và vector phòng; SRS FR-4 thêm
  onboarding quiz → preference_vector, popularity fallback, ε-greedy. Không có lịch sử tương tác (`user_interactions` =
  5 dòng), Form 2 (ground-truth) chưa làm, buổi thử nghiệm 09/10.
- **Quyết định**: knowledge-based recommender (Burke 2002; Felfernig & Burke 2008): (1) lọc cứng ngân sách ×1,2, thời
  gian ≤ max(1,5T, T+5), loại chỗ ở, giới tính; tự nới khi < 10 tin và báo rõ (McSherry 2004); (2) MAUT U = Σ wₖuₖ, hàm
  uₖ đơn điệu bất đối xứng, **trọng số = tần suất top-3 của 31 SV khảo sát**, co rút ½ về 3 yếu tố người dùng tự chọn,
  tiện ích "tin không nhắc" = chưa rõ (θ = 0,5); (3) MMR λ = 0,7 chọn tập 10 tin, hiển thị theo U. Bỏ yếu tố "an ninh
  khu vực" (61% SV chọn) vì không có dữ liệu. Đánh giá: offline 3 hệ trên 31 bộ tiêu chí thật + online pooling mù
  (đề xuất / lọc+sắp giá / cosine thiết kế gốc), P@10, NDCG@10, Wilcoxon.
- **Lý do**: Cosine đo hướng, sở thích nhà trọ đơn điệu — trên DB: cosine thô ≥ 0,9999 ở 100% của 1.312 tin (giá lấn át
  phút), bất biến tỉ lệ (4 tr/20′ = 2 tr/10′); cosine chuẩn hoá: top-10 chỉ 35% thoả tiêu chí. Offline hệ đề xuất 92%
  thoả (phần còn lại trong dải vượt 20% có chủ đích), ILS 0,28 (chỉ tiêu ≤ 0,7), 9,9/10 vị trí khác nhau; B-giá đưa 31
  người cùng 20 phòng. ε-greedy cần vòng học từ phản hồi mới có nghĩa; knowledge-based không có cold-start nên không cần
  popularity. Pooling là cách duy nhất còn kịp để có P@10 bằng phán đoán thật.
- **Đánh đổi**: θ, λ, hệ số co rút, ngưỡng là thiết kế — notebook 01 đo độ nhạy: trọng số khảo sát ±20% giữ top-10 ổn
  định (Jaccard 0,90–1,00), còn θ và λ ảnh hưởng nhiều hơn (0,60–0,78) ⇒ báo cáo nêu rõ. N buổi thử nghiệm nhỏ (~15–20) ⇒
  kèm KTC bootstrap + effect size, không chỉ p. Khu học mặc định khu II ở offline (khảo sát không lưu câu A4).

## ADR-022: Chỉ giữ tin SẠCH — vị trí chính xác, còn trên nguồn, đủ thông tin; loại bằng trạng thái + lý do, không xoá
- **Ngày**: 2026-10-07
- **Bối cảnh**: Bản đồ vón cục: 840 tin dồn vào 6 điểm (điểm mặc định của phường do Chợ Tốt gán), chỉ 78 tin có toạ
  độ riêng. Kiểm tiếp phát hiện tin "ma" (Chợ Tốt trả 404 — đã gỡ khỏi sàn sau lần crawl 15–18/09), 3 tin mẫu seed
  (URL giả, ảnh Unsplash) đứng đầu bản đồ, tâm phường Hưng Lợi trùng cổng khu I ("1 phút tới khu I"). Nhóm đang khảo sát
  để có bộ dữ liệu riêng ⇒ chủ nhiệm quyết định loại hẳn mọi tin chưa sạch, kể cả tin thật chỉ có toạ độ cấp phường.
- **Quyết định**: `python -m app.cleaner.audit [--network] [--apply]` — tầng 1 luật offline (tin mẫu, không toạ độ,
  > 8 km từ khu II, vị trí cấp phường/điểm dùng chung bởi ≥ 2 địa chỉ/trùng tâm trường/nguồn HTML thiếu số nhà, giá ngoài
  0,7–8 tr, < 3 ảnh hoặc mô tả < 50 ký tự, sang nhượng, trùng tiêu đề + giá); tầng 2 qua mạng cho tin còn lại (Chợ Tốt:
  gateway JSON 404 = đã gỡ; nguồn khác: HTTP 404/410; Nominatim reverse: toạ độ phải nằm trên con đường trong địa chỉ).
  Đã gỡ → `expired`; còn lại → `hidden`; lý do ở cột `audit_reason` (mig 98).
- **Lý do**: Ẩn bằng trạng thái thay vì DELETE: hệ thống không còn thấy tin (search/map/gợi ý đều lọc theo status) nhưng
  báo cáo đếm được loại bao nhiêu vì lý do gì, khôi phục được, và tin từng được chia sẻ trong chat không làm hỏng FK.
  `hidden` không bị upsert của crawler bật lại; `expired` thì có (đúng nghĩa: tin xuất hiện lại trên sàn).
- **Đánh đổi**: 1.323 → **18 tin** hiển thị (07/10). Gợi ý và buổi chấm mù 09/10 chạy trên tập rất nhỏ — số liệu offline
  của notebook 01 (31 truy vấn × 1.312 tin) là của danh mục TRƯỚC rà soát, phải chạy lại khi có bộ dữ liệu khảo sát.
  Crawl lại (tay hoặc scheduler) sẽ đưa tin cấp phường trở lại ⇒ chạy lại `audit` sau mỗi lần crawl, hoặc tắt crawler.
- **Sửa đổi cùng ngày (07/10, chiều)**: 18 tin quá ít cho gợi ý/buổi thử nghiệm ⇒ chủ nhiệm cho thêm lại dữ liệu crawl và
  "lọc bớt cho phù hợp". `audit --policy system` (mặc định): khôi phục tin thật chỉ có toạ độ cấp phường với cờ
  `location_precise = FALSE` (mig 99) — **bản đồ mặc định chỉ cắm tin chính xác**, có ô "Hiện cả N tin vị trí gần đúng";
  danh sách/gợi ý dùng mọi tin kèm nhãn "vị trí tương đối". Vẫn loại: tin đã gỡ, tin mẫu, ngoài phạm vi, giá bất thường,
  < 3 ảnh/mô tả ngắn, trùng, sang nhượng, không toạ độ. Crawl Chợ Tốt full (857 tin đang đăng, 126 mới); tin nhatot không
  thấy trong lượt crawl = đã gỡ (mẫu 29/30 trả 404). Kết quả: **1.005 tin** (21 vị trí chính xác). `--policy strict` giữ
  hành vi cũ cho bộ demo tối giản.

## ADR-023: Ghép CHỈ chatbot từ branch `PHUC` — route `/chatbot`, 1 migration gộp, corpus 1 schema, đọc thẳng dữ liệu tin của repo
- **Ngày**: 2026-10-08
- **Bối cảnh**: Chatbot (tìm trọ + KTX CTU + pháp lý thuê trọ, RAG có trích dẫn, lịch sử theo tài khoản) nằm ở branch
  `origin/PHUC` (445f89d, 07/10). Branch đó có chung gốc 70f2bed với `feature/ghep-ban-chat` nhưng lệch 45 commit và mang
  theo nhiều module khác (risk, reports/kiểm duyệt, admin, review sentiment, engagement, auth lifecycle…). Đụng độ trực tiếp:
  route `/chat/conversations` (chat ghép bạn của repo này), migration 90–99 trùng số hoàn toàn, `parsed_amenities` khác
  key, giới tính ở cột khác, catalog phục vụ là chuỗi schema `legal_word_repair_v16` → `graph_*` → `legal_ctu_ktx_v2`
  + `housing_graph_*` chỉ tồn tại trong DB máy Phúc.
- **Quyết định**:
  1. Chép nguyên `room_service/chatbot` + `room_service/legal_knowledge`; KHÔNG ghép risk/reports/engagement. Sửa tối thiểu:
     prefix **`/chatbot`** (FE proxy `/api/chatbot/*`), rate limit qua `app/ratelimit.py`, lọc tin bằng `visible_clause()`,
     key tiện ích theo crawler repo này (`private_wc`, `fridge`, `free_hours`; bỏ lọc cứng "gác"/"thú cưng" vì không có cột),
     giới tính đọc `gender_only`, loại mặc định = mọi loại đang hiện (gồm `nha_mini`, PHUC mặc định `phong_tro`).
  2. Phần chatbot của mig 90/93/94/95/97/98/99/100/101 gộp thành **`100_chatbot.sql`** (COPY thành `98c-chatbot.sql` để chạy
     trước `99-test-db.sh`); thêm `risk_evaluated_at` luôn NULL ⇒ chatbot coi risk "chưa đánh giá" (trung tính).
  3. Corpus = gộp nguyên văn manifest v16 (40 nguồn pháp lý/hướng dẫn) + KTX CTU 07/10 (4 nguồn) vào
     `apps/api/chatbot_corpus/`, nạp 1 bước bằng `python -m app.room_service.legal_knowledge.index_corpus` vào schema
     **`legal_ctu_v1`** (44 tài liệu / 530 đoạn / 530 vector — khớp bản phục vụ PHUC ghi trong docs/CHATBOT.md).
  4. Tin trọ: đọc thẳng `public.aggregated_listings` (tin crawl + khảo sát của repo), vector E5 bằng `index_listings`.
  5. Graph RAG và agent Gemini **tắt mặc định**; LLM `auto` = Gemini (nếu có key) → Qwen qua Ollama trên host → template.
- **Lý do**: Ghép cả branch kéo theo ~1.000 file và quyết định nghiệp vụ của module khác (risk tự chấm sau crawl, auth đổi
  TTL refresh 30→7 ngày, SMTP…) mà nhóm chưa duyệt. `/chatbot` tách hẳn 2 tính năng "chat" — không phải đoán route nào của
  ai. Đọc thẳng bảng tin của repo để chatbot thấy đúng dữ liệu UI đang hiện (kể cả 20 tin khảo sát), không phải catalog riêng.
- **Đánh đổi**: Không có Graph RAG ⇒ thiếu 1 nguồn bằng chứng so với bản PHUC đo 36 câu. Không có key Gemini thì câu trả lời
  pháp lý/KTX thường rơi về template/trích nguyên văn vì bộ kiểm chứng claim bác bản nháp của qwen2.5:7b (đo 08/10: câu KTX
  73 s rồi rơi template). Image API nặng thêm ~1 GB (torch CPU) — `INSTALL_ML=false` để build nhẹ (chatbot chỉ BM25).
  Code chatbot còn theo phong cách của Phúc (comment tiếng Anh, dòng dài) — không viết lại để còn đồng bộ được với branch gốc.

## ADR-024: Sinh viên không đăng tin — chỉ admin quản lý nhà trọ; cảnh báo rủi ro = cẩm nang + nhắc theo ngữ cảnh, không mô hình AI
- **Ngày**: 2026-10-08
- **Bối cảnh**: Từ khi có chức năng đăng tin (UGC) chưa có tin nào do người dùng đăng (0 dòng `source='user'`). Tin do người
  lạ tự đăng là chỗ dễ lừa đảo nhất, cần kiểm duyệt + chấm rủi ro. Nhưng dữ liệu không có nhãn lừa đảo nào (`risk_score` = 0
  toàn bộ, tin bẩn đã bị ADR-022 ẩn) ⇒ không huấn luyện/đánh giá được mô hình phát hiện lừa đảo. Văn bản ràng buộc là
  **thuyết minh** THS2026-66 (SRS do nhóm tự viết): 14.2 chỉ ghi "mô phỏng … cảnh báo thông tin rủi ro" (không mô hình, không
  chỉ tiêu); 13.2 loại trừ "đi sâu vấn đề pháp lý của hợp đồng thuê trọ"; sản phẩm dòng 4 có "quản lý người dùng, nhà trọ".
- **Quyết định**:
  1. Bỏ đăng tin cho sinh viên: `POST/PUT/DELETE /listings` + `GET /listings/managed` cần `require_admin`; bỏ
     `GET /listings/mine`, trang "Tin của tôi", nút "Đăng tin miễn phí". Admin **sửa** chỉ tin nhập tay (`source='user'`,
     tin crawl/khảo sát ⇒ 409 vì pipeline ghi đè), **ẩn** được mọi tin (crawler không bật lại tin `hidden`).
     Trang quản trị: `/quan-ly/nha-tro`, `/listings/new`, `/listings/[id]/edit` (không phải admin ⇒ 404).
  2. Cảnh báo rủi ro = trang `/cam-nang` (tìm phòng / ở ghép / pháp lý & hợp đồng; nội dung ở `cam-nang/content.ts`, mọi ý
     pháp lý trỏ điều khoản thật trong `chatbot_corpus`) + khung "Trước khi đặt cọc" ở trang chi tiết tin + Trợ lý AI trả lời
     có trích dẫn. Mục "Cẩm nang" nằm trong thanh menu cùng Tìm trọ, Bản đồ, Gợi ý (thay mục "Trợ lý AI" và nút "Đăng tin miễn phí").
- **Lý do**: Dữ liệu chỉ còn 3 nguồn truy vết được (crawl có link gốc, khảo sát thực địa, admin nhập tay). Cẩm nang đáp
  đúng kết quả kỳ vọng của thuyết minh ("nâng cao nhận thức … tin giả và lừa đảo"), đo được bằng khảo sát người dùng thử.
- **Đánh đổi**: "Tương tác giữa sinh viên và chủ trọ" (thuyết minh phần 5) chỉ còn qua khung liên hệ (gọi/Zalo/tin gốc) —
  chủ trọ không có tài khoản. Chưa có lớp "điểm cần kiểm tra" tự động trên từng tin (giá/m² bất thường, ảnh trùng, 1 SĐT
  nhiều tin) — để sau. Thay đổi phạm vi cần báo GVHD.


## ADR-025: Đánh giá nhà trọ = UGC sao + tag chuẩn trên bảng `reviews` sẵn có; không mô hình cảm xúc, không review Google
- **Ngày**: 2026-10-12
- **Bối cảnh**: Thuyết minh dòng 6 đăng ký "nhắn tin, trao đổi, **đánh giá**"; 14.2 có "cảnh báo thông tin rủi ro". DB có bảng
  `reviews` (mig 90: sao + tag) nhưng 0 dòng; branch `PHUC` có module `listing_reviews` (sao + nhận xét + Naive Bayes cảm xúc
  huấn luyện trên vài chục câu tự viết). Không có nguồn đánh giá sẵn: khảo sát thực địa không chấm điểm, Google Maps Platform
  không dùng được ở Việt Nam (xem Map_MapLibre_POI.md mục 5) và không có khoá.
- **Quyết định**: module `app/reviews` trên bảng `reviews` (mig 102: unique (listing_id, user_id) + updated_at). SV đăng nhập,
  1 đánh giá/tin (sửa/xoá được), sao 1–5 + tối đa 6 tag trong 12 tag chuẩn (5 tốt, 7 cảnh báo) + nhận xét ≤ 1000 ký tự (chặn
  SĐT/link) + "đang ở / đã ở / đã đi xem". Hiện ngay; admin ẩn ở `/quan-ly/danh-gia`. Trang chi tiết hiện điểm TB, phân bố
  sao, đếm tag; tag cảnh báo được ≥ 2 người báo ⇒ khung "Lưu ý từ người đã ở" trỏ sang cẩm nang. Thẻ tin/bản đồ: "★ 4,2 (5)".
- **Lý do**: tag chuẩn đếm được và hiện thành cảnh báo rủi ro có nguồn là người thật (đúng 14.2, không cần mô hình — ADR-024);
  NB của branch PHUC không có dữ liệu thật để đánh giá độ chính xác nên không đưa vào sản phẩm/báo cáo.
- **Đánh đổi**: chưa có dữ liệu ⇒ cần nhóm thu đánh giá THẬT (nhóm khảo sát ghi theo quan sát thực địa, SV đang thuê), không
  tạo đánh giá mẫu. Không kiểm chứng được người viết có thật ở trọ (chỉ tự khai). Nếu sau này ghép module của PHUC thì trùng
  tên package `app/reviews` — phải gộp.


## ADR-026: Không thử nghiệm với người dùng — đánh giá bằng số đo offline trên dữ liệu thật và mô phỏng
- **Ngày**: 2026-10-14 · quyết định của chủ nhiệm.
- **Bối cảnh**: Buổi thử nghiệm dự kiến 09/10 (chấm mù gợi ý, chấm điểm ghép bạn, SUS) chưa diễn ra: DB có 0 phiên
  `rec_eval_sessions`, `roommate_ratings` chỉ có dữ liệu thử, 12 tài khoản MSSV chưa dùng. Nghiệm thu tuần 12–16/10.
  Thuyết minh 12.2 cho phép "đánh giá tính khả thi và hiệu quả … thông qua mô phỏng chức năng và phân tích kết quả";
  14.2 có nhắc "phản hồi từ người dùng thử nghiệm".
- **Quyết định**: Không thử nghiệm người dùng. Chương kết quả dùng: gợi ý — trọng số từ khảo sát 31 SV + so 3 hệ offline
  trên 31 bộ tiêu chí thật × 1.115 tin (notebook 01, chạy lại 14/10: đề xuất thoả ràng buộc 91,9%, ILS@10 0,295, 9,97 vị trí
  khác nhau/10; B-giá 100% / 0,475 / 8,07; cosine thiết kế gốc 32,6% / 0,346 / 6,0) + độ nhạy; ghép bạn — 19 hồ sơ khảo sát
  thật + mô phỏng ghi rõ (notebook 06). Notebook bỏ hẳn phần sinh dữ liệu giả; khung tính online giữ lại (chạy được nếu sau này
  có dữ liệu), hàm Wilcoxon được đối chiếu `scipy`.
- **Hệ quả**: chỉ tiêu P@10 ≥ 0,6 / NDCG@10 ≥ 0,65 / điểm hài lòng ghép bạn / SUS (thuyết minh bổ sung) KHÔNG đo — ghi ở
  hạn chế và hướng phát triển. Trang `/goi-y/danh-gia`, `/roommate/rate` vẫn là công cụ đánh giá có sẵn trong sản phẩm.
