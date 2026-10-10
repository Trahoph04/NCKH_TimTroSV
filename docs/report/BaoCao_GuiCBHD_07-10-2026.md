# Báo cáo kết quả thực hiện — đề nghị CBHD xác nhận điều kiện nghiệm thu

**Đề tài:** Xây dựng hệ thống có ứng dụng trí tuệ nhân tạo hỗ trợ sinh viên Đại học Cần Thơ tìm nhà trọ
**Mã số:** THS2026-66 · **Chủ nhiệm:** Trần Hoàng Phú · **CBHD:** TS. Nguyễn Công Danh
**Ngày lập:** 07/10/2026 · **Code freeze:** 10/10/2026 · **Nghiệm thu dự kiến:** 12–16/10/2026

> Mọi con số trong báo cáo được lấy trực tiếp từ cơ sở dữ liệu, test và notebook đánh giá ngày 07/10/2026. Những phần
> **chưa có số đo thật** được ghi rõ là chưa có, không ước lượng thay.

---

## 1. Tóm tắt

- **Sản phẩm chạy được**: website tìm trọ có bản đồ số, gợi ý nhà trọ, ghép bạn ở và nhắn tin realtime. Hệ thống chạy
  bằng Docker trên máy local, dữ liệu là **1.012 tin trọ thật đang hiển thị**, gồm 1.005 tin thu thập từ 3 trang đăng tin
  và 7 nhà nhóm tự khảo sát thực địa. **308 kiểm thử tự động** đều đạt.
- **Ba module AI đã có thuật toán và số đo offline**: gợi ý nhà trọ, ghép bạn ở, làm sạch/phân loại dữ liệu. Đánh giá
  với người dùng thật (P@10, mức hài lòng, SUS) dự kiến lấy trong **buổi thử nghiệm 09/10**.
- **Hai module do thành viên khác làm, chưa ghép vào bản chính**: chatbot RAG và cảnh báo rủi ro (kèm trang quản trị).
- **Thiếu sót lớn nhất**:
  - mẫu khảo sát nhỏ (33 phản hồi);
  - phần lớn tin chỉ có toạ độ cấp phường;
  - chưa có đánh giá từ người dùng thật;
  - chưa có chức năng đánh giá phòng (sao, nhận xét);
  - một số chỉ tiêu trong thuyết minh bổ sung chưa đạt.

Nhóm đề nghị CBHD xem mục 2 (đối chiếu thuyết minh) và mục 8 (các điểm xin ý kiến) để xác nhận có đủ điều kiện đưa ra
hội đồng hay không.

---

## 2. Đối chiếu với nội dung đã đăng ký trong thuyết minh

Ký hiệu: ✅ hoàn thành · 🟡 một phần · ❌ chưa có

