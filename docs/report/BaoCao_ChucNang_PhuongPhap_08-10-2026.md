# Trọ CTU — Chức năng, phương pháp và phần AI

_Cập nhật 08/10/2026 · Đề tài THS2026-66 · Thay thế phần mô tả kỹ thuật của báo cáo gửi CBHD ngày 07/10 (bản đó giữ nguyên để lưu vết). Chatbot đã ghép vào bản chính; phần "cảnh báo rủi ro bằng AI" được thay bằng Cẩm nang._

## 1. Tóm tắt

Hệ thống web giúp sinh viên ĐH Cần Thơ tìm nhà trọ: **gom tin từ 7 nguồn → làm sạch → hiện trên bản đồ có đường đi → gợi ý theo tiêu chí → ghép bạn ở → nhắn tin → hỏi đáp bằng chatbot**. Hiện có khoảng 1.080 tin đang hiển thị (08/10).

**Phần nào là AI?** Nói thẳng để tránh hiểu nhầm:

| Mức | Thành phần | Bản chất |
|---|---|---|
| **AI học máy (mô hình có sẵn)** | Chatbot hỏi đáp | Mô hình ngôn ngữ lớn (Gemini, Qwen) + mô hình nhúng văn bản (E5) — nhóm **dùng**, không huấn luyện |
| **AI dựa trên tri thức** (nhánh cổ điển của AI, không học từ dữ liệu) | Gợi ý nhà trọ, ghép bạn ở | Hệ gợi ý knowledge-based: lọc ràng buộc + chấm điểm đa tiêu chí, trọng số lấy từ khảo sát |
| **Không phải AI** (luật, thuật toán thông thường) | Làm sạch tin, khử trùng lặp, định vị, chỉ đường, cẩm nang | Luật, regex, MinHash/LSH, đồ thị đường |

## 2. Chức năng, cách hoạt động, phương pháp

| # | Chức năng | Hoạt động thế nào | Phương pháp / thuật toán | AI? | Huấn luyện |
|---|---|---|---|---|---|
| 1 | Thu thập tin | Lấy tin từ 7 trang theo lịch, lưu vào CSDL | Crawler cấu hình bằng selector JSON; Chợ Tốt đọc qua JSON gateway | Không | — |
| 2 | Làm sạch & phân loại | Chia tin thành phòng trọ / nhà mini / nhà nguyên căn / mặt bằng; kiểm giá; điền diện tích; chấm điểm chất lượng 0–1 | Luật từ khoá + regex (5 tầng); khử trùng bằng MinHash/LSH (128 hàm băm, ngưỡng Jaccard 0,5) | Không | — |
| 3 | Định vị & bản đồ | Gán toạ độ, hiện ghim/cụm, vẽ đường từ CTU tới phòng, tính số phút đi xe | Geocode nhiều tầng (Nominatim/OSM); OpenRouteService (đồ thị đường OSM); truy vấn không gian PostGIS | Không | — |
| 4 | Gợi ý nhà trọ | Người dùng nhập ngân sách, khu CTU, thời gian đi, tiện ích → 10 tin kèm lý do | Lọc cứng → **MAUT** (điểm đa thuộc tính) → đa dạng hoá **MMR** | Tri thức | Không |
| 5 | Ghép bạn ở | Hiện bộ thẻ bạn hợp tính kèm % và lý do; hai bên cùng thích thì "Thành đôi" | Lọc cứng 2 tầng → **khoảng cách Gower có trọng số** → **trung bình điều hoà** hai chiều | Tri thức | Không |
| 6 | Nhắn tin | Chat realtime giữa hai người đã ghép; liên hệ chỉ lộ khi cả hai đồng ý | WebSocket + Redis pub/sub; xoá EXIF ảnh | Không | — |
| 7 | **Chatbot** | Trả lời tìm phòng và hỏi đáp pháp lý/KTX kèm trích dẫn nguồn | **RAG**: truy xuất lai (SQL + BM25 + vector) → LLM → kiểm chứng | **AI học máy** | Dùng mô hình có sẵn |
| 8 | Cẩm nang | 3 mục (tìm phòng, ở ghép, pháp lý & hợp đồng) kèm căn cứ điều luật | Nội dung biên soạn, trỏ điều khoản thật | Không | — |
| 9 | Quản lý nhà trọ | Chỉ admin nhập/sửa/ẩn tin | Phân quyền theo vai trò | Không | — |

