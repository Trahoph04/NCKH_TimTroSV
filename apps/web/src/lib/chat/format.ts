// Helper hiển thị cho chat.
import type { Conversation, ListingSnapshot, RoommateProfile } from "./types";

export function initials(name: string | null | undefined): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const pad = (n: number) => String(n).padStart(2, "0");

export function timeHM(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (sameDay(d, now)) return "Hôm nay";
  if (sameDay(d, y)) return "Hôm qua";
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}${d.getFullYear() !== now.getFullYear() ? `/${d.getFullYear()}` : ""}`;
}

/** Thời gian ngắn ở danh sách hội thoại: 14:31 · Hôm qua · 28/09 */
export function listTime(iso: string): string {
  const d = new Date(iso);
  return sameDay(d, new Date()) ? timeHM(iso) : dayLabel(iso);
}

export function lastSeenText(iso: string | null | undefined): string {
  if (!iso) return "Ngoại tuyến";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "Vừa mới hoạt động";
  if (mins < 60) return `Hoạt động ${mins} phút trước`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Hoạt động ${hours} giờ trước`;
  return `Hoạt động ${Math.floor(hours / 24)} ngày trước`;
}

export function scoreText(score: number | null | undefined): string | null {
  if (score == null) return null;
  return `${Math.round(score * 100)}%`;
}

export function previewText(c: Conversation, meId: number): string {
  const m = c.last_message;
  if (!m) return "Hãy chào nhau một câu nhé";
  const mine = m.sender_id === meId ? "Bạn: " : "";
  switch (m.kind) {
    case "system":
      return "Mới ghép đôi — gửi lời chào nào!";
    case "image": {
      const n = (m.payload as { images?: unknown[] } | null)?.images?.length ?? 1;
      return `${mine}Đã gửi ${n} ảnh`;
    }
    case "listing":
      return `${mine}Đã chia sẻ tin: ${(m.payload as ListingSnapshot | null)?.title ?? "phòng trọ"}`;
    default:
      return `${mine}${m.body ?? ""}`;
  }
}

export function priceShort(price: number | null | undefined): string {
  if (price == null) return "Thỏa thuận";
  const tr = price / 1_000_000;
  return `${Number.isInteger(tr) ? tr.toFixed(0) : tr.toFixed(1)} triệu`;
}

// Nhãn hồ sơ ở ghép (thang theo migration 30 + form v2).
const SLEEP = ["Ngủ sớm (trước 23h)", "Ngủ khoảng 23h–0h", "Cú đêm (sau 0h)"];
const BUDGET = ["Dưới 1 triệu", "1–1,5 triệu", "1,5–2 triệu", "2–3 triệu", "Trên 3 triệu"];

export function profileRows(p: RoommateProfile | null): { k: string; v: string }[] {
  if (!p) return [];
  const rows: { k: string; v: string }[] = [];
  if (p.sleep_time != null) rows.push({ k: "Giờ ngủ", v: SLEEP[p.sleep_time] ?? "—" });
  if (p.cleanliness != null) rows.push({ k: "Sạch sẽ", v: `${p.cleanliness}/5` });
  if (p.noise_tolerance != null) rows.push({ k: "Chịu ồn", v: `${p.noise_tolerance}/5` });
  if (p.smoke != null)
    rows.push({ k: "Hút thuốc", v: p.smoke ? (p.smoke_in_room ? "Có, trong phòng" : "Có, ra ngoài") : "Không" });
  if (p.budget_band != null) rows.push({ k: "Ngân sách/người", v: BUDGET[p.budget_band] ?? "—" });
  return rows;
}

export function profileChips(p: RoommateProfile): string[] {
  const chips: string[] = [];
  if (p.sleep_time != null) chips.push(["Ngủ sớm", "Ngủ 23h–0h", "Cú đêm"][p.sleep_time] ?? "");
  if (p.cleanliness != null) chips.push(`Sạch sẽ ${p.cleanliness}/5`);
  if (p.smoke === false) chips.push("Không hút thuốc");
  if (p.budget_band != null) chips.push(BUDGET[p.budget_band] ?? "");
  return chips.filter(Boolean);
}