| # | Nội dung đăng ký (mục 15) | Sản phẩm cam kết | Hiện trạng | Minh chứng |
|---|---|---|---|---|
| 1 | Khảo sát nhu cầu SV | Bộ câu hỏi, dữ liệu, báo cáo phân tích | 🟡 Có bộ câu hỏi 6 phần, **33 phản hồi** (19 có đủ phần lối sống). Dữ liệu đã dùng để sinh trọng số cho gợi ý và ghép bạn. Báo cáo phân tích nằm trong chương 2 báo cáo tổng kết | `docs/planning/Khao_Sat_SV_Form.md`, `eval/data/survey_v2.csv` (không công khai vì có thông tin cá nhân) |
| 2 | Phân tích yêu cầu, thiết kế tổng thể | Mô hình hệ thống, thiết kế bảng dữ liệu | ✅ SRS, đặc tả use case, ERD, từ điển dữ liệu, 22 quyết định kiến trúc (ADR) | `docs/planning/`, `docs/reference/`, `docs/DECISIONS.md`, `Diagrams/` |
| 3 | Mô hình gợi ý bạn ở ghép | Module AI, hệ thống matching, báo cáo đánh giá | ✅ Thuật toán, API, giao diện, chấm điểm làm mù, notebook đánh giá. 🟡 Chưa có điểm hài lòng của người dùng thật (chờ 09/10) | `apps/api/app/matching/`, `eval/notebooks/06_roommate_eval.ipynb` |
| 4 | Website: quản lý người dùng, nhà trọ, tìm kiếm, lọc | Website đủ chức năng | ✅ Đăng ký/đăng nhập (email, MSSV, Google), đăng/sửa/ẩn tin, tìm kiếm, lọc, sắp xếp. 🟡 Trang quản trị viên ở nhánh khác, chưa ghép | `apps/web/`, `apps/api/app/{auth,listings}/` |
| 5 | Bản đồ số + kết nối AI | Hiển thị vị trí, khoảng cách tới CTU, gợi ý nhà trọ thông minh | ✅ Bản đồ, phút đi thật tới 3 khu, tiện ích xung quanh, gợi ý nhà trọ có giải thích. 🟡 Gợi ý chưa có số đo với người dùng thật | `apps/web/src/app/{map,goi-y}/`, `apps/api/app/{recommend,pois}/` |
| 6 | Tương tác, hoàn thiện giao diện | Nhắn tin, trao đổi, đánh giá, kết nối ở ghép | ✅ Chat realtime giữa SV đã ghép (ảnh, đang nhập, đã xem, đồng ý mới lộ liên hệ). ❌ **Chưa có đánh giá phòng** (sao, nhận xét). ❌ Tạo nhóm 3+ người: đã cắt | `apps/api/app/chat/` |
| 7 | Kiểm thử, đánh giá, thử nghiệm | Báo cáo kiểm thử, hệ thống hoàn chỉnh | 🟡 308 kiểm thử tự động. Chưa có báo cáo kiểm thử thủ công. Buổi thử nghiệm người dùng dự kiến 09/10 | `apps/api/tests/`, `docs/reference/Test_Plan.md` |
| — | Chatbot hỏi đáp (nội dung 3) | Hỗ trợ truy vấn bằng chatbot | 🟡 Thành viên khác đang làm trên nhánh riêng, chưa ghép (xem mục 3.10) | nhánh `codex/ui-chi-tiet-nha-tro` |
| — | Cảnh báo rủi ro (mục tiêu 12.2) | Giảm rủi ro lừa đảo | 🟡 Có ở nhánh riêng (luật có giải thích, khiếu nại, kiểm duyệt), chưa ghép, chưa có số đo recall | như trên |

**Sản phẩm theo quy định ĐHCT (mục 16):** website có. Bản tin, báo cáo tóm tắt và video ≤ 2 phút do nhóm chuẩn bị riêng
(không nằm trong mã nguồn); cần kiểm tra lại trước 11/10.

---

## 3. Chức năng, thuật toán và lý do lựa chọn

### 3.1 Thu thập dữ liệu nhà trọ

**Thuật toán/cách làm:**
- Crawler cho 7 nguồn. Mỗi trang HTML có cấu hình selector riêng (plugin JSON). Riêng Chợ Tốt đọc qua JSON gateway
  công khai, vì nguồn này có toạ độ do người đăng ghim và có tiền cọc.
- Hai chế độ crawl: *incremental* (chỉ trang đầu) và *full* (quét hết). Tin không còn thấy 2 lần thì chuyển "hết hạn".
- Độ tươi của tin tính theo `exp(−tuổi/7 ngày)`.

**Vì sao:** không có dữ liệu thì không có hệ thống. Crawl tự động là cách duy nhất có vài trăm tin cập nhật mà không cần
người nhập tay. Cấu hình selector tách khỏi code để trang nguồn đổi giao diện thì chỉ sửa cấu hình. Crawler giãn cách
2 giây/request, khai User-Agent định danh, không đăng nhập, không vượt chặn.

### 3.2 Làm sạch và phân loại tin (5 tầng, theo luật)

