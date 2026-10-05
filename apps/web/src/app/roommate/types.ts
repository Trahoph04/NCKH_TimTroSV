// Khớp đúng response của apps/api/app/matching/router.py. Giữ ở file riêng để
// khi API đổi shape thì type-check (npm run build) bắt được ngay, không phải
// phát hiện bằng màn hình trắng lúc demo.

export type DeckProfile = {
  user_id: number;
  name: string | null;
  avatar_url: string | null;
  gender: string | null;
  don_vi: string | null;
  bio: string | null;
  sleep_time: number | null;
  cleanliness: number | null;
  noise_tolerance: number | null;
  budget_band: number | null;
  scenario: number | null;
  ac_usage: number | null;
  money_style: number | null;
  hanh_vi: string[] | null;
  persona: string | null;
  is_simulated: boolean;
};

export type DeckItem = {
  user_id: number;
  position: number;
  // null khi deck_mode='random' (buổi thử nghiệm ẩn mọi tín hiệu thuật toán)
  score: number | null;
  reasons: string[];
  caveat: string | null;
  soft_flags: string[];
  is_simulated: boolean;
  profile: DeckProfile | null;
};

export type DeckRes = {
  items: DeckItem[];
  reason: "no_profile" | "profile_incomplete" | "pool_empty" | "deck_done" | null;
  pool_total: number;
  deck_mode?: string;
  weights_ver?: string;
};

export type Profile = {
  user_id: number;
  gender: string | null;
  don_vi: string | null;
  budget_band: number | null;
  scenario: number | null;
  sleep_time: number | null;
  cleanliness: number | null;
  noise_tolerance: number | null;
  ac_usage: number | null;
  money_style: number | null;
  smoke: boolean | null;
  smoke_in_room: boolean | null;
  hanh_vi: string[] | null;
  deal_breakers: string[] | null;
  persona: string | null;
  bio: string | null;
  is_simulated: boolean;
  src: string | null;
};

export type ProfileRes = {
  profile: Profile | null;
  in_pool: boolean;
  options: { hanh_vi: string[]; deal_breakers: string[] };
};

// invite_id/note có khi "thích" này đến từ POST /matching/invite (lời mời kèm lời nhắn)
export type LikeItem = DeckProfile & {
  liked_at?: string;
  passed_at?: string;
  invite_id?: number | null;
  note?: string | null;
};

export type DeckMode = "ranked" | "random";

// GET /matching/rate — KHÔNG có score/arm: người chấm không được biết thẻ nào
// do thuật toán chọn (thiết kế 2.7, chấm làm mù).
export type RateCard = {
  card_code: string;
  position: number;
  rating: number | null;
  is_simulated: boolean;
  profile: DeckProfile | null;
};

export type RateRes = {
  items: RateCard[];
  reason: "no_profile" | "profile_incomplete" | "pool_empty" | null;
  round: number;
  done?: boolean;
};
