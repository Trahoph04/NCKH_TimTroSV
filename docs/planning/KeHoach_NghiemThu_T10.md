# Kế hoạch 4 tuần đến nghiệm thu — THS2026-66

_Lập: 13/09/2026 · Mốc nghiệm thu: **tuần 12–16/10/2026** · Chủ nhiệm: Phú_

> Nguyên tắc xuyên suốt: **hội đồng chấm 3 thứ — demo chạy trót lọt, báo cáo có số liệu, mỗi nội dung đã đăng ký trong thuyết minh có sản phẩm tương ứng.** Mọi việc không phục vụ 1 trong 3 thứ đó thì cắt.

---

## 0. Hiện trạng (đối chiếu code ngày 13/09)

| Đã xong (không đụng nữa) | Chưa có (phải làm trong 4 tuần) |
|---|---|
| Crawler 6 nguồn + cleaner 5 tầng (~300 tin sạch) | **Bảng `reviews`** + API đánh giá / khiếu nại |
| Auth JWT, UGC đăng/sửa/ẩn tin, Tin của tôi | **Risk engine** — `risk_score` toàn bộ = 0, badge "Chưa rõ" |
| Trang chủ + lọc, chi tiết tin, theme mới | **Gợi ý nhà trọ** (content-based) — chưa có endpoint |
| Bản đồ Leaflet: bán kính, 3 khu, phút đi xe (ORS), cluster | **Ghép bạn ở**: có bảng `roommate_profiles`/`match_requests`, chưa có thuật toán, API, UI, Zalo |
| Sơ đồ UC/ERD/Class/Sequence (Diagrams/) | **Chatbot RAG** — chưa có LLM, embedding, tài liệu pháp lý |
| 86 unit test backend | **Eval notebooks** 04/05/06 + dataset ground-truth |
| Form khảo sát v2 (~30 phản hồi) | **Báo cáo tổng kết, báo cáo tóm tắt, bản tin, slides** |

Kết luận: nền tảng dữ liệu + web đã ổn; **4 module AI và toàn bộ hồ sơ nghiệm thu là 0%**. Bốn tuần phải dồn vào đó.

---

## 1. Chốt scope (quyết định ngay tuần 1, không bàn lại)

### 1.1 Làm — đúng 4 module, mỗi module ở mức "chạy được + đo được"

| Module | Phạm vi tối thiểu để nghiệm thu | Số liệu đưa vào báo cáo |
|---|---|---|
| **A. Bản đồ + Review + Cảnh báo rủi ro** (kiểu nhaminhbach.com) | Review 1–5 sao + tag ("cọc không trả", "giá không đúng", "điện nước cao", "an ninh kém", "chủ tốt"); marker màu xanh/vàng/đỏ/xám trong bán kính CTU; panel review khi bấm marker; nút Khiếu nại (bảng `reports` có sẵn) | Recall cảnh báo trên 100 tin gán nhãn (≥30 tin rủi ro); phân bố risk_score |
| **B. Gợi ý nhà trọ** | Content-based cosine: vector (giá, diện tích, phút tới khu học, tiện ích, quận) × hồ sơ SV (C1–C5 form); endpoint `/recommend`; khối "Gợi ý cho bạn" ở trang chủ | Precision@10, NDCG@10 với ground-truth Form 2 (20–30 SV) |
| **C. Ghép bạn ở + Zalo** | Bộ lọc cứng (giới tính, thuốc lá, D14) → điểm tương thích có trọng số (sleep, cleanliness, noise, D11, ngân sách, cùng khu) → top-5; gửi/nhận lời mời; **chấp nhận đôi bên mới lộ link `zalo.me/<sđt>`** | Điểm hài lòng 1–5 của 20 SV với top-3 gợi ý; so với baseline ngẫu nhiên; N hồ sơ (mục tiêu 80) |
| **D. Chatbot RAG** | Gemini + embedding; 2 nguồn tri thức: (1) dữ liệu tin trong DB, (2) **bộ văn bản pháp lý về thuê trọ** (xem 1.3); trả lời có trích nguồn | RAGAS Faithfulness / Answer Relevancy trên 50 câu hỏi; fallback chấm tay 2 người |

### 1.2 Cắt / thay thế (ghi rõ lý do trong báo cáo, mục "Hạn chế & hướng phát triển")