**Thuật toán:**
1. Phân loại theo từ khoá: phòng trọ / nhà mini / nhà nguyên căn / mặt bằng / khác.
2. Kiểm giá theo từng loại.
3. Xác định diện tích.
4. Chuẩn hoá tiêu đề.
5. Tính điểm chất lượng 0–1.

Kèm theo:
- Trích tiền điện, tiền nước, tiền cọc, giới tính, giờ giấc bằng regex.
- **Lệnh rà soát** (`app.cleaner.audit`): kiểm tin còn tồn tại trên nguồn, và kiểm toạ độ có nằm đúng con đường ghi
  trong địa chỉ hay không (dùng reverse geocode của Nominatim).

**Vì sao dùng luật, không dùng mô hình học máy:** không có tập dữ liệu đã gán nhãn để huấn luyện. Luật thì minh bạch,
giải thích được từng quyết định, và sửa ngay khi phát hiện sai.

**Số đo:**
- Bộ phân loại khớp **785/789 (99,5%)** với nhãn rà soát văn bản của một bộ dữ liệu Chợ Tốt độc lập. Lưu ý: từ khoá
  được chỉnh trên chính tập này, nên con số là *độ khớp*, chưa phải độ chính xác tổng quát.
- Rà soát ngày 07/10 loại 443/1.672 tin:

  | Lý do loại | Số tin |
  |---|---|
  | Đã bị gỡ khỏi nguồn | 325 |
  | Ngoài phạm vi | 46 |
  | Thiếu ảnh hoặc mô tả | 38 |
  | Không có toạ độ | 11 |
  | Trùng lặp | 11 |
  | Sang nhượng | 6 |
  | Tin mẫu giả | 3 |
  | Giá bất thường | 3 |

  Ngoài ra 217 tin không hiển thị vì là nhà nguyên căn, mặt bằng, hoặc bị bộ làm sạch loại.

### 3.3 Toạ độ (geocoding)

**Thuật toán:**
- Geocode nhiều tầng: địa chỉ có số nhà → phường (Nominatim/OSM) → địa danh → tâm phường.
- Chặn toạ độ rơi ngoài khung Cần Thơ (Nominatim từng trả toạ độ ở Hà Nội, TP.HCM).
- Phát hiện **toạ độ dùng chung**: một điểm mà nhiều địa chỉ khác nhau cùng trỏ vào là điểm mặc định của phường do sàn tự
  gán. Các tin đó được gắn nhãn "vị trí tương đối".

**Vì sao:** chuỗi địa chỉ trên tin đăng thường thiếu số nhà, nên không công cụ nào (kể cả Google) định vị tới từng nhà
được. Hệ thống chọn **trung thực về độ chính xác** thay vì giả vờ chính xác.

### 3.4 Bản đồ số và đường đi

**Công nghệ:**
- MapLibre GL JS với bản đồ nền vector OpenFreeMap (dữ liệu OpenStreetMap).
- Chỉ đường bằng **OpenRouteService** (đồ thị đường OSM, thuật toán Contraction Hierarchies):
  - API Matrix tính sẵn **số phút đi xe tới 3 khu CTU** cho mọi tin (1.012/1.012 tin đã có);
  - đường đi vẽ trên bản đồ được lưu sẵn trong bảng `route_cache`.
- Hai lớp hiển thị: tin có vị trí chính xác (chấm đặc) và tin vị trí cấp phường (cụm xám).
- Bấm cụm thì ra danh sách tin; chọn tin thì vẽ đường đi, hiện tiện ích xung quanh và thông tin liên hệ.

**Vì sao không dùng Google Maps như thuyết minh mục 13.1 ghi:**
- Việt Nam thuộc danh sách *Prohibited Territories* của Google Maps Platform.
- Điều khoản cấm phân phối ứng dụng dùng dịch vụ lõi tại đây, và cấm lưu/cào dữ liệu Maps.