## 3. Chi tiết từng chức năng

### 3.1 Thu thập và làm mới dữ liệu
- **Cách làm:** mỗi nguồn có cấu hình riêng. Hai chế độ: *quét nhanh* (1–2 trang đầu, bắt tin mới) và *quét sâu* (hết danh sách). Tin vắng mặt qua 2 lần quét sâu thì đánh dấu hết hạn; độ tươi tính theo `exp(−tuổi/7 ngày)`.
- **Làm mới tự động:** có thật nhưng **có điều kiện** — bộ hẹn giờ nằm trong tiến trình API nên chỉ chạy khi hệ thống đang bật liên tục, không chạy bù khi bị lỡ. Kiểm tra 08/10: lần chạy tự động gần nhất lấy về 62 tin mới, nhưng 3/7 nguồn bị treo; giờ chạy thực tế theo UTC (quét sâu rơi vào 10:00 giờ Việt Nam thay vì 3:00). Tin mới chưa tự qua bước rà soát chất lượng. Các điểm này đã ghi nhận để khắc phục.

### 3.2 Làm sạch và phân loại
Phân loại bằng luật, **không dùng học máy** vì chưa có tập dữ liệu gán nhãn. Luật minh bạch, giải thích được từng quyết định. Bộ phân loại khớp 785/789 (99,5%) với nhãn rà soát văn bản của một bộ dữ liệu Chợ Tốt độc lập (từ khoá được chỉnh trên chính tập này nên đây là độ khớp, chưa phải độ chính xác tổng quát). Lệnh rà soát ngày 07/10 loại 443/1.672 tin (chủ yếu tin đã gỡ khỏi nguồn: 325).

### 3.3 Định vị, bản đồ, đường đi
- Geocode theo tầng: địa chỉ có số nhà → phường → địa danh → tâm phường; chặn toạ độ ngoài khung Cần Thơ.
- Toạ độ nhiều tin chỉ tới cấp phường (một điểm mặc định gom hàng trăm tin), nên giao diện ghi "vị trí tương đối". Chỉ khoảng 4% tin có vị trí chính xác. Hệ thống chọn **trung thực về độ chính xác**.
- Số phút đi xe tới 3 khu CTU tính sẵn bằng ORS Matrix; đường đi lưu trong `route_cache`, dự phòng OSRM. 1.113 tiện ích OSM (chợ, nhà thuốc, trạm xe buýt…) tra bằng `ST_DWithin`.
- Không dùng Google Maps (như thuyết minh 13.1) vì, theo điều khoản Google Maps Platform mà nhóm đã tra cứu (báo cáo 07/10), Việt Nam nằm trong danh sách lãnh thổ bị hạn chế và điều khoản cấm lưu dữ liệu — nên đối chiếu lại điều khoản hiện hành trước khi trích trong báo cáo cuối.

### 3.4 Gợi ý nhà trọ (knowledge-based)
1. **Lọc cứng** theo ngân sách, thời gian đi, loại chỗ ở, giới tính; quá ít kết quả thì tự nới và báo rõ đã nới gì.
2. **MAUT:** U = Σ wₖ·uₖ. Hàm điểm uₖ đơn điệu (rẻ hơn ngân sách thì tốt, vượt thì trừ điểm). **Trọng số lấy từ tần suất 31 SV chọn "3 yếu tố quan trọng nhất"**, rồi co về lựa chọn của từng người. Tiện ích tin không nhắc tới là *chưa rõ* (điểm trung tính), không phải *không có*.
3. **MMR** để 10 tin không dồn vào cùng một chỗ.

**Vì sao không dùng lọc cộng tác hay cosine:** gần như không có lịch sử tương tác (5 dòng) nên không có gì để học; cosine không phân biệt được tin (cho điểm ≥ 0,9999 ở 100% tin trên vector [giá, phút]).

**Số đo offline** (31 bộ tiêu chí thật × 1.115 tin, chạy lại 14/10): thoả ràng buộc gốc 91,9%; độ đa dạng ILS@10 = 0,295 (chỉ tiêu ≤ 0,7); 9,97 vị trí khác nhau/10 tin — tốt hơn cách "lọc rồi sắp theo giá" (ILS 0,475; 8,07 vị trí); cosine của thiết kế gốc chỉ thoả 32,6%. **Không có số đo với người dùng thật** — không thử nghiệm người dùng (quyết định 14/10, ADR-026).