| Thuyết minh ghi | Làm thay bằng | Lý do đưa vào báo cáo |
|---|---|---|
| Nhắn tin, tạo nhóm trong web | Kết nối Zalo sau khi match | Tận dụng kênh SV đã dùng, tránh lưu tin nhắn riêng tư → an toàn dữ liệu hơn |
| Isolation Forest phát hiện gian lận | Rule-based + Isolation Forest **chỉ trên giá/m²** | Không có đủ tin lừa đảo thật để học; rule minh bạch, giải thích được |
| MAE feedback sau 2 tuần (Thuyết minh bổ sung) | Khảo sát hài lòng tức thời 20 SV | Không đủ thời gian theo dõi 2 tuần |
| ≥3000 listing (bổ sung) | Báo số thật (~300–500) | Cần Thơ có ít nguồn; báo cáo theo thuyết minh gốc (không ghi 3000) |
| Deploy public | Demo local Docker + video dự phòng | Ưu tiên ổn định khi demo |

### 1.3 Tài liệu pháp lý cho chatbot (tải từ thuvienphapluat.vn, lưu `apps/api/app/rag/docs/`)

1. Bộ luật Dân sự 2015 — Mục 5 Hợp đồng thuê tài sản (Điều 472–482), Điều 328 đặt cọc.
2. Luật Nhà ở 2023 — chương về cho thuê nhà ở (quyền/nghĩa vụ bên thuê – bên cho thuê, chấm dứt hợp đồng).
3. Luật Cư trú 2020 + Nghị định 62/2021 — đăng ký tạm trú cho người thuê.
4. Quy định giá điện cho người thuê nhà (Thông tư 16/2014/TT-BCT, sửa đổi bởi Thông tư 09/2023) — câu hỏi SV hỏi nhiều nhất.
5. Quy định an toàn PCCC nhà trọ (văn bản mới nhất hiện hành — tra cứu lại trước khi nạp).
6. Quy định sinh viên ngoại trú của CTU (nếu có văn bản nội bộ).

> Mỗi văn bản: lưu `.md` kèm tên văn bản + số hiệu + ngày hiệu lực; chunk theo Điều. Kiểm tra lại số hiệu/hiệu lực trước khi đưa vào báo cáo.

---

## 2. Lịch tuần

### Tuần 1 · 14–20/09 — "Mọi module có backend chạy được"

| Việc | Người | Sản phẩm kiểm tra được |
|---|---|---|
| Migration `90_reviews.sql` (reviews, review_tags), API `POST/GET /listings/{id}/reviews`, `POST /listings/{id}/report` | Lợi | `curl` tạo được review, test pass |
| Risk engine `apps/api/app/risk/`: score = 0.5·review_signal + 0.3·price_anomaly(IsolationForest giá/m² theo quận) + 0.2·content_rule (thiếu địa chỉ, giá quá rẻ, ảnh stock trùng); ghi `risk_score`/`risk_reasons`; job chạy sau cleaner | Phú | 300 tin có score ≠ 0; badge đổi màu |
| Recommendation `apps/api/app/recsys/`: build feature vector, `GET /recommend?budget&campus&max_minutes&amenities` | Huy | Trả 10 tin, giải thích "vì sao gợi ý" |
| Matching `apps/api/app/matching/`: script `import_survey.py` (CSV form v2 → `roommate_profiles`), hàm `score(a,b)`, `GET /matching/suggest` | Phú + Huy | 30 hồ sơ thật import được, top-5 ra hợp lý |
| RAG skeleton: `GEMINI_API_KEY` vào config, chọn embedding (`intfloat/multilingual-e5-small` local hoặc Gemini embedding), bảng `rag_chunks (vector)`, ingest 6 văn bản 1.3, `POST /chat` | Phúc + Phú | Hỏi "tiền cọc có được trả lại không?" → trả lời có trích Điều |
| **Đẩy khảo sát lên 80**: đăng lại form ở group K49/K50 CTU, nhóm lớp, ký túc xá; kèm quà (thẻ cào 50k bốc thăm) | Bảo + cả nhóm | Sheet đạt ≥60 vào 20/09 |
| Khung báo cáo tổng kết (5 chương, xem mục 4) + viết Chương 1 (đặt vấn đề) và Chương 2 (khảo sát — phân tích 30–60 phản hồi đã có bằng pandas) | Phúc | File `docs/report/BaoCao_TongKet.docx` có Ch.1–2 |

### Tuần 2 · 21–27/09 — "Mọi module có giao diện, demo được từng màn"