Hệ OSM miễn phí, không cần key cho bản đồ nền, và cùng một nguồn dữ liệu với phần geocode và chỉ đường nên kết quả khớp
nhau. Khoảng cách theo đường sá thật chính xác hơn đường chim bay, vì Cần Thơ có nhiều sông và cầu.

### 3.5 Tiện ích xung quanh

**Cách làm:**
- Lấy **1.113 điểm** từ OpenStreetMap qua Overpass API, lưu trong PostGIS. Gồm chợ, siêu thị, ATM, nhà thuốc, y tế,
  trạm xe buýt.
- Truy vấn không gian `ST_DWithin` cho ra số tiện ích và tiện ích gần nhất trong bán kính 1 km.

**Vì sao:** đúng mục tiêu "đánh giá mức độ thuận tiện" của thuyết minh. Dữ liệu mở, có thể tái lập. Giao diện ghi rõ đây
là khoảng cách chim bay.

### 3.6 Gợi ý nhà trọ — gợi ý dựa trên tri thức (knowledge-based)

**Thuật toán** (lọc → chấm điểm → đa dạng hoá):
1. **Lọc cứng** theo ngân sách, thời gian đi, loại chỗ ở và giới tính. Khi quá ít kết quả thì tự nới ràng buộc và báo
   cho người dùng biết đã nới gì (McSherry 2004).
2. **Chấm điểm đa thuộc tính (MAUT)**: U = Σ wₖ·uₖ.
   - Hàm điểm uₖ đơn điệu và bất đối xứng: rẻ hơn ngân sách thì tốt, vượt ngân sách thì bị trừ.
   - **Trọng số wₖ lấy từ tần suất 31 SV chọn "3 yếu tố quan trọng nhất"** trong khảo sát, rồi co rút về đúng 3 yếu tố
     mà từng người tự chọn.
   - Tiện ích mà tin không nhắc tới được coi là *chưa rõ* (điểm trung tính), không bị coi là *không có*.
3. **Đa dạng hoá bằng MMR** (Carbonell & Goldstein 1998), để 10 tin không dồn vào cùng một chỗ.
4. **Giải thích** lý do cho từng tin, kèm danh sách "nên hỏi chủ trọ".

**Vì sao không dùng lọc cộng tác (CF) hay cosine như thiết kế ban đầu:**
- Không có lịch sử tương tác (bảng tương tác chỉ có 5 dòng), và SV vài năm mới thuê trọ một lần. CF không có dữ liệu để
  học. Họ phương pháp phù hợp là gợi ý dựa trên tri thức (Burke 2002; Felfernig & Burke 2008).
- Cosine đo *hướng*, trong khi sở thích nhà trọ là *đơn điệu*. Đo trên dữ liệu thật:
  - cosine trên vector [giá, phút] cho điểm ≥ 0,9999 ở **100% tin**, tức không phân biệt được tin nào;
  - cosine chuẩn hoá chỉ cho **32%** kết quả top-10 thoả tiêu chí người dùng.

**Số đo offline** (31 bộ tiêu chí thật từ khảo sát × 1.012 tin, ngày 07/10):

| Hệ | Thoả tiêu chí gốc | ILS@10 (càng thấp càng đa dạng; chỉ tiêu ≤ 0,7) | Số vị trí khác nhau / 10 tin | Độ phủ danh mục |
|---|---|---|---|---|
| **Đề xuất (MAUT + MMR)** | 90% (10% còn lại nằm trong dải vượt ngân sách 20% có chủ đích) | **0,29** | **9,9** | 63 tin |
| Lọc + sắp theo giá (cách SV đang làm) | 100% | 0,48 | 8,1 | 19 tin (ai cũng nhận gần như cùng một danh sách) |
| Cosine (thiết kế gốc) | 32% | 0,34 | 6,1 | 65 tin |

