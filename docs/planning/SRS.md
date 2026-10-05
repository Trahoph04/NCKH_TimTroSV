# Đặc Tả Yêu Cầu Phần Mềm (SRS)
## Hệ thống tổng hợp & gợi ý nhà trọ AI cho sinh viên ĐH Cần Thơ

**Đề tài:** THS2026-66 · **Phiên bản:** 1.0 · **Ngày:** 29/06/2026
**Chuẩn tham chiếu:** IEEE 830-1998

---

## 1. Giới thiệu

### 1.1 Mục đích
Tài liệu đặc tả đầy đủ yêu cầu chức năng (FR) và phi chức năng (NFR) của hệ thống, làm cơ sở thiết kế, hiện thực, kiểm thử và nghiệm thu. Đối tượng đọc: nhóm nghiên cứu, cán bộ hướng dẫn, hội đồng nghiệm thu.

### 1.2 Phạm vi
Hệ thống web tổng hợp tin nhà trọ từ nhiều nguồn, chuẩn hóa và lưu trữ, kèm các tính năng AI: gợi ý nhà trọ cá nhân hóa, tìm bạn ở ghép, chatbot RAG, cảnh báo rủi ro. Giới hạn địa lý: khu vực quanh ĐH Cần Thơ (quận Ninh Kiều và lân cận).

### 1.3 Định nghĩa & viết tắt
| Thuật ngữ | Ý nghĩa |
|---|---|
| FR / NFR | Functional / Non-Functional Requirement |
| RAG | Retrieval-Augmented Generation |
| Listing | Tin đăng nhà trọ |
| Crawler | Bộ thu thập dữ liệu tự động |
| Cold-start | Vấn đề gợi ý cho user mới chưa có lịch sử |
| Freshness | Độ tươi của tin (còn cập nhật gần đây hay không) |

### 1.4 Tài liệu liên quan
- `Agent-Generated/02_PhanTich_NghiepVu_Va_DuLieu.md` — phân tích nghiệp vụ, schema
- `Agent-Generated/04_PhanTich_BaiToanAn.md` — bài toán kỹ thuật T1-T11
- `Agent-Generated/05_DacTa_UseCase.md` — đặc tả use case
- `Document/Technical_Roadmap.md` — giải pháp kỹ thuật + DoD
- `Document/API_Specification.md` — đặc tả API

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm
Kiến trúc tách Frontend (Next.js) — Backend (FastAPI) — Database (PostgreSQL + PostGIS + pgvector) — Cache (Redis). Crawler chạy batch định kỳ (near-fresh, không real-time). Triển khai free-tier (nguyên tắc P1: chi phí vận hành 0đ trong thời gian đề tài).

### 2.2 Tác nhân (Actor)
- **Guest:** tìm kiếm, xem tin, xem bản đồ, xem badge rủi ro — không cần đăng nhập.
- **User (sinh viên):** kế thừa Guest + gợi ý AI, chatbot, ở ghép, lưu tin, đăng tin, đánh giá.
- **Admin:** quản trị nội dung, kiểm duyệt tin flagged, cấu hình crawler, dashboard.
- **System (Cron/Scheduler):** crawler tự động, AI pipeline, scheduled jobs.

### 2.3 Ràng buộc
- Ngân sách hạ tầng = 0đ trong thời gian đề tài (P1): dùng free-tier, tránh API trả phí (Google Maps → thay Nominatim/OSM; Gemini free-tier cho RAG).
- Không tự động XÓA dữ liệu (P2): mọi tin nghi vấn chỉ ẩn/cảnh báo, Admin quyết định destructive.
- Tôn trọng ToS nguồn crawl: rate-limit, không cào nguồn cấm.

---

## 3. Yêu cầu chức năng (FR)

### FR-1: Xác thực & Phân quyền
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-1.1 | Đăng ký bằng email + xác thực OTP | Guest |
| FR-1.2 | Đăng nhập email/password, cấp JWT (access 15p, refresh 7 ngày) | Guest |
| FR-1.3 | Đăng nhập Google OAuth 2.0 | Guest |
| FR-1.4 | Quên/đặt lại mật khẩu qua email | Guest |
| FR-1.5 | Quản lý hồ sơ cá nhân | User |
| FR-1.6 | Phân quyền theo role (guest/user/admin) | System |

### FR-2: Tìm kiếm & Xem tin
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-2.1 | Tìm kiếm theo từ khóa | Guest |
| FR-2.2 | Lọc đa tiêu chí (giá, diện tích, quận/phường, tiện ích, khoảng cách CTU) | Guest |
| FR-2.3 | Sắp xếp (giá ↑↓, mới nhất, gần CTU, độ tươi) | Guest |
| FR-2.4 | Bản đồ Leaflet/OSM, pin → popup | Guest |
| FR-2.5 | Tìm theo bán kính trên bản đồ | Guest |
| FR-2.6 | Trang chi tiết (gallery, giá, tiện ích, bản đồ mini, nguồn, thời gian cập nhật) | Guest |
| FR-2.7 | So sánh 2-3 phòng | User |
| FR-2.8 | Ẩn tin status=expired khỏi kết quả; hiển badge "cập nhật X giờ trước" | System |

