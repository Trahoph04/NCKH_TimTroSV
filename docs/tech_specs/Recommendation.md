# Gợi ý nhà trọ — as-built (07/10/2026)

Thiết kế `docs/specs/Recommendation.md` · quyết định ADR-021 · notebook `eval/notebooks/01_recommendation_eval.ipynb`.

## 1. Thành phần

| Phần | File |
|---|---|
| Lõi thuần (lọc + nới, MAUT, MMR, ILS, 2 hệ đối chứng, giải thích) | `apps/api/app/recommend/core.py` |
| Đọc danh mục (cache 60 s, đếm chợ/siêu thị 500 m), prefill, lượt đánh giá mù | `apps/api/app/recommend/repo.py` |
| API `/recommend`, `/recommend/prefill`, `/recommend/eval/{session,judge}` | `apps/api/app/recommend/router.py` |
| CSV cho notebook | `recommend/export_snapshot.py`, `recommend/export_judgments.py` |
| Bảng đánh giá mù | `infra/db/migrations/97_rec_eval.sql` |
| Trang `/goi-y` (form + kết quả + "Hệ thống xếp hạng như thế nào?") | `apps/web/src/app/goi-y/` |
| Trang `/goi-y/danh-gia` (thẻ mù, chấm 0–2, tiến độ) | `apps/web/src/app/goi-y/danh-gia/` |
| Cầu nối + notebook | `eval/recommend_lib.py`, `eval/tools/build_nb01.py` |
| Test | `apps/api/tests/test_recommend.py` (16 ca) — toàn bộ 298 passed |

Lối vào: header "Gợi ý", nút ở hero trang chủ.

## 2. Số đo offline (31 bộ tiêu chí khảo sát, khu II, 1.312 tin)

| Hệ | Thoả ràng buộc gốc | ILS@10 | Vị trí khác nhau /10 | Độ phủ |
|---|---|---|---|---|
| **Đề xuất** | 0,92 | **0,28** | **9,9** | 66 |
| B-giá | 1,00 | 0,43 | 9,5 | 20 |
| B-cosine (thiết kế gốc) | 0,35 | 0,34 | 7,2 | 79 |

Không truy vấn nào phải nới. Độ nhạy (Jaccard@10 với top-10 mặc định): trọng số ±20% → 0,90–1,00; θ 0,3/0,7 →
0,78/0,64; λ 0,5/0,9 → 0,61/0,70; co rút 0,3/0,7 → 0,72/0,70; điểm giá tại ngân sách 0,5/0,7 → 0,91/0,87.

## 3. Buổi thử nghiệm 09/10 — kịch bản phần gợi ý (~6 phút/người)

1. SV đăng nhập tab **MSSV** (phiếu in `eval/data/phieu_dang_nhap.html`).
2. Mở `/goi-y/danh-gia` → chọn tiêu chí **như khi tìm phòng thật** → "Bắt đầu đánh giá".
3. Chấm hết ~25–30 thẻ: Không quan tâm / Có thể xem thử / Sẽ liên hệ (được mở "Xem chi tiết").
4. Không giải thích thẻ nào của hệ nào (làm mù). Chờ trang tải xong rồi mới bấm.
5. Sau buổi: `docker compose exec -T api python -m app.recommend.export_judgments > eval/data/rec_judgments.csv`,
   `export_snapshot > eval/data/rec_candidates.csv`, rồi chạy lại notebook 01 (lệnh đầu `build_nb01.py`).

Trước buổi: không chạy crawl/reclassify trong lúc thử nghiệm (danh mục đổi giữa chừng làm 2 người cùng tiêu chí thấy
tin khác nhau); xoá lượt thử của nhóm (`DELETE FROM rec_eval_sessions WHERE user_id IN (...)`).

## 4. Đã kiểm
- API: tiêu chí khảo sát điển hình (2 tr, khu II, ≤ 10′, wifi + WC riêng) → 10 tin, 0,75 s lần đầu, lý do + "hỏi: WC riêng".
- Trình duyệt: `/goi-y` (ngân sách lấy sẵn từ hồ sơ ghép bạn, % giảm dần, lý do ✓, cảnh báo cần hỏi); `/goi-y/danh-gia`
  tạo 29 thẻ, chấm 1 thẻ → 1/29 lưu server (lượt thử đã xoá khỏi DB dev); chưa đăng nhập → chuyển `/login`.
- Notebook 01 chạy hết; mục 5 đang chạy bằng DỮ LIỆU GIẢ có nhãn tới khi có `rec_judgments.csv`.

## 5. Hạn chế (đưa vào báo cáo)
- Chưa có dữ liệu "an ninh khu vực" (61% SV coi trọng) → chưa tính.
- Tiện ích phần lớn "chưa rõ": WC riêng chỉ 2% tin nhắc, wifi 21%, chỗ để xe 5% → không lọc cứng, đẩy thành "nên hỏi".
- Giá tin ở ghép có thể là giá/người; vài tin rất rẻ (≤ 1 tr) được điểm giá tối đa — buổi thử nghiệm sẽ cho biết SV có
  chấm chúng "sẽ liên hệ" không.
- Toạ độ cấp phường; phút đi ORS `driving-car`; khu học offline mặc định khu II.