**Độ nhạy:** thay đổi trọng số khảo sát ±20% thì top-10 gần như giữ nguyên (Jaccard 0,84–0,98). Tham số "điểm cho tiện
ích chưa rõ" và hệ số MMR ảnh hưởng nhiều hơn (Jaccard 0,60–0,75). Đây là tham số thiết kế và sẽ được ghi rõ trong báo cáo.

**Đánh giá online (09/10):** SV chấm mù các tin gộp từ top-10 của cả 3 hệ, theo kiểu pooling của TREC. Từ đó có
**P@10 và NDCG@10 thật**, kiểm định Wilcoxon theo cặp. Trang chấm và công cụ phân tích đã sẵn sàng.

### 3.7 Ghép bạn ở — gợi ý tương hỗ (reciprocal recommender)

**Thuật toán:**
1. **Lọc cứng 2 tầng.**
   - Tầng an toàn: cùng giới; deal-breaker hút thuốc trong phòng hoặc ở bẩn, phủ quyết hai chiều.
   - Tầng khả thi: ngân sách, thời điểm cần phòng.
2. **Khoảng cách Gower có trọng số**, cho ra điểm có hướng s(A→B) và s(B→A).
3. **Trung bình điều hoà** của hai điểm, để chặn các cặp chỉ hợp một chiều.
4. Bộ thẻ ưu tiên hồ sơ thật, thẻ mô phỏng tối đa 50%; ε-greedy 20%.
5. Phân tích thêm bằng Stable Roommates (Irving).

**Vì sao:**
- Ma trận tương tác rỗng và N nhỏ, nên CF không khả thi.
- Đo trên 93 cặp cùng giới, ngưỡng "cosine ≥ 0,7" của SRS cho **91,4%** cặp đi qua, nên vô dụng làm bộ lọc.
- Gower xử lý được dữ liệu hỗn hợp (thứ bậc và định danh).
- Trung bình điều hoà ≤ trung bình cộng ở **84/93** cặp.
- Trọng số lấy từ tần suất chọn deal-breaker trong khảo sát.

**Số đo** (notebook 06):

| Chỉ số | Kết quả |
|---|---|
| Lọc 1 tầng → 2 tầng | 6/19 → **16/19** người có ứng viên |
| Kendall τ khi trọng số ±20% | 0,974 (tệ nhất 0,600) |
| Gini exposure | 0,430 → 0,367 khi có phạt |
| Stable Roommates | Nhóm nữ có lời giải ổn định; nhóm nam không có (2 cặp chặn) |

Điểm hài lòng 1–5 so với ghép ngẫu nhiên: chờ buổi 09/10.

### 3.8 Nhắn tin realtime

**Công nghệ:** WebSocket kết hợp Redis pub/sub, chạy được nhiều worker; Redis lỗi thì tự chuyển sang polling.
- Ảnh gửi trong chat được mã hoá lại để xoá EXIF và GPS.
- Thông tin liên hệ chỉ lộ khi **cả hai** cùng bấm đồng ý.
- Có báo cáo người dùng và huỷ ghép.

**Vì sao:** cần các tín hiệu tức thời (đang nhập, đã xem, đang online), và bảo vệ thông tin cá nhân của SV.

### 3.9 Liên hệ chủ trọ

- Tin có số điện thoại thì hiển thị số (bấm để gọi), có thêm Zalo/Facebook nếu có. Không có số thì có nút "Xem tin gốc"
  dẫn sang trang nguồn.
- Số điện thoại nằm ở **API riêng**, chỉ trả về khi mở đúng một tin, nên không thể thu thập hàng loạt.
- Hiện 105/1.012 tin có số.

### 3.10 Module ở nhánh khác (chưa ghép vào bản chính)

**Chatbot RAG:**
- Truy hồi lai (SQL + BM25 + pgvector với `multilingual-e5-small`).
- Sinh câu trả lời bằng Qwen2.5-7B chạy local qua Ollama; dự phòng bằng Gemini, cuối cùng là trả lời theo mẫu.
- Có trích dẫn tin nguồn.
- Báo cáo đánh giá của nhánh cho mọi chỉ số = 1,0 và độ trễ p95 khoảng 1 ms. Nhiều khả năng số đo trên dữ liệu giả và
  nhánh trả lời theo mẫu, **cần đo lại** trên dữ liệu thật với LLM trước khi đưa vào báo cáo.

