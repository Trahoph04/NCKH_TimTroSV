// Helper format dữ liệu hiển thị — dùng chung cho listing card/detail/map.

export function formatPrice(price: number | null | undefined): string {
  if (price == null) return "Thỏa thuận";
  // dưới 1 triệu: "750 nghìn" — làm tròn 1 chữ số thập phân ra "0.8 triệu" sai lệch với tiêu đề tin
  if (price < 1_000_000) return `${Math.round(price / 1000)} nghìn/tháng`;
  const trieu = price / 1_000_000;
  const formatted = Number.isInteger(trieu) ? trieu.toFixed(0) : trieu.toFixed(1);
  return `${formatted} triệu/tháng`;
}

// Bản ngắn cho card: giá to + hậu tố "/ tháng" tách riêng ở UI.
export function formatPriceShort(price: number | null | undefined): string {
  if (price == null) return "Thỏa thuận";
  if (price < 1_000_000) return `${Math.round(price / 1000)} nghìn`;
  const trieu = price / 1_000_000;
  const formatted = Number.isInteger(trieu) ? trieu.toFixed(0) : trieu.toFixed(1);
  return `${formatted} triệu`;
}

export function formatArea(area: number | null | undefined): string {
  if (area == null) return "";
  return `${area} m²`;
}

export function formatDistance(meters: number | null | undefined): string {
  if (meters == null) return "";
  const km = meters / 1000;
  return `cách CTU ${km.toFixed(1)} km`;
}

export type RiskLevel = "safe" | "caution" | "suspicious" | "unknown";

export const RISK_BADGE: Record<RiskLevel, { label: string; className: string }> = {
  safe: { label: "An toàn", className: "bg-emerald-100 text-emerald-700" },
  caution: { label: "Cẩn trọng", className: "bg-amber-100 text-amber-700" },
  suspicious: { label: "Nghi vấn", className: "bg-rose-100 text-rose-700" },
  unknown: { label: "Chưa rõ", className: "bg-slate-100 text-slate-600" },
};

export function riskBadge(level: string): { label: string; className: string } {
  return RISK_BADGE[level as RiskLevel] ?? RISK_BADGE.unknown;
}

// Nhãn phụ trên card/bản đồ: loại nhà mini + tin pass phòng (điều khoản cọc/hợp đồng do người
// thuê cũ nói, chưa kiểm — gói Chợ Tốt bắt buộc hiện nhãn này).
export function listingTags(listing: {
  listing_type?: string | null;
  offer_kind?: string | null;
}): { label: string; className: string }[] {
  const tags: { label: string; className: string }[] = [];
  if (listing.listing_type === "nha_mini") {
    tags.push({ label: "Nhà mini", className: "bg-sky-100 text-sky-800" });
  }
  if (listing.offer_kind === "lease_transfer") {
    tags.push({ label: "Sang nhượng", className: "bg-amber-100 text-amber-800" });
  }
  return tags;
}

// Vị trí chính xác = người đăng tự ghim / có số nhà và nằm đúng đường / nhóm khảo sát đo tại chỗ (app.cleaner.audit).
// Chưa rà soát (tin user tự đăng: location_precise NULL) → tin theo nhãn geocode.
export function isLocationPrecise(l: { location_precise: boolean | null; geocode_confidence: string | null }): boolean {
  return l.location_precise === true || (l.location_precise == null && l.geocode_confidence === "high");
}

// "0900000001" → "0900 000 001" (dễ đọc khi đọc số qua điện thoại)
export function formatPhone(phone: string): string {
  const d = phone.replace(/\D/g, "");
  return d.length === 10 ? `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}` : phone;
}

const SOURCE_NAMES: Record<string, string> = {
  "nhatot.com": "Chợ Tốt",
  "chotot.com": "Chợ Tốt",
  "phongtro123.com": "Phongtro123",
  "tromoi.com": "Trọ Mới",
  "mogi.vn": "Mogi",
  "bds123.vn": "BDS123",
  "nhadatcantho247.vn": "Nhà đất Cần Thơ 247",
};

// Tên trang nguồn cho nút "Xem tin gốc trên …"
export function sourceName(url: string | null): string {
  if (!url) return "trang nguồn";
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return SOURCE_NAMES[host] ?? host;
  } catch {
    return "trang nguồn";
  }
}
