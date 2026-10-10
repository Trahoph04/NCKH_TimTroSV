# Gợi ý nhà trọ (FR-4) — knowledge-based + MAUT + MMR

_Lập 07/10/2026 · thay thiết kế "Content-Based Cosine" ở `planning/03_ThietKe_KyThuat_Va_AI.md` mục Module 2 ·
buổi thử nghiệm 09/10 · quyết định: ADR-021_

## Mục tiêu
Sinh viên nhập tiêu chí (ngân sách, khu học, thời gian đi tối đa, tiện ích cần, 3 yếu tố quan trọng nhất) → 10 tin
phù hợp kèm **lý do** và **điều cần hỏi chủ trọ**. Đo được bằng số liệu thật: P@10, NDCG@10 (phán đoán mù của sinh
viên trong buổi thử nghiệm), ILS@10, so với 2 hệ đối chứng.

## Vì sao không theo thiết kế gốc (cosine) — số đo 07/10
- Không có lịch sử tương tác (`user_interactions` = 5 dòng; SV thuê trọ vài năm/lần) ⇒ collaborative filtering và
  content-based "học từ tin đã thích" đều không có dữ liệu. Họ đúng là **knowledge-based recommender** (Burke 2002;
  Felfernig & Burke 2008; Aggarwal 2016 ch. 5) — thiết kế gốc "vector SV vs vector phòng" thực chất là họ này, chỉ sai
  phép đo.
- Cosine đo **hướng**, còn sở thích nhà trọ **đơn điệu** (rẻ hơn / gần hơn là tốt hơn). Trên DB thật, truy vấn
  (2 tr, ≤ 10 phút tới khu II):
  - cosine thô `[giá, phút]`: **100% của 1.312 tin có cos ≥ 0,9999** (giá tính bằng triệu lấn át số phút) — không
    phân biệt được; trong nhóm đó 987 tin vượt ngân sách hoặc vượt 10 phút;
  - bất biến tỉ lệ: cos((2 tr, 10′), (4 tr, 20′)) = 1,0 — phòng gấp đôi giá và gấp đôi đường được điểm tuyệt đối;
  - cosine chuẩn hoá min-max: top-10 có 3 tin vượt ngân sách, 3 tin vượt 10 phút dù **325 tin thoả cả hai**.

## Yêu cầu
- [x] R1 Tầng 1 — lọc cứng: tin đang hiển thị (`visible_clause`), giá ≤ 1,2 × ngân sách, phút ≤ max(1,5 T, T + 5),
      loại chỗ ở (nếu chọn), tin dành riêng giới tính khác (`gender_only`) khi người dùng khai giới tính.
- [x] R2 Tự nới ràng buộc khi < 10 ứng viên (McSherry 2004): thời gian (+5 phút/bậc, tới +20) → giá (×1,35 → ×1,5) →
      bỏ lọc loại chỗ ở; **báo rõ** đã nới gì.
- [x] R3 Tầng 2 — MAUT: U = Σ wₖ·uₖ ∈ [0, 1]; hàm uₖ đơn điệu, bất đối xứng (bảng dưới).
- [x] R4 Trọng số từ khảo sát (31 SV chọn top-3, `eval/data/survey_v2.csv`); cá nhân hoá bằng co rút:
      w = ½·w_khảo_sát + ½·w_bản_thân (đều 1/3 trên 3 yếu tố người dùng tự chọn; không chọn ⇒ w_khảo_sát).
- [x] R5 Thiếu dữ liệu ≠ không có: tiện ích/giờ giấc "tin không nhắc" = **chưa rõ**, nhận θ = 0,5 (trung tính); không bao
      giờ lọc cứng theo tiện ích.
- [x] R6 Tầng 3 — MMR (Carbonell & Goldstein 1998), λ = 0,7: tránh 10 tin dồn 1 điểm phường / tin gần trùng.
      MMR chỉ **chọn tập**; danh sách trả về xếp theo U (thứ tự chọn của MMR làm tin 94% đứng sau 87%).
- [x] R7 Giải thích: 2–3 lý do đóng góp lớn nhất (wₖ·uₖ) + "nên hỏi chủ trọ" cho tiện ích người dùng cần mà tin không
      nhắc + nhãn vị trí tương đối.
- [x] R8 Hai hệ đối chứng chạy cùng đầu vào: **B-giá** (lọc cứng không nới + sắp giá tăng — cách SV đang làm với bộ lọc)
      và **B-cosine** (đúng thiết kế 03: vector chuẩn hoá min-max [giá, phút, tiện ích cần], không lọc).