**Cảnh báo rủi ro:** luật có giải thích (yêu cầu cọc trước, giá thấp bất thường so với trung vị cùng quận, thiếu thông
tin), cộng với tín hiệu khiếu nại từ cộng đồng và trang kiểm duyệt cho quản trị viên. Chưa có tập gán nhãn để đo recall.

**Gợi ý bằng embedding:** E5 + rerank BGE, lưu trong MongoDB. Nhóm không chọn làm hệ chính, vì 3 lý do:
- mỗi truy vấn mới mất 23–26 giây trên CPU;
- không xét vị trí địa lý ("gần ĐH Cần Thơ" trả về phòng gần trường khác);
- thêm hạ tầng mới (MongoDB, mô hình ~2 GB).

Ghi vào phần hướng phát triển.

---

## 4. Cơ sở dữ liệu lưu ở đâu

| Thành phần | Công nghệ | Vị trí lưu | Ghi chú |
|---|---|---|---|
| CSDL chính | **PostgreSQL 16 + PostGIS 3.4 + pgvector** | Container Docker `db`, dữ liệu trong **Docker volume `nckh_pgdata`** trên máy chạy hệ thống | Lược đồ là SQL thuần trong `infra/db/migrations/` (20 → 99), tự chạy khi volume trống. Có DB riêng `nckh_test` cho kiểm thử |
| Bảng chính | — | — | `aggregated_listings` (1.672 dòng, 1.012 hiển thị) · `users` (45) · `roommate_profiles` (10 thật, 32 mô phỏng có nhãn) · `swipes`, `match_requests`, `conversations`, `messages`, `chat_media` · `pois` (1.113) · `route_cache` · `deck_log`, `roommate_ratings`, `rec_eval_*` (đánh giá) · `crawl_runs` |
| Hàng đợi / pub-sub | Redis 7 | Container `redis` | Chỉ phát sự kiện chat realtime, không lưu dữ liệu bền vững |
| Ảnh chat | File system | Docker volume `media` | Đã xoá EXIF. Xoá volume thì mất ảnh |
| Ảnh nhà trọ khảo sát | File tĩnh | `apps/web/public/khao-sat/` (trong mã nguồn) | 24 ảnh, đã xoá metadata |
| Ảnh tin crawl | URL | CDN của trang nguồn | Không tải về |
| Dữ liệu khảo sát SV | CSV | `eval/data/` (**không** đưa lên git) | Có họ tên, MSSV, email |
| Dữ liệu khảo sát nhà trọ gốc | Excel | Ngoài repo | Có SĐT chủ trọ |
| Bản đồ nền, chỉ đường, tiện ích | Dịch vụ ngoài | OpenFreeMap, OpenRouteService, Overpass | **Cần Internet khi demo.** Đường đi và tiện ích đã lưu sẵn để giảm phụ thuộc |

**Sao lưu:** nhóm chạy `pg_dump` trước mỗi thao tác dữ liệu lớn. Đề nghị sao lưu toàn bộ volume vào ngày 10/10 để dự
phòng cho buổi demo.

---

## 5. Đánh giá hệ thống