### 3.5 Ghép bạn ở (reciprocal recommender)
1. **Lọc cứng 2 tầng:** an toàn (cùng giới; deal-breaker hút thuốc/ở bẩn, phủ quyết hai chiều) → khả thi (ngân sách, thời điểm cần phòng).
2. **Khoảng cách Gower có trọng số** cho điểm có hướng s(A→B) và s(B→A) — xử lý được dữ liệu hỗn hợp.
3. **Trung bình điều hoà** hai điểm để chặn cặp chỉ hợp một chiều.
4. Bộ thẻ ưu tiên hồ sơ thật; thẻ mô phỏng tối đa 50% và gắn nhãn.

Số đo (notebook 06): lọc 2 tầng làm số người có ứng viên tăng 6/19 → 16/19; trọng số ±20% gần như không đổi thứ hạng (Kendall τ = 0,974). Điểm hài lòng so với ghép ngẫu nhiên: không đo (không thử nghiệm người dùng, ADR-026).

### 3.6 Chatbot — phần AI chính

**Hoạt động (RAG, tra cứu rồi mới trả lời):**
1. **Quy tắc chạy trước** (không dùng mô hình): tình huống khẩn cấp → hướng dẫn 113/114/115; câu ngoài khu vực ("phòng ở Hà Nội"); từ chối soạn hợp đồng; hiểu câu nối tiếp "rẻ hơn / gần hơn".
2. **Truy xuất lai:** lọc SQL + từ khoá (BM25) + vector (embedding `multilingual-e5-small`, 384 chiều) trên 1.081 tin và kho 45 văn bản pháp lý/KTX (571 đoạn).
3. **Sinh câu trả lời:** Gemini (`gemini-3.5-flash-lite`) là chính, Qwen2.5-7B chạy local (Ollama) dự phòng, cuối cùng là trích nguyên văn nguồn.
4. **Kiểm chứng:** mỗi kết luận phải gắn nguồn `[n]` và có căn cứ trong đoạn đã truy xuất, không thì bị loại và rơi về trích nguyên đoạn. Câu tìm phòng dùng khuôn trả lời cố định để không bịa giá, địa chỉ.

**Đo (08/10, bộ 36 câu pháp lý/KTX, gọi qua HTTP thật):** 0 lỗi, trung vị 10–15 giây/câu (chỉ Qwen: 70–85 giây). 27/36 câu hệ thống tự đánh giá "đầy đủ", 9/36 "một phần"; **chạy lặp thì dao động ±5 câu**, nên đây là mức tham khảo, chưa phải điểm chấm theo đáp án chuẩn. Đã sửa các lỗi phát hiện khi đánh giá (khẩn cấp, ngoài khu vực, mức phạt, giá điện bậc). Còn yếu: câu mà kho không có nguồn, lọc theo giá điện/nước của tin.

### 3.7 Cẩm nang
Thay cho "AI cảnh báo rủi ro": dữ liệu không có nhãn lừa đảo nào để huấn luyện hay đo recall, nên nhóm chọn trang cẩm nang (tìm phòng / ở ghép / pháp lý & hợp đồng) trỏ điều khoản thật (Bộ luật Dân sự Đ328, Luật Nhà ở, Luật Cư trú, Thông tư 60/2025…), cộng khung nhắc "Trước khi đặt cọc" ở trang chi tiết tin. Phù hợp thuyết minh 14.2 ("cảnh báo thông tin rủi ro", không nêu mô hình) và kết quả kỳ vọng ("nâng cao nhận thức"). Thuyết minh mục 13.2 loại trừ đi sâu pháp lý hợp đồng, nên cẩm nang chỉ nêu điều cần biết kèm dẫn nguồn.

## 4. Nếu là AI thì huấn luyện bao lâu?

**Nhóm không huấn luyện (training) mô hình nào** — thời gian huấn luyện của nhóm là **0**.

