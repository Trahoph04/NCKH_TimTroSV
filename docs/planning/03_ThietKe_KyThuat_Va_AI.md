# 📑 TÀI LIỆU 3: THIẾT KẾ KỸ THUẬT VÀ 4 MODULE AI
**Đề tài:** Xây dựng hệ thống tổng hợp và gợi ý nhà trọ ứng dụng AI hỗ trợ sinh viên ĐH Cần Thơ

---

## 1. 🏗️ KIẾN TRÚC VÀ STACK CÔNG NGHỆ ĐỀ XUẤT

*Hệ thống được thiết kế theo kiến trúc Tách biệt Frontend - Backend (Microservices nhẹ).*

- **Frontend (Web Client):** Next.js 14, TailwindCSS, Leaflet.js (Bản đồ tương tác).
- **Backend API (Nghiệp vụ Web):** Node.js + Express (JWT Auth, Quản lý User, Routing).
- **Backend AI & Crawler (Python):** FastAPI (Xử lý thuật toán AI, Scrapy Crawler).
- **Cơ sở dữ liệu:** PostgreSQL kết hợp extension `pgvector` (để lưu trữ vector AI) và `PostGIS` (phân tích dữ liệu không gian OSM).
- **Caching & Real-time:** Redis (Cache kết quả gợi ý, quản lý Session/Socket chat).

---

## 2. 🔬 CHI TIẾT 4 MODULE AI CỐT LÕI

### 🔴 MODULE 1: Data Pipeline & Cảnh Báo Rủi Ro (Risk Detection)
- **Vấn đề:** Dữ liệu crawl về có nhiều tin rác, trùng lặp, giá ảo.
- **Kỹ thuật sử dụng:**
  - **Lọc trùng lặp (Deduplication):** Sử dụng thuật toán `MinHash` và `LSH` để so sánh độ tương đồng của đoạn văn bản mô tả. Nếu giống > 75% ➔ Gộp chung thành 1 tin.
  - **Phát hiện giá bất thường:** Dùng thuật toán `Isolation Forest` học không giám sát. Nếu giá/diện tích quá lệch so với mặt bằng khu vực Ninh Kiều ➔ Cắm cờ "Bất thường".
  - **Rule-based:** Chấm điểm rủi ro nếu (1) Không có ảnh, (2) Nhắc đến "đặt cọc trước khi xem phòng".

### 🟠 MODULE 2: Gợi Ý Nhà Trọ (Housing Recommendation)
> **07/10/2026: thiết kế cosine dưới đây đã được thay** bằng knowledge-based (lọc + MAUT + MMR) — số đo bác cosine
> và thiết kế mới ở `docs/specs/Recommendation.md`, ADR-021. Giữ nguyên đoạn dưới làm lịch sử.
- **Vấn đề:** Trả về danh sách nhà trọ phù hợp nhất với túi tiền, sở thích và nhu cầu an sinh của sinh viên.
- **Kỹ thuật sử dụng:** `Content-Based Filtering` kết hợp `Cosine Similarity` và `Spatial Analysis` (Phân tích không gian).
- **Cách hoạt động:**
  - Build Vector Sinh Viên: `[Ngân_sách, Khoảng_cách_mong_muốn, Wi-fi, Ưu_tiên_gần_công_an, Ưu_tiên_gần_bến_xe_buýt...]`
  - Build Vector Phòng Trọ: `[Giá_thực_tế, Khoảng_cách_thực_tế, Có_Wifi, Khoảng_cách_đến_công_an, Khoảng_cách_đến_bến_xe_buýt...]`
  - Tính khoảng cách Cosine giữa 2 vector, sắp xếp top K (K=10) có độ tương đồng lớn nhất để gợi ý.
- **Đánh giá thuật toán:** Đo lường bằng chỉ số `Precision@K` và `NDCG@K`.

### 🟡 MODULE 3: Tương Thích Bạn Ở Ghép (Roommate Matching)
- **Vấn đề:** Sinh viên cần tìm bạn ở ghép hòa hợp về lối sống để tránh xung đột.
- **Kỹ thuật sử dụng:** `Weighted Cosine Similarity` (Tương đồng Cosine có trọng số).
- **Cách hoạt động:** 
  - Khảo sát các thông số (Trọng số tương ứng): Ngân sách (25%), Giờ ngủ (20%), Hút thuốc (15%), Mức độ dọn dẹp (15%), Ngành học (10%).
  - Tính điểm Matching Score từ 0.0 đến 1.0 giữa 2 sinh viên bất kỳ. Trên 0.7 ➔ Đề xuất kết nối.

### 🟢 MODULE 4: Chatbot Trợ Lý Ảo LLM (RAG Pipeline)
- **Vấn đề:** Sinh viên không thích tự click tìm kiếm, họ thích "nhắn tin hỏi luôn" (VD: "Có phòng nào 1 triệu ở hẻm 51 không?"). Nếu dùng ChatGPT bình thường thì nó sẽ bịa ra dữ liệu (Hallucination).
- **Kỹ thuật sử dụng:** Mô hình `RAG` (Retrieval-Augmented Generation).
- **Cách hoạt động:**
  - **B1 (Indexing):** Lấy tất cả tin phòng trọ đang "Active", dùng model `multilingual-e5-small` nhúng thành Vector (Embedding), lưu vào `pgvector`.
  - **B2 (Retrieval):** Khi SV đặt câu hỏi, AI nhúng câu hỏi đó, tìm 5 phòng trọ sát nghĩa nhất trong database.
  - **B3 (Generation):** Bơm 5 phòng trọ đó (kèm các chỉ số an sinh không gian: khoảng cách đồn công an, siêu thị) vào Prompt (Ngữ cảnh), đưa cho LLM (`Google Gemini 1.5 Flash` qua API). Gemini sẽ tổng hợp và trả lời sinh viên bằng ngôn ngữ tự nhiên.
- **Đánh giá chatbot:** Sử dụng framework `RAGAS` với các chỉ số `Faithfulness` (Độ trung thực) và `Answer Relevancy` (Đúng trọng tâm).
