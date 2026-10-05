# 📎 BỔ SUNG THUYẾT MINH — Phần Khoa học

**Đề tài:** Hệ thống tổng hợp & gợi ý nhà trọ AI hỗ trợ SV ĐH Cần Thơ — THS2026-66
**Mục đích:** Bổ sung/sửa các mục yếu trong `Thuyết minh.md` (OCR gốc vỡ định dạng). Dùng nội dung dưới để cập nhật bản .docx gốc trước khi nộp.

---

## SỬA MỤC 10.2 + 10.3 — TÀI LIỆU THAM KHẢO KHOA HỌC

Bản gốc chỉ trích báo chí ([3][4][8][9]). Bổ sung references học thuật (Scopus/ISI/hội nghị) cho từng kỹ thuật lõi:

**Recommendation / Cold Start / Diversity:**
- [R1] Zhang, S. et al. (2021). *A Survey of Cold-Start Problem in Collaborative Filtering Recommendation Systems.* — nền tảng giải bài toán T5.
- [R2] Ziegler, C. et al. (2005). *Improving Recommendation Lists Through Topic Diversification.* WWW. — Intra-List Similarity (ILS), giải T6.
- [R3] Sutton & Barto (2018). *Reinforcement Learning: An Introduction* (ε-greedy). — exploration/exploitation T6.

**RAG / Chatbot:**
- [R4] Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS. — kiến trúc RAG, giải T8.
- [R5] Es, S. et al. (2024). *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* EACL. — đo Faithfulness, Answer Relevancy.
- [R6] Wang, L. et al. (2024). *Multilingual E5 Text Embeddings.* — model embedding tiếng Việt.

**Data Engineering:**
- [R7] Broder, A. (1997). *On the Resemblance and Containment of Documents* (MinHash). — dedup T4.
- [R8] Indyk & Motwani (1998). *Approximate Nearest Neighbors: Towards Removing the Curse of Dimensionality* (LSH). STOC. — T4.
- [R9] Liu, F.T. et al. (2008). *Isolation Forest.* ICDM. — phát hiện bất thường giá, T10.

**Spatial / Geocoding:**
- [R10] OpenStreetMap Foundation. *Overpass API & Nominatim Documentation.* — POI + geocoding miễn phí, T2,T3.
- [R11] (Bổ sung 1 bài tạp chí KH ĐH CTU/ĐH BKHN về xử lý địa chỉ tiếng Việt — tra cứu trước khi nộp.)

**Ghép bạn ở — Reciprocal Recommender (T7):**
- [R12] Pizzato, L., Rej, T., Chung, T., Koprinska, I., Kay, J. (2010). *RECON: A Reciprocal Recommender for Online Dating.* ACM RecSys. — điểm tương thích hai chiều, gộp bằng harmonic mean.
- [R13] Palomares, I., Porcel, C., Pizzato, L., Guy, I., Herrera-Viedma, E. (2021). *Reciprocal Recommender Systems: Analysis of State-of-Art Literature, Challenges and Opportunities towards Social Recommendation.* Information Fusion, 69, 103–127. — tổng quan RRS; lọc reciprocal khi dựng deck.
- [R14] Gower, J.C. (1971). *A General Coefficient of Similarity and Some of Its Properties.* Biometrics, 27(4), 857–871. — độ tương đồng trên dữ liệu trộn kiểu (thứ bậc / nhị phân / tập hợp), xử lý thiếu dữ liệu.
- [R15] Yang, C. et al. (2024). *Revisiting Reciprocal Recommender Systems: Metrics, Formulation, and Method.* arXiv:2408.09748. — metric đánh giá RRS.
- [R16] Tomita, Y. et al. (2024). *Fair Reciprocal Recommendation in Matching Markets.* ACM RecSys. — congestion / công bằng exposure (đo bằng Gini, notebook 06 mục 8).
- [R17] Irving, R.W. (1985). *An Efficient Algorithm for the "Stable Roommates" Problem.* Journal of Algorithms, 6(4), 577–595. — ghép ổn định không hai phía, có thể vô nghiệm.
- [R18] *(Weighted Gower distance — BMC Medical Research Methodology, 2024.)* — trọng số cho từng chiều của Gower. **Tra cứu tên tác giả + tiêu đề đầy đủ trước khi nộp.**