### FR-3: Thu thập & Quản lý dữ liệu (Crawler Pipeline)
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-3.1 | Crawl batch định kỳ: incremental mỗi 5h, full sweep 3h sáng | System |
| FR-3.2 | Rate-limit 1req/5s + xoay User-Agent; 403/429 → alert + bỏ nguồn (T1) | System |
| FR-3.3 | Parser plugin JSON selector cho từng nguồn (không hard-code) | System |
| FR-3.4 | Chuẩn hóa giá/diện tích/tiện ích từ text tự do (NLP) | System |
| FR-3.5 | Geocoding đa tầng Nominatim → landmark → ward centroid (T2) | System |
| FR-3.6 | Khử trùng MinHash/LSH cross-source, ngưỡng Jaccard (T4) | System |
| FR-3.7 | Freshness: last_seen, miss_count, expired khi miss ≥2 (T11, không xóa) | System |
| FR-3.8 | Tính khoảng cách PostGIS đến CTU/POI khi insert | System |

### FR-4: Gợi ý cá nhân hóa (AI)
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-4.1 | Onboarding quiz → preference_vector 384-dim (T5) | User |
| FR-4.2 | Gợi ý "Dành cho bạn" Top-10 Content-Based Cosine | User |
| FR-4.3 | Cold-start: chưa có vector → Popularity-Based fallback | User |
| FR-4.4 | Ghi implicit feedback (view/bookmark/click) | User |
| FR-4.5 | Khám phá ε-greedy 80/20 chống filter bubble (T6) | User |

### FR-5: Tìm bạn ở ghép (AI)
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-5.1 | Điền hồ sơ ở ghép **12 câu theo form khảo sát v2** (giới tính, Trường/Khoa, ngân sách, kịch bản ở, giờ ngủ, rửa chén, chịu ồn, máy lạnh, chia tiền, hút thuốc, hành vi, deal-breaker) — lưu xong trả ngay top-3 | User |
| FR-5.2 | Điểm tương thích = **Gower có trọng số** (trọng số dẫn từ khảo sát) cho từng chiều → điểm có hướng s(A→B), s(B→A) → **harmonic mean** → xếp top-K kèm lý do/lưu ý (ADR-013). *Thay cho "Weighted Cosine ≥ 0,7": đo trên 93 cặp cùng giới của khảo sát, 91,4% cặp có cosine ≥ 0,7 ⇒ ngưỡng không loại được ai (notebook 06 mục 2)* | User |
| FR-5.3 | Gửi lời mời kết nối (thích / lời mời kèm lời nhắn); hai bên cùng thích ⇒ thành đôi + mở chat; liên hệ chỉ lộ khi **cả hai** bấm đồng ý lần nữa (T3) | User |
| FR-5.4 | **Chỉ ghép cùng giới**, tuyệt đối, không có tuỳ chọn. Hồ sơ `gender = NULL` ⇒ **ngoài pool** (không đoán giới tính của ai) | System |
| FR-5.5 | **Lọc cứng 2 tầng** (ADR-014): tầng an toàn = cùng giới + deal-breaker *hút thuốc trong phòng* / *ở bẩn* (veto hai chiều); tầng khả thi = ngân sách lệch > 1 bậc, khai "ở một mình", thời điểm cần phòng lệch > 2 tháng. Deal-breaker còn lại là **mềm**: trừ điểm + cảnh báo rõ chữ trên thẻ, không ẩn | System |
| FR-5.6 | Deck: hồ sơ thật ưu tiên, thẻ mô phỏng ≤ 50%; ε-greedy 80/20; chế độ `random` cho buổi thử nghiệm (xáo thứ tự, ẩn %); telemetry do server ghi (`deck_log`, ADR-015) | System |

### FR-6: Chatbot RAG (AI)
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-6.1 | Hỏi đáp ngôn ngữ tự nhiên, trả lời kèm danh sách phòng | User |
| FR-6.2 | Confidence thresholding ≥0.65, dưới ngưỡng → fallback không bịa (T8) | System |
| FR-6.3 | Conversation memory 5 lượt gần nhất (T9) | User |
| FR-6.4 | Gắn trích dẫn nguồn vào câu trả lời | System |

