# Báo cáo kiểm thử — Hệ thống Trọ CTU (THS2026-66)

_Ngày lập: 13/10/2026 · Phiên bản kiểm thử: nhánh `feature/ghep-ban-chat` + thay đổi chưa commit ngày 12–13/10 ·
Môi trường: Docker Compose (Postgres 16 + PostGIS 3.4 + pgvector, Redis 7, FastAPI, Next.js 14) trên macOS._

Sản phẩm thuyết minh mục 15.2 dòng 7 ("Báo cáo kiểm thử — Hệ thống hoàn chỉnh"). Mọi con số dưới đây đo thật trong ngày
12–13/10/2026; không có số ước lượng.

## 1. Kiểm thử tự động (backend)

Chạy trong container API trên cơ sở dữ liệu kiểm thử riêng `nckh_test` (không đụng dữ liệu dev — ADR-018):
`docker cp apps/api/tests/. <api>:/app/tests/ && docker compose exec -T -e GEMINI_API_KEY= api python -m pytest`.

**Kết quả: 645 ca — 624 đạt, 20 bỏ qua có điều kiện, 1 xfail đã biết, 0 lỗi** (69 giây).

| Nhóm chức năng | Số ca | Nội dung chính |
|---|---:|---|
| Thu thập & làm sạch dữ liệu | 107 | parser 6 nguồn, cleaner 5 tầng, trích điện/nước/cọc, liên hệ, địa chỉ, rà soát (audit), chốt chặn crawl (chỉ admin, lượt full lỗi không xoá tin, không hồi sinh tin bị loại, đổi toạ độ thì tính lại phút) |
| Tin trọ, bản đồ, đánh giá, quản trị, xác thực | 87 | tìm kiếm/lọc (quận qua `district_norm`), tin lân cận, tiện ích OSM, đường đi có cache, quản lý tin chỉ admin, đánh giá nhà trọ (1 đánh giá/tài khoản, chặn SĐT/link, kiểm duyệt), quản lý người dùng (khoá có hiệu lực ngay, chặn WebSocket), đăng nhập email/MSSV |
| Gợi ý nhà trọ | 16 | lọc + nới tiêu chí, MAUT, MMR, 2 hệ đối chứng |
| Ghép bạn ở & chat realtime | 153 | lọc cứng 2 tầng, Gower + harmonic, deck, lời mời, chấm điểm làm mù, chat WebSocket + Redis, ảnh, đồng ý chia sẻ liên hệ (T3), chịu lỗi Redis |
| Chatbot & kho pháp lý/KTX | 282 | phân loại câu hỏi (khẩn cấp, ngoài khu vực, tranh chấp tiền cọc), truy xuất BM25 + vector, kiểm chứng trích dẫn, mức phạt, giá điện, KTX CTU |

20 ca bỏ qua: 9 ca lịch sử chatbot và 1 ca truy xuất DB chạy trên schema cô lập (bật bằng biến môi trường), 7 ca Graph RAG
(tuỳ chọn, chưa dựng ở repo này), 1 ca cần corpus gắn ngoài, 2 ca mô phỏng cần file khảo sát `survey_v2.csv` (dữ liệu cá
nhân, không nằm trong repo). 1 xfail (`test_incomplete_exception_is_not_safe_evidence`) lỗi sẵn trên mã gốc branch PHUC.

## 2. Kiểm thử frontend

- Kiểm tra kiểu toàn bộ mã (`tsc --noEmit`) và build production (`next build`): đạt, 0 lỗi.
- Smoke 18 trang × 3 vai (khách / sinh viên / admin) trên bản production: đạt — trang công khai 200, trang cần đăng nhập
  chuyển về đăng nhập (307), trang quản trị với sinh viên 404, không có lỗi runtime trong HTML.
- Kiểm thử trên trình duyệt thật (Chrome, desktop 1440 px và khung 360–390 px): bản đồ (icon, cụm, chọn tin, đường đi,
  tiện ích, popup), thẻ tin trên điện thoại, menu điện thoại, bản đồ nhỏ, đăng nhập/đăng ký, khu đánh giá, Cẩm nang KTX, trợ
  lý mở với câu hỏi điền sẵn. Console trình duyệt: không lỗi.