| Hạng mục | Phương pháp | Kết quả đến 07/10 |
|---|---|---|
| Đúng chức năng | 308 kiểm thử tự động trên DB thật (`nckh_test`) + build kiểm tra kiểu cho frontend; CI GitHub Actions | **308 đạt**, 2 bỏ qua (cần CSV có thông tin cá nhân) |
| Chất lượng dữ liệu | Lệnh rà soát: tin còn sống (gateway Chợ Tốt, HTTP), toạ độ đúng đường (Nominatim reverse) | 1.672 dòng: 1.012 hiển thị, 443 loại bởi rà soát, 217 không phải chỗ ở cho thuê hoặc bị loại khi làm sạch. Kiểm 30 tin mẫu thì 29 tin đúng là đã bị gỡ. 28 tin có vị trí chính xác |
| Gợi ý nhà trọ | Offline: 3 hệ × 31 bộ tiêu chí. Online: chấm mù kiểu pooling → P@10, NDCG@10, Wilcoxon | Offline: mục 3.6. **Online: chờ 09/10** |
| Ghép bạn ở | Notebook 06 (cùng code sản phẩm) + chấm mù 1–5 so với ngẫu nhiên | Offline: mục 3.7. **Online: chờ 09/10** |
| Trải nghiệm người dùng | Thang SUS 10 câu sau buổi thử nghiệm | **Chưa có** (cần chuẩn bị phiếu) |
| Hiệu năng | Đo tại máy local | Gợi ý ~0,75 s lần đầu, nhanh hơn khi có cache. Đường đi có cache 3 ms, gọi ORS ~1,9 s |
| Bảo mật | Token httpOnly, giới hạn tần suất, chặn upload lớn, xoá EXIF | Chưa quét OWASP ZAP. Chưa đo coverage |

**Tự đánh giá:**
- Phần lõi đã chạy được và đo được: thu thập dữ liệu → làm sạch → bản đồ → gợi ý → ghép bạn → nhắn tin.
- Điểm mạnh về khoa học: mỗi lựa chọn thuật toán đều có số đo trên dữ liệu thật, kể cả số đo bác bỏ thiết kế ban đầu.
- Điểm yếu: đánh giá với người dùng thật chưa có, và mẫu khảo sát nhỏ.

---

## 6. Khó khăn và thiếu sót quan trọng

1. **Vị trí chỉ tới cấp phường:**
   - 984/1.012 tin chỉ có toạ độ mặc định của phường do sàn gán (một điểm ở Hưng Lợi gom hơn 200 tin), nên bản đồ bị vón
     cục.
   - Xử lý: bản đồ hai lớp và nhãn "vị trí tương đối".
   - Bổ sung: nhóm đang khảo sát thực địa, hiện có 8 nhà, 7 nhà đã nạp với toạ độ đo tại chỗ.
2. **Dữ liệu sàn hết hạn nhanh:**
   - Sau 3 tuần, 298 tin Chợ Tốt đã bị gỡ.
   - Lịch crawl tự động có cấu hình nhưng chưa ghi nhận lần chạy nào, phải crawl tay. Nguyên nhân chưa xác định.
3. **Mẫu khảo sát nhỏ:**
   - 33 phản hồi, trong khi thuyết minh bổ sung cam kết ≥ 150. Chỉ 19 hồ sơ có đủ phần lối sống.
   - Ghép bạn phải bổ sung hồ sơ mô phỏng (có gắn nhãn, không dùng trong số đo chính).
4. **Chưa có đánh giá người dùng thật:** P@10/NDCG@10 của gợi ý, điểm hài lòng của ghép bạn và SUS đều phụ thuộc buổi
   09/10. Nếu buổi này không diễn ra, các chỉ tiêu đã đăng ký sẽ không có số.
5. **Chỉ tiêu thuyết minh bổ sung chưa đạt:**
   - ≥ 3.000 tin: hiện 1.012 hiển thị trên 1.672 thu thập. Cần Thơ ít nguồn, và đề tài ưu tiên sạch hơn nhiều.
   - MAE sau 2 tuần: không đủ thời gian theo dõi.
   - Coverage ≥ 60% và OWASP ZAP: chưa chạy.
6. **Thay đổi so với thuyết minh:**
   - OSM thay Google Maps (lý do pháp lý).
   - MAUT thay cosine cho gợi ý; Gower + điều hoà thay cosine cho ghép bạn (có số đo chứng minh).
   - Cắt chức năng tạo nhóm chat 3+ người.