> R15, R16: đối chiếu lại danh sách tác giả trên trang bài báo trước khi đưa vào .docx.

> Ghi chú: đánh số lại liên tục với references báo chí gốc khi gộp vào .docx.

---

## SỬA MỤC 12.2 — MỤC TIÊU CỤ THỂ (định lượng)

Thay mục tiêu mơ hồ bằng mục tiêu đo được:

1. Khảo sát ≥150 SV CTU, phân tích thống kê tiêu chí chọn trọ & khó khăn.
2. Crawl ≥3000 listing **unique** từ ≥3 nguồn; dedup MinHash recall ≥90%.
3. Geocoding pipeline 3 tầng đạt confidence ≥medium cho ≥80% listing.
4. Recommendation: **Precision@10 ≥0.6, NDCG@10 ≥0.65, ILS ≤0.7**.
5. Roommate Matching: **MAE feedback sau 2 tuần ≤1.5/5**.
6. Chatbot RAG: **Faithfulness ≥0.7, Answer Relevancy ≥0.75** (RAGAS).
7. Risk Detection: **recall ≥85%** trên 100 tin lừa đảo gán nhãn.

---

## SỬA MỤC 15.1 — NỘI DUNG NGHIÊN CỨU (gắn kỹ thuật)

6 phần gốc giữ nguyên khung, bổ sung kỹ thuật & metric cho từng phần:

| Phần | Nội dung | Kỹ thuật chính | Metric |
|---|---|---|---|
| 1 | Khảo sát nhu cầu | Thống kê mô tả (pandas) | N≥150 |
| 2 | Xây dựng nền tảng web | Next.js + Node + FastAPI + PG/PostGIS/pgvector | — |
| 3 | Data pipeline | Scrapy + NLP + MinHash/LSH + IsolationForest | dedup ≥90%, risk ≥85% |
| 4 | Recommendation + Matching | Content-Based Cosine, ε-greedy, Weighted Cosine | P@10 ≥0.6, MAE ≤1.5 |
| 5 | Spatial + Chatbot | PostGIS, Geocode 3 tầng, RAG + e5 + Gemini | geocode ≥80%, RAGAS ≥0.7 |
| 6 | Kiểm thử + triển khai | Unit test, OWASP ZAP, SUS | coverage ≥60% |

---

## SỬA MỤC 17 — SẢN PHẨM KHCN (thêm metric)

Bản gốc chỉ ghi "01 Ứng dụng Web AI". Bổ sung:

| # | Sản phẩm | Chỉ tiêu định lượng |
|---|---|---|
| 3.1 | Web app AI hỗ trợ tìm trọ | Live + ≥3000 listing + 4 module AI đạt ngưỡng metric mục 12.2 |
| 3.2 | Bộ dữ liệu nhà trọ Cần Thơ đã làm sạch | ≥3000 records, có nhãn risk/freshness |
| 3.3 | Báo cáo đánh giá thực nghiệm (notebook) | Precision@K, NDCG, RAGAS, ILS |

---

## RỦI RO TOP 3 (bổ sung mục rủi ro)

| Rủi ro | Xác suất | Giảm thiểu |
|---|---|---|
| Nguồn crawl bị block | Cao | Plugin JSON + 2 nguồn dự phòng + manual seed 500 tin |
| Geocode hẻm Cần Thơ kém | Cao | Pipeline 3 tầng + ward centroid + badge ước lượng |
| Hết quota Gemini API | TB | Fallback Llama 3.1 8B local (Ollama) |

> Chi tiết kỹ thuật: `Technical_Roadmap.md`. Tiến độ: `Sprint_Plan.md`.