### FR-7: Cảnh báo rủi ro (AI)
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-7.1 | Risk Detection 5 lớp (rule + IsolationForest + cross-platform...) (T10) | System |
| FR-7.2 | Badge 3 mức (✅/⚠️/🔴) trên mỗi tin | Guest |
| FR-7.3 | Popup giải thích risk_reasons[] | Guest |
| FR-7.4 | Báo cáo tin sai (reports) | User |

### FR-8: Thông báo & Quản trị
| ID | Yêu cầu | Quyền |
|---|---|---|
| FR-8.1 | Thông báo tin mới khớp tiêu chí đã lưu | User |
| FR-8.2 | Thông báo có bạn ghép tương thích | User |
| FR-8.3 | Admin dashboard (tổng tin, tin mới, report, crawler status) | Admin |
| FR-8.4 | Kiểm duyệt tin flagged (duyệt/ẩn) | Admin |
| FR-8.5 | Cấu hình crawler (bật/tắt nguồn, tần suất, log) | Admin |

---

## 4. Yêu cầu phi chức năng (NFR)

### NFR-1: Hiệu năng
- Tìm kiếm + filter trả kết quả < 2s với ≤5000 listing.
- Báo cáo freshness 1-click < 2s.
- Chatbot RAG trả lời < 5s (gồm vector search + LLM).
- Recommend API < 1s cho Top-10.

### NFR-2: Bảo mật
- Password hash bcrypt; không lưu plaintext.
- JWT access token 15p + refresh 7 ngày; refresh rotation.
- Validate input mọi endpoint (chống SQLi/XSS); ORM tham số hóa.
- HTTPS bắt buộc ở production (Let's Encrypt).
- Rate-limit API public chống abuse.
- Endpoint mạng phải có auth trừ các route công khai (search/detail/badge).

### NFR-3: Khả dụng (Usability)
- Giao diện tiếng Việt, responsive (mobile + desktop).
- Guest dùng được tìm kiếm cơ bản không cần đăng nhập.
- User mới luôn thấy ≥10 gợi ý lần đầu (không màn hình rỗng).
- Accessibility: tuân thủ WCAG ở mức khả thi (alt text, contrast).

### NFR-4: Độ tin cậy & Tính tươi của dữ liệu
- Crawler uptime 7 ngày không bị block; layout-change recovery ≤15 phút sửa.
- Health check: <10 tin mới/lần crawl → cảnh báo Admin.
- Tin >30 ngày không thấy lại → gắn stale/expired.
- Không mất dữ liệu hợp lệ: chỉ ẩn, không xóa tự động (P2).

### NFR-5: Khả năng bảo trì & Mở rộng
- Thêm nguồn crawl mới = thêm 1 file `<source>.json` selector, không sửa code Python.
- Code tách module (crawler/recommend/chatbot/risk độc lập).
- Unit test coverage ≥60% (mục tiêu nghiệm thu).

### NFR-6: Chi phí (ràng buộc đề tài)
- Vận hành 0đ trong thời gian đề tài: free-tier (Vercel/Render + Supabase PG + Gemini free + OSM).
- Tính toán nội bộ thay API trả phí (geocode Nominatim, distance PostGIS).

---

## 5. Tiêu chí nghiệm thu (Acceptance)

| Module | Metric | Ngưỡng đạt |
|---|---|---|
| Crawler | Uptime 7 ngày, recovery layout-change | Không block, ≤15ph |
| Geocoding | % confidence ≥ medium | ≥80% |
| Dedup | Recall / False-merge | ≥90% / ≤5% |
| Recommendation | Precision@10 / NDCG@10 / ILS | ≥0.6 / ≥0.65 / ≤0.7 |
| Roommate | MAE feedback 2 tuần | ≤1.5/5 |
| Chatbot RAG | Faithfulness / Answer Relevancy | ≥0.7 / ≥0.75 |
| Risk | Recall trên 100 tin scam | ≥85% |
| Freshness | Báo cáo 1-click | <2s |
| Test | Unit coverage | ≥60% |

---

## 6. Phụ lục: Truy vết FR ↔ Bài toán kỹ thuật

| Bài toán | FR liên quan | Module |
|---|---|---|
| T1 Crawler chặn | FR-3.1, FR-3.2, FR-3.3 | Crawler |
| T2 Geocoding | FR-3.5 | Crawler |
| T4 Dedup | FR-3.6 | Crawler |
| T5 Cold-start | FR-4.1, FR-4.3 | Recommend |
| T6 Filter bubble | FR-4.5 | Recommend |
| T7 Roommate | FR-5.1 – FR-5.6 | Matching |
| T8 RAG hallucination | FR-6.2 | Chatbot |
| T9 Multi-turn | FR-6.3 | Chatbot |
| T10 Risk detection | FR-7.1 | Risk |
| T11 Freshness | FR-2.8, FR-3.7, NFR-4 | Crawler |