7. **Ghép mã nguồn:**
   - Chatbot, rủi ro, quản trị và trang chi tiết mới nằm ở nhánh khác. Lịch sử git không chung gốc với bản chính, và số
     migration bị trùng.
   - Đây là **rủi ro kỹ thuật lớn nhất trước code freeze 10/10**.
8. **Chức năng chưa có:** đánh giá phòng (sao, nhận xét), quên mật khẩu/OTP, so sánh phòng, thông báo tin mới.
9. **Giới hạn kỹ thuật:**
   - Quota chỉ đường ORS (đường đi mới lưu sẵn cho một phần tin).
   - Bản đồ nền, ảnh tin và chỉ đường đều cần Internet.
   - 674/1.012 tin (67%) không ghi diện tích. Hệ thống ước lượng theo giá và đánh dấu trong CSDL (`is_imputed_area`),
     nhưng **giao diện chưa phân biệt số ước lượng**. Cần sửa: ẩn hoặc ghi rõ "ước lượng" trước khi demo.
   - Chưa có dữ liệu "an ninh khu vực", trong khi 61% SV coi trọng yếu tố này.
10. **Pháp lý và đạo đức:**
    - Dữ liệu thu thập từ sàn chưa xác minh quyền sử dụng, chỉ dùng cho nghiên cứu và demo nội bộ.
    - Số điện thoại chủ trọ từ khảo sát cần sự đồng ý trước khi công khai (NĐ 13/2023/NĐ-CP).
    - Dữ liệu SV khảo sát không đưa lên git.

---

## 7. Kế hoạch đến nghiệm thu

| Ngày | Việc | Kết quả kiểm tra được |
|---|---|---|
| 08/10 | Ghép nhánh chatbot/rủi ro/quản trị vào bản chính, chạy lại toàn bộ kiểm thử. Đo lại chatbot trên dữ liệu thật | 1 nhánh chính chạy đủ module |
| 08/10 | Chuẩn bị phiếu SUS và phiếu đăng nhập MSSV; lưu sẵn đường đi còn thiếu | — |
| **09/10** | **Buổi thử nghiệm**: chấm ghép bạn → chấm mù gợi ý → SUS | CSV phán đoán, notebook 01/06 có số thật |
| 10/10 | Code freeze, sao lưu DB, quay video dự phòng | — |
| 10–11/10 | Hoàn thiện chương 4 (kết quả), báo cáo tóm tắt, bản tin, slide | Hồ sơ đầy đủ |

---

## 8. Kính đề nghị CBHD cho ý kiến

1. Với phạm vi trên, đề tài **có đủ điều kiện đưa ra hội đồng nghiệm thu** không? Nếu chưa, cần bổ sung tối thiểu những
   gì?
2. Thầy có chấp nhận các thay đổi so với thuyết minh ở mục 6.6 (OSM thay Google; MAUT và Gower thay cosine; cắt tạo nhóm)
   với lý do và số đo kèm theo không?
3. Thuyết minh bổ sung (≥ 3.000 tin, ≥ 150 phiếu, MAE 2 tuần…) có phải bản chính thức để hội đồng đối chiếu không? Nếu
   đúng, nhóm sẽ trình bày số thật và giải trình ở phần hạn chế.
4. Thiếu chức năng **đánh giá phòng** (nội dung 6) có cần bổ sung trước nghiệm thu không? Ước tính khoảng nửa ngày.
5. Thầy góp ý về kịch bản buổi thử nghiệm 09/10 (số SV, cách chọn SV) để kết quả đủ tin cậy.

*Tài liệu chi tiết:*
- *Kỹ thuật:* `docs/tech_specs/` (Map_MapLibre_POI, Recommendation, Chat_Realtime, Matching_Messaging_Design).
- *Quyết định:* `docs/DECISIONS.md` (ADR-001…022).
- *Notebook:* `eval/notebooks/01_recommendation_eval.ipynb`, `06_roommate_eval.ipynb`.