- Hạn chế: chưa có kiểm thử tự động cho giao diện (unit/E2E) — các luồng trên kiểm thủ công và bằng HTTP.

## 3. Kiểm thử triển khai

- Dựng cơ sở dữ liệu từ volume rỗng (giống máy mới clone repo): đủ 21 migration (20–102), không lỗi khởi tạo; có bảng tiện
  ích (1.113 điểm), cột khoá tài khoản, ràng buộc đánh giá; DB kiểm thử `nckh_test` dựng cùng lúc.
- CI (`.github/workflows/ci.yml`): đường dẫn và lệnh khớp cấu trúc hiện tại.

## 4. Rà soát chất lượng (audit) và kết quả xử lý

Ngày 12/10, theo quy trình 4 vai (Tech Lead + 3 agent chuyên trách: cấu hình/CI, chức năng frontend, phân quyền & bảo mật):

| Mức | Số phát hiện | Đã sửa | Ví dụ |
|---|---:|---:|---|
| High | 4 | 4 | API kích crawl không cần đăng nhập; lượt crawl lỗi làm hết hạn toàn bộ tin của nguồn; Postgres/Redis mở cho cả mạng LAN; trang chủ lỗi 500 với URL sai kiểu |
| Medium | 13 | 13 | không có menu trên điện thoại; link Quản lý không hiện cho admin; form sập khi lỗi 422; nhãn hồ sơ ghép bạn sai; open redirect sau đăng nhập; lọc quận "Bình Thủy" sót tin; phút tới trường cũ sau khi đổi toạ độ |
| Low | 10 | 5 | đã sửa: giá "0.8 triệu", gõ tiếng Việt bị gửi dở, nhãn trùng ở form ghép bạn, id không phải số ở proxy; còn lại chấp nhận/ghi hạn chế (vd. `.env.example` chỉ đọc, file `plantuml.jar` trong git) |

Hai vòng rà soát mã sửa lỗi và mã mới (đánh giá nhà trọ, quản lý người dùng) bổ sung 11 điểm: sửa 10 (chặn thoát kiểm
duyệt bằng xoá–đăng lại, cắt kết nối chat của tài khoản bị khoá, lọc SĐT không chặn nhầm khoảng giá…), 1 điểm trợ năng sửa
một phần (nút chọn sao/quan hệ chưa có điều hướng bằng phím mũi tên).

Ngày 13/10 chạy lại kịch bản demo bằng HTTP thật: phát hiện 1 lỗi chặn demo — câu "Chủ trọ giữ cọc không trả thì sao?"
bị hiểu là tìm phòng. Đã sửa (phân loại + mở rộng truy vấn) — chatbot trả lời trích **BLDS Điều 328**, 7,3 giây.

## 5. Hiệu năng đo được

| Thao tác | Thời gian |
|---|---|
| Danh sách / chi tiết tin | 5–70 ms |
| Tin lân cận 5 km (~960 tin) | 40–200 ms |
| Đường đi (có cache) | 6–23 ms |
| Gợi ý nhà trọ (10 tin) | 20–500 ms |
| Chatbot — câu tìm phòng | ~1,9 s |
| Chatbot — câu pháp lý/KTX (Gemini) | 6–16 s |

## 6. Hạn chế còn lại

- Không thử nghiệm với người dùng (quyết định 14/10/2026, ADR-026) ⇒ không có P@10/NDCG@10, điểm hài lòng ghép bạn và SUS
  của người dùng thật; đánh giá hệ thống dựa trên số đo offline trên dữ liệu thật và mô phỏng (notebook 01, 06 chạy lại 14/10,
  đã bỏ phần sinh dữ liệu giả).
- Số phút đi xe là ước tính của OpenRouteService (profile ô tô, chưa tính kẹt xe); toạ độ khu là tâm khuôn viên, chưa phải
  cổng trường; đa số tin chỉ có vị trí cấp phường (UI ghi "vị trí tương đối").
- Chatbot phụ thuộc khoá Gemini và mạng; khi lỗi tự chuyển sang mô hình cục bộ/câu trả lời mẫu.
- Bản đồ nền, ảnh tin crawl cần Internet.