| Việc | Người | Sản phẩm kiểm tra được |
|---|---|---|
| `/map`: marker màu theo `risk_level`; panel trái khi bấm marker = địa chỉ + sao + danh sách review + nút "Review nhà này" / "Khiếu nại" (bố cục như ảnh nhaminhbach) | Lợi | Ảnh chụp màn hình cho báo cáo |
| Trang chi tiết tin: khối review + form đánh giá (đăng nhập mới được review) | Bảo | |
| Trang chủ: khối "Gợi ý cho bạn" (lấy hồ sơ từ `users.preference` hoặc 4 ô nhập nhanh) | Huy | |
| Trang `/roommate`: form hồ sơ (mapping 1:1 câu D của form), danh sách top-5 kèm % tương thích + lý do, nút Gửi lời mời / Chấp nhận, hiện nút Zalo khi 2 bên chấp nhận | Huy + Bảo | |
| Chatbot: FAB góc phải, hiển thị câu trả lời + nguồn (Điều luật hoặc tin số #) | Phúc | |
| **Dataset đánh giá**: `eval/data/scam_labels.csv` 100 tin gán nhãn tay (2 người gán độc lập, ghi Cohen's kappa); `qa_test.json` 50 câu hỏi + đáp án kỳ vọng; Form 2 ground-truth gợi ý (15–20 tin thật, "tin nào bạn sẽ gọi?") phát cho 30 SV | Phúc (scam) · Bảo (QA) · Phú (Form 2) | 3 file trong `eval/data/` |
| Viết Chương 3 (thiết kế hệ thống — tái dùng Diagrams/) | Phú | |

### Tuần 3 · 28/09–04/10 — "Đo, thử nghiệm với người dùng, viết kết quả"

| Việc | Người | Sản phẩm kiểm tra được |
|---|---|---|
| Chạy notebook `01_recommendation_eval`, `04_risk_eval`, `05_rag_eval`, `06_roommate_eval` → bảng số liệu + biểu đồ | Phú + Huy | 4 notebook có output, PNG biểu đồ |
| **Thử nghiệm người dùng** 20–30 SV (1 buổi tại trường): dùng 4 chức năng theo kịch bản, chấm SUS 10 câu + đánh giá top-3 ghép bạn 1–5 | Bảo + Phúc | Bảng SUS, điểm hài lòng, ghi nhận lỗi |
| Kiểm thử: test case thủ công 40–60 ca theo use case (Test_Plan.md), bổ sung unit test cho 4 module; bảng kết quả pass/fail | Lợi + Bảo | `docs/report/BaoCao_KiemThu.md` |
| Sửa lỗi phát hiện từ thử nghiệm (chỉ lỗi chặn demo) | Lợi + Huy | |
| Viết Chương 4 (kết quả thực nghiệm: số liệu 4 module + khảo sát người dùng) | Phú + Phúc | |

### Tuần 4 · 05–11/10 — "Đóng gói hồ sơ, tập demo"

| Việc | Người | Hạn |
|---|---|---|
| **Code freeze 08/10** — sau đó chỉ sửa lỗi demo | cả nhóm | 08/10 |
| Chương 5 (kết luận, hạn chế, hướng phát triển) + hoàn thiện toàn bộ báo cáo tổng kết theo mẫu ĐHCT; tài liệu tham khảo (ghép [1]–[9] gốc + [R1]–[R11] bổ sung) | Phú | 07/10 |
| Báo cáo tóm tắt (8–10 trang) + Bản tin (1 trang) theo mẫu ĐHCT | Phúc | 08/10 |
| Slides 15–20 trang + kịch bản demo 8 phút (mục 5) | Bảo + Lợi | 09/10 |
| Quay video demo dự phòng 5 phút (phòng khi mạng/Docker lỗi) | Huy | 09/10 |
| Tập demo 2 lần trước nhóm, 1 lần trước GVHD (TS. Nguyễn Công Danh) — gửi báo cáo cho GVHD góp ý **trước 05/10** | cả nhóm | 10/10 |
| Kiểm tra hồ sơ (mục 6), in ấn, nộp | Phú | 11/10 |

### 12–16/10 — Nghiệm thu. Dự phòng 3 ngày cho yêu cầu chỉnh sửa của hội đồng.

---

## 3. Phân công tổng thể (khớp nhiệm vụ trong thuyết minh)

| Người | Lane chính | Chương báo cáo |
|---|---|---|
| **Phú** (CN) | Risk engine, matching, RAG core, tích hợp AI, tổng hợp báo cáo | Ch.3, Ch.4, Ch.5, tổng hợp |
| **Phúc** | Phân tích khảo sát, chatbot UI + dataset QA, gán nhãn scam, báo cáo tóm tắt + bản tin | Ch.1, Ch.2 |
| **Lợi** | Backend review/report, FE map & chi tiết, kiểm thử | Báo cáo kiểm thử |
| **Huy** | Recommendation, matching API+UI, notebook eval, video demo | Ch.4 (phần số liệu) |
| **Bảo** | Review UI, roommate UI, thu khảo sát, thử nghiệm người dùng, slides | Phụ lục khảo sát, slides |

Họp nhóm **thứ 2 & thứ 5 hàng tuần, 30 phút**: mỗi người báo "đã xong / đang kẹt / cần gì". Ghi vào `task.md`.

---

## 4. Cấu trúc báo cáo tổng kết (viết song song, không để cuối)

1. **Đặt vấn đề** — thực trạng tìm trọ SV CTU, mục tiêu, phạm vi (bán kính 2–3 km quanh 3 khu CTU).
2. **Khảo sát & phân tích nhu cầu** — N phản hồi, tiêu chí chọn trọ, khó khăn, rủi ro từng gặp (B5), kỳ vọng tính năng (E1) → luận cứ cho 4 module.
3. **Thiết kế hệ thống** — kiến trúc 3 tầng, ERD, use case, pipeline dữ liệu (crawler → cleaner → geocode → route), thiết kế từng module AI (công thức điểm, sơ đồ RAG).
4. **Kết quả thực nghiệm** — số liệu dữ liệu (tin, nguồn, chất lượng), 4 bảng metric, ảnh màn hình, SUS + phản hồi người dùng, kết quả kiểm thử.
5. **Kết luận** — đạt gì so với mục tiêu 12.2, hạn chế (mục 1.2 ở trên), hướng phát triển.
Phụ lục: bộ câu hỏi khảo sát, hướng dẫn cài đặt, danh sách test case.

---

## 5. Kịch bản demo 8 phút (tập đúng thứ tự này)

1. (1') Trang chủ — số liệu thật, lọc "Dưới 2 triệu · Khu II · ≤10 phút".
2. (2') Bản đồ — bán kính quanh Khu II, marker đỏ → bấm → review 1 sao "cọc không trả" + lý do rủi ro; marker xanh → review tốt. Bấm "Khiếu nại".
3. (1') Gợi ý cho bạn — nhập ngân sách/khu/tiện ích → 10 tin + lý do.
4. (2') Ghép bạn ở — hồ sơ đã điền → top-5 kèm % → gửi lời mời → tài khoản thứ 2 chấp nhận → hiện nút Zalo.
5. (1.5') Chatbot — "Chủ trọ giữ cọc không trả thì sao?" (trích BLDS Điều 328) và "Phòng nào dưới 1.5 triệu gần khu I?" (trích DB).
6. (0.5') Slide số liệu: 4 metric + SUS.

Chuẩn bị sẵn: 2 tài khoản đăng nhập, DB đã seed review mẫu, `docker compose up` trước 30 phút, video dự phòng.

---

## 6. Checklist hồ sơ nghiệm thu

- [ ] Báo cáo tổng kết theo mẫu ĐHCT (in + PDF)
- [ ] Báo cáo tóm tắt
- [ ] Bản tin
- [ ] Sản phẩm: source code (zip + GitHub), `Deployment_Guide.md`, video demo
- [ ] Minh chứng: sheet khảo sát, `eval/data/*`, 4 notebook có output, báo cáo kiểm thử
- [ ] Slides + kịch bản demo
- [ ] Bảng kê khối lượng công việc + chứng từ thanh quyết toán (đã chuẩn bị đợt trước — kiểm tra lại)
- [ ] Ý kiến GVHD trước khi nộp

---

## 7. Rủi ro & xử lý

| Rủi ro | Dấu hiệu | Xử lý |
|---|---|---|
| Khảo sát không đủ 80 | 20/09 chưa tới 60 | Chấp nhận N thật, bổ sung 30–50 hồ sơ mô phỏng **ghi rõ là mô phỏng** chỉ để demo matching; số liệu eval dùng hồ sơ thật |
| Gemini free tier bị giới hạn khi demo | 429 lúc tập demo | Cache 20 câu hỏi demo sẵn; provider có thể đổi sang Groq |
| Recall cảnh báo < 85% | notebook 04 | Báo số thật + phân tích lỗi; đừng sửa nhãn cho đẹp |
| Thành viên bận thi/đồ án | tuần 3 trễ | Việc tuần 3 của mỗi người đều có người dự phòng (bảng mục 3) |
| Docker hỏng ngày demo | — | Video dự phòng + DB dump `pgdata` sao lưu ngày 08/10 |

---

## 8. Việc ngay hôm nay (13–14/09)

1. Gửi kế hoạch này cho nhóm + chốt lịch họp thứ 2.
2. Đăng lại link khảo sát kèm quà bốc thăm.
3. Tạo `GEMINI_API_KEY` (AI Studio) và thêm vào `.env`.
4. Bắt đầu module A (review + risk) — phiên làm việc tiếp theo với Claude.
