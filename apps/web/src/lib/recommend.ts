import type { ListingOut } from "./api";

// Khớp apps/api/app/recommend/core.py (SURVEY_TOP3, AMENITY_LABELS) và câu C1/C4/C5 của khảo sát.
export const BUDGET_OPTIONS = [
  { value: 1_500_000, label: "Dưới 1,5 tr" },
  { value: 2_000_000, label: "1,5 – 2 tr" },
  { value: 2_500_000, label: "2 – 2,5 tr" },
  { value: 3_500_000, label: "2,5 – 3,5 tr" },
  { value: 4_500_000, label: "Trên 3,5 tr" },
];
export const COMMUTE_OPTIONS = [
  { value: 5, label: "Dưới 5 phút" },
  { value: 10, label: "5–10 phút" },
  { value: 15, label: "10–15 phút" },
  { value: 20, label: "15–20 phút" },
  { value: 30, label: "Trên 20 phút nếu rẻ" },
];
export const CAMPUS_OPTIONS = ["Khu I", "Khu II", "Khu III"];
export const HOUSING_OPTIONS = [
  { value: "", label: "Tất cả" },
  { value: "phong_tro", label: "Phòng trọ" },
  { value: "nha_mini", label: "Nhà mini" },
];
export const AMENITY_OPTIONS = [
  { value: "wifi", label: "Wifi" },
  { value: "private_wc", label: "WC riêng" },
  { value: "free_hours", label: "Giờ giấc tự do" },
  { value: "parking", label: "Chỗ để xe" },
  { value: "kitchen", label: "Được nấu ăn" },
  { value: "air_conditioner", label: "Máy lạnh" },
  { value: "fridge", label: "Tủ lạnh" },
  { value: "washing_machine", label: "Máy giặt" },
];
// "An ninh khu vực" có trong khảo sát nhưng chưa có dữ liệu → không đưa vào (docs/specs/Recommendation.md)
export const FACTOR_OPTIONS = [
  { value: "gia", label: "Giá thuê rẻ" },
  { value: "gan_truong", label: "Gần trường" },
  { value: "gio_tu_do", label: "Giờ giấc tự do" },
  { value: "tien_nghi", label: "Tiện nghi" },
  { value: "cho_de_xe", label: "Chỗ để xe" },
  { value: "gan_cho", label: "Gần chợ, quán ăn" },
];

export type Criteria = {
  budget: number;
  campus: number;
  max_minutes: number;
  housing: string; // "" = cả hai
  required: string[];
  top_factors: string[];
  gender?: string | null;
};

export const DEFAULT_CRITERIA: Criteria = {
  budget: 2_000_000,
  campus: 1,
  max_minutes: 10,
  housing: "",
  required: [],
  top_factors: [],
};

// Bỏ housing rỗng: API dùng enum, chuỗi rỗng sẽ bị 422.
export function toPayload(c: Criteria) {
  const { housing, gender, ...rest } = c;
  return { ...rest, ...(housing ? { housing } : {}), ...(gender ? { gender } : {}) };
}

export type RecommendItem = { listing: ListingOut; match: number; reasons: string[]; ask: string[] };
export type RecommendResult = {
  items: RecommendItem[];
  relaxed: string[];
  candidates: number;
  weights: Record<string, number>;
  algo_ver: string;
};

export type EvalCard = { card_code: string; listing: ListingOut; minutes: number | null; relevance: number | null };
export type EvalSession = {
  session_id: number;
  campus: number;
  cards: EvalCard[];
  judged: number;
  completed: boolean;
};