| Thành phần | Nguồn mô hình | Nhóm làm gì | Thời gian xử lý (đã đo 08/10) |
|---|---|---|---|
| Nhúng văn bản `multilingual-e5-small` | Có sẵn, chạy trong container | Chỉ *suy luận* (tính vector) | 48 ms/đoạn; nhúng toàn bộ 1.081 tin + 571 đoạn luật ≈ **1,3 phút trên CPU, một lần**; 10 ms/câu hỏi |
| Gemini `3.5-flash-lite` | Dịch vụ của Google, gọi qua API | Chỉ gọi | ~7–20 giây/câu trả lời pháp lý |
| Qwen2.5-7B | Có sẵn, chạy local (Ollama) | Chỉ chạy | ~3 giây (câu ngắn) đến 70+ giây (câu pháp lý) |
| Trọng số gợi ý (MAUT) và ghép bạn (Gower) | Thống kê từ khảo sát | Tính tần suất từ 31 phản hồi | Vài giây — **không phải huấn luyện mô hình** |

**Vì sao không huấn luyện:** (1) không có dữ liệu có nhãn (tập phân loại tin, nhãn lừa đảo = 0, tương tác người dùng = 5 dòng); (2) mẫu khảo sát nhỏ (33 phản hồi); (3) mô hình có sẵn đủ cho phạm vi đề tài; (4) huấn luyện thêm dễ khiến mô hình bịa tự tin hơn. Mọi cải tiến chatbot hiện tại đến từ sửa quy tắc và bổ sung tài liệu nguồn.

## 5. Vì sao không chỉ dùng ký túc xá?

- **Sức chứa có hạn:** KTX CTU có 3 khu, khoảng **8.780 chỗ**; sinh viên đăng ký rồi chờ kết quả sắp chỗ, không bảo đảm có chỗ.
- **Điều kiện cứng:** phí nộp theo học kỳ, không hoàn phí nếu trả chỗ trước hạn; nhiều loại phòng không được nấu ăn; cơ sở Hậu Giang chỉ xếp năm nhất và năm cuối, Sóc Trăng chỉ năm cuối.
- **Không thay thế được, chỉ bổ trợ:** KTX rẻ hơn (220.000–475.000 đồng/tháng so với trung vị phòng trọ khoảng 2,5 triệu), nên vẫn là lựa chọn tốt. Phần sinh viên không có chỗ hoặc cần ở riêng/ở ghép thì cần hệ thống này. Chatbot vẫn trả lời thông tin KTX kèm nguồn của CTU.

_(Số liệu KTX theo trang thông tin của CTU trong kho tài liệu chatbot, tải 07/10/2026.)_

## 6. Hạn chế cần nói rõ
- **Không có đánh giá với người dùng thật** (P@10/NDCG@10 gợi ý, điểm hài lòng ghép bạn, SUS): chủ nhiệm quyết định không thử nghiệm người dùng (14/10, ADR-026) — đánh giá dựa trên số đo offline trên dữ liệu thật và mô phỏng; công cụ chấm mù vẫn có sẵn trong hệ thống.
- **Dữ liệu:** vị trí chính xác chỉ ~4% tin; diện tích 67% là số hệ thống tự đoán theo giá; 333 tin của 3 nguồn bị treo chưa cập nhật từ 18/09.
- **Chatbot:** kết quả dao động giữa các lần chạy; chưa chấm theo đáp án chuẩn; số đo của nhánh Phúc (36 câu, RAGAS) dùng mô hình qua proxy chưa xác minh nên chỉ để tham khảo.
- **Thay đổi so với thuyết minh:** OSM thay Google Maps; MAUT/Gower thay cosine; cắt tạo nhóm 3+ người; bỏ đăng tin cho sinh viên (chỉ admin nhập tin); cảnh báo rủi ro bằng cẩm nang thay vì mô hình AI — **cần báo CBHD**.
- **Chưa làm:** quên mật khẩu/OTP, đánh giá phòng (sao, nhận xét), so sánh phòng, thông báo tin mới; OWASP ZAP và đo coverage.

## 7. Nguồn số liệu
Notebook `eval/notebooks/01` (gợi ý) và `06` (ghép bạn); `docs/tech_specs/Chatbot.md`, `docs/CHECKPOINT.md` (đo chatbot 08/10); `docs/DECISIONS.md` (ADR-021…024); báo cáo gửi CBHD 07/10; tài liệu KTX trong `apps/api/chatbot_corpus/`.
