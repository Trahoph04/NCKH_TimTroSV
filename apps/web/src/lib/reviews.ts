// Đánh giá nhà trọ của SV — key tag khớp apps/api/app/reviews/schemas.py (đổi thì đổi cả hai nơi).
// Tag tiêu cực là cảnh báo do người đã ở/đi xem báo lại (thuyết minh 14.2), không có mô hình AI chấm (ADR-024).
export const REVIEW_TAGS: { key: string; label: string; negative: boolean }[] = [
  { key: "dung_mo_ta", label: "Đúng như tin đăng", negative: false },
  { key: "chu_tot", label: "Chủ trọ tốt", negative: false },
  { key: "sach_se", label: "Sạch sẽ", negative: false },
  { key: "yen_tinh", label: "Yên tĩnh", negative: false },
  { key: "an_ninh_tot", label: "An ninh tốt", negative: false },
  { key: "coc_khong_tra", label: "Giữ cọc không trả", negative: true },
  { key: "gia_khong_dung", label: "Giá khác tin đăng", negative: true },
  { key: "dien_nuoc_cao", label: "Điện nước tính giá cao", negative: true },
  { key: "an_ninh_kem", label: "An ninh kém", negative: true },
  { key: "on_ao", label: "Ồn ào", negative: true },
  { key: "ngap_nuoc", label: "Hay ngập nước", negative: true },
  { key: "chu_kho_chiu", label: "Chủ trọ khó tính", negative: true },
];
export const TAG_LABEL: Record<string, string> = Object.fromEntries(REVIEW_TAGS.map((t) => [t.key, t.label]));
export const NEGATIVE_TAGS = new Set(REVIEW_TAGS.filter((t) => t.negative).map((t) => t.key));

export const RELATIONS: { key: string; label: string }[] = [
  { key: "dang_o", label: "Đang ở" },
  { key: "da_o", label: "Đã từng ở" },
  { key: "da_xem", label: "Đã đi xem phòng" },
];
export const RELATION_LABEL: Record<string, string> = Object.fromEntries(RELATIONS.map((r) => [r.key, r.label]));

// Cảnh báo ở trang chi tiết khi ít nhất ngần này người cùng báo một tag tiêu cực — 1 người thì có thể là ác ý/hiểu lầm
export const WARN_MIN_REPORTS = 2;

export type Review = {
  id: number;
  listing_id: number;
  rating: number;
  tags: string[];
  content: string | null;
  relation: string | null;
  author: string;
  status: string;
  created_at: string;
  updated_at: string | null;
};
export type ReviewSummary = {
  average: number | null;
  total: number;
  rating_counts: Record<string, number>;
  tag_counts: Record<string, number>;
};
export type ReviewList = { summary: ReviewSummary; items: Review[]; page: number; size: number };

// "4,2" — dấu phẩy thập phân kiểu Việt
export function formatRating(avg: number): string {
  return avg.toFixed(1).replace(".", ",");
}
