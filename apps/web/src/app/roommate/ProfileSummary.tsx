import * as L from "./labels";
import type { DeckProfile } from "./types";

// Phần thân thẻ hồ sơ (tầng T1, ẩn danh) — dùng chung cho Bộ thẻ và trang chấm
// điểm /roommate/rate. Hai nơi PHẢI hiện cùng một lượng thông tin: chấm điểm
// trên thẻ khác với thẻ đã quẹt thì hai số liệu không so được với nhau.
export function ProfileHeader({ p, isSimulated }: { p: DeckProfile | null; isSimulated: boolean }) {
  return (
    <div>
      {/* KHÔNG ảnh chân dung — quẹt trên LỐI SỐNG, không trên ngoại hình. */}
      <h3 className="font-bold text-ink">{p?.name || "Sinh viên CTU"}</h3>
      <p className="text-sm text-ink-muted">
        {p?.gender === "nam" ? "Nam" : p?.gender === "nu" ? "Nữ" : "—"}
        {p?.don_vi ? ` · ${p.don_vi}` : ""}
      </p>
      {isSimulated && (
        // Nhãn bắt buộc: hồ sơ mô phỏng bị loại khỏi mọi số liệu đánh giá
        <span className="mt-1 inline-block rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
          hồ sơ mô phỏng
        </span>
      )}
    </div>
  );
}

export function ProfileFacts({ p }: { p: DeckProfile | null }) {
  return (
    <>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <Row k="Giờ ngủ" v={L.at(L.SLEEP, p?.sleep_time)} />
        <Row k="Rửa chén" v={L.at(L.CLEAN, p?.cleanliness)} />
        <Row k="Chịu ồn" v={L.at(L.NOISE, p?.noise_tolerance)} />
        <Row k="Máy lạnh" v={L.at(L.AC, p?.ac_usage)} />
        <Row k="Ngân sách" v={L.at(L.BUDGET, p?.budget_band)} />
        <Row k="Dự định ở" v={L.at(L.SCENARIO, p?.scenario)} />
      </dl>
      {p?.bio && <p className="rounded-lg bg-tint px-3 py-2 text-sm italic text-ink-soft">“{p.bio}”</p>}
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="text-ink-faint">{k}</dt>
      <dd className="font-medium text-ink-soft">{v}</dd>
    </>
  );
}