- [x] R9 `POST /recommend` (public), `GET /recommend/prefill` (đăng nhập — ngân sách từ hồ sơ ghép bạn).
- [x] R10 Đánh giá mù `/goi-y/danh-gia` (đăng nhập): gộp top-10 của 3 hệ, xáo trộn, thẻ giống hệt nhau (không điểm,
      không lý do) → SV chấm 0 "Không quan tâm" / 1 "Có thể xem thử" / 2 "Sẽ liên hệ". Server ghi hệ nào xếp tin đó ở hạng
      mấy; FE không biết.
- [x] R11 Trang `/goi-y` + lối vào ở trang chủ/header; thẻ kết quả có % phù hợp, lý do, điều cần hỏi.
- [x] R12 Notebook 01 dựng lại (sinh từ `eval/tools/build_nb01.py`), gọi đúng hàm sản phẩm: offline trên 31 bộ tiêu chí
      khảo sát + online từ CSV phán đoán (khung + dữ liệu giả ghi nhãn tới khi có buổi 09/10).

## Hàm hữu dụng (B = ngân sách, T = phút tối đa)

| Yếu tố (khảo sát) | top-3 | w gốc | uₖ |
|---|---|---|---|
| Giá thuê rẻ | 20 | 0,270 | p ≤ B: 0,6 + 0,4·(B − p)/(0,5B) (trần 1); B < p ≤ 1,2B: 0,6·(1,2B − p)/(0,2B) |
| Gần trường / đi lại nhanh | 19 | 0,257 | m ≤ 0,5T: 1; ≤ T: 1 − 0,4·(m − 0,5T)/(0,5T); > T: 0,6 giảm tuyến tính về 0 ở mức lọc cứng; thiếu phút: 0,3 |
| Giờ giấc tự do, chủ không ở chung | 15 | 0,203 | tin nói giờ tự do: 1; chưa rõ: θ |
| Tiện nghi (máy lạnh, wifi, WC riêng…) | 13 | 0,176 | có danh sách cần: trung bình {1 nếu tin nhắc, θ nếu không}; không chọn: min(1, số tiện nghi nhắc tới / 3) |
| Có chỗ để xe | 6 | 0,081 | tin nhắc: 1; chưa rõ: θ |
| Gần chợ / quán ăn | 1 | 0,014 | min(1, số chợ + siêu thị/tiện lợi trong 500 m / 3) — bảng `pois` |
| ~~An ninh khu vực~~ | 19 | — | **bỏ**: chưa có nguồn dữ liệu an ninh đáng tin (quyết định 07/10) → hạn chế + hướng phát triển |

Tham số (θ, λ, ngưỡng 0,6 / 1,2B / 1,5T, hệ số co rút ½) là **thiết kế** — notebook kiểm độ nhạy ±20% (Kendall τ top-10).

## Đánh giá
- **Offline** (không cần người): 31 bộ tiêu chí thật (C1 ngân sách, C4 thời gian, C5 tiện ích, top-3) làm truy vấn,
  khu II mặc định (khảo sát không lưu câu khu học). Đo cho cả 3 hệ: tỉ lệ top-10 thoả ràng buộc gốc, ILS@10, số điểm vị
  trí khác nhau trong top-10, độ phủ danh mục, độ nhạy tham số.
- **Online** (09/10): pooling kiểu TREC — mọi tin trong top-10 của bất kỳ hệ nào đều được chấm ⇒ không có tin chưa
  chấm. Mỗi SV × mỗi hệ: P@10 (chặt: rel = 2; lỏng: rel ≥ 1), NDCG@10 (gain 2^rel − 1). So cặp bằng Wilcoxon
  signed-rank; báo N và khoảng tin cậy bootstrap — N nhỏ (~15–20) phải nói rõ.

## Ràng buộc
- Toạ độ đa số tin cấp phường ⇒ "gần chợ" là quanh khu vực; phút tới trường là ORS `driving-car` (xấp xỉ xe máy).
- Thẻ đánh giá mù phải giống hệt nhau giữa các hệ (cùng trường thông tin), không lộ điểm/lý do/hệ.
- Không lưu tiêu chí kèm danh tính ra CSV: export dùng mã người chấm băm.

## Ngoài phạm vi
- Học trọng số từ phản hồi (cần dữ liệu tương tác — sau buổi thử nghiệm).
- ε-greedy (SRS FR-4.5): không có vòng học từ phản hồi nên thăm dò không có tác dụng; đa dạng do MMR đảm nhiệm, đo ILS.
- Popularity fallback (FR-4.3): knowledge-based không có cold-start nên không cần.
