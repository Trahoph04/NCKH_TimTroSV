"use client";

import { useState } from "react";
import * as L from "./labels";
import type { Profile } from "./types";

/** 12 câu của form v2. Lưu xong trả LUÔN top-3 (thưởng tức thì) — xem
 *  POST /matching/profile trong apps/api/app/matching/router.py. */
export default function ProfileForm({
  initial,
  options,
  onSaved,
}: {
  initial: Profile | null;
  options: { hanh_vi: string[]; deal_breakers: string[] };
  onSaved: () => void;
}) {
  const [f, setF] = useState<Partial<Profile>>(initial ?? {});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setF((p) => ({ ...p, [k]: v }));
  const toggle = (k: "hanh_vi" | "deal_breakers", v: string) =>
    setF((p) => {
      const cur = p[k] ?? [];
      return { ...p, [k]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] };
    });

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const res = await fetch("/api/matching/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(f),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        // 422 từ pydantic có detail là array — ép về chuỗi đọc được
        setErr(typeof d.detail === "string" ? d.detail : "Hồ sơ có trường không hợp lệ");
        return;
      }
      onSaved();
    } catch {
      setErr("Không kết nối được máy chủ");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-5">
      <header>
        <h1 className="text-xl font-extrabold text-ink">Hồ sơ ở ghép</h1>
        <p className="mt-1 text-sm text-ink-muted">
          12 câu bấm chọn, khoảng 90 giây. Xong là thấy ngay gợi ý. Người khác chỉ
          thấy <strong>tên gọi và tóm tắt thói quen</strong> của bạn — không thấy MSSV
          hay thông tin liên hệ.
        </p>
      </header>

      {/* Giới tính là LỌC CỨNG tuyệt đối (chỉ ghép cùng giới) nên phải nói rõ
          hệ quả của việc không khai, thay vì để người dùng thắc mắc sao không
          có gợi ý nào. */}
      <Field label="Giới tính của bạn" note="Hệ thống chỉ ghép cùng giới. Không khai thì chưa vào được danh sách ghép.">
        <Radios
          value={f.gender ?? null}
          options={[
            ["nam", "Nam"],
            ["nu", "Nữ"],
          ]}
          onChange={(v) => set("gender", v)}
        />
      </Field>

      <Field label="Trường / Khoa / Viện">
        <select
          className="w-full rounded-lg border border-line px-3 py-2 text-sm"
          value={f.don_vi ?? ""}
          onChange={(e) => set("don_vi", e.target.value || null)}
        >
          <option value="">— chọn —</option>
          {L.DON_VI.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </Field>

      <Scale label="Ngân sách thuê phòng mỗi tháng" labels={L.BUDGET} from={0}
             value={f.budget_band ?? null} onChange={(v) => set("budget_band", v)} />
      <Scale label="Bạn dự định ở như thế nào?" labels={L.SCENARIO.slice(1)} from={1}
             value={f.scenario ?? null} onChange={(v) => set("scenario", v)} />
      <Scale label="Ngày thường bạn đi ngủ lúc mấy giờ?" labels={L.SLEEP} from={0}
             value={f.sleep_time ?? null} onChange={(v) => set("sleep_time", v)} />
      <Scale label="Chén bát sau khi ăn xong, bạn thường:" labels={L.CLEAN.slice(1)} from={1}
             value={f.cleanliness ?? null} onChange={(v) => set("cleanliness", v)} />
      <Scale label="Bạn cùng phòng bật nhạc lúc 23h. Bạn sẽ:" labels={L.NOISE.slice(1)} from={1}
             value={f.noise_tolerance ?? null} onChange={(v) => set("noise_tolerance", v)} />
      <Scale label="Tiền điện máy lạnh — bạn thuộc kiểu nào?" labels={L.AC} from={0}
             value={f.ac_usage ?? null} onChange={(v) => set("ac_usage", v)} />
      <Scale label="Chuyện tiền nong khi ở chung:" labels={L.MONEY.slice(1)} from={1}
             value={f.money_style ?? null} onChange={(v) => set("money_style", v)} />

      <Field label="Về thuốc lá">
        <Radios
          value={f.smoke === null || f.smoke === undefined ? null : f.smoke ? (f.smoke_in_room ? "in" : "out") : "no"}
          options={[
            ["no", "Mình không hút"],
            ["out", "Mình có hút nhưng ra ngoài hút"],
            ["in", "Mình hút và cần hút trong phòng"],
          ]}
          onChange={(v) => {
            // smoke và smoke_in_room là HAI cột: chỉ mức "hút trong phòng" mới
            // đụng deal-breaker. Gộp thành một cờ là loại oan người ra ngoài hút.
            set("smoke", v !== "no");
            set("smoke_in_room", v === "in");
          }}
        />
      </Field>

      <Field label="Bạn giống người nào hơn?">
        <Radios
          value={f.persona ?? null}
          options={[["A", `An — ${L.PERSONA.A}`], ["B", `Bình — ${L.PERSONA.B}`]]}
          onChange={(v) => set("persona", v)}
        />
      </Field>

      <Field label="Những điều nào ĐÚNG với bạn?" note="Chọn tất cả những điều đúng. Người được ghép sẽ thấy phần này.">
        <Checks items={options.hanh_vi} selected={f.hanh_vi ?? []} onToggle={(v) => toggle("hanh_vi", v)} />
      </Field>

      <Field
        label="Điều bạn KHÔNG chấp nhận được ở người ở ghép"
        note="Hút thuốc trong phòng và ở bẩn sẽ LOẠI HẲN những người đó khỏi danh sách của bạn. Các điều còn lại không loại, nhưng sẽ hiện cảnh báo rõ trên thẻ và hạ điểm mạnh."
      >
        <Checks items={options.deal_breakers} selected={f.deal_breakers ?? []} onToggle={(v) => toggle("deal_breakers", v)} />
      </Field>

      <Field label="Một câu giới thiệu (không bắt buộc)">
        <textarea
          className="w-full rounded-lg border border-line px-3 py-2 text-sm"
          rows={3}
          maxLength={500}
          value={f.bio ?? ""}
          placeholder="VD: Cần yên tĩnh để học bài, hay nấu ăn ở nhà."
          onChange={(e) => set("bio", e.target.value || null)}
        />
      </Field>

      {err && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}

      <button
        onClick={save}
        disabled={saving}
        className="w-full rounded-xl bg-primary py-3 font-semibold text-white transition hover:bg-primary-bright disabled:opacity-50"
      >
        {saving ? "Đang lưu…" : "Lưu hồ sơ và xem gợi ý"}
      </button>
    </div>
  );
}

function Field({ label, note, children }: { label: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-ink">{label}</label>
      {note && <p className="text-xs text-ink-muted">{note}</p>}
      {children}
    </div>
  );
}

function Radios({
  value, options, onChange,
}: { value: string | null; options: [string, string][]; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`block w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
            value === v ? "border-primary bg-primary-soft font-semibold text-primary" : "border-line hover:border-primary-ring"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Scale({
  label, labels, from, value, onChange,
}: { label: string; labels: string[]; from: number; value: number | null; onChange: (v: number) => void }) {
  return (
    <Field label={label}>
      <div className="space-y-1.5">
        {labels.map((t, i) => {
          const v = from + i;
          return (
            <button
              key={v}
              type="button"
              onClick={() => onChange(v)}
              className={`block w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                value === v ? "border-primary bg-primary-soft font-semibold text-primary" : "border-line hover:border-primary-ring"
              }`}
            >
              {t}
            </button>
          );
        })}
      </div>
    </Field>
  );
}

function Checks({
  items, selected, onToggle,
}: { items: string[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <button
          key={it}
          type="button"
          onClick={() => onToggle(it)}
          className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
            selected.includes(it) ? "border-primary bg-primary-soft text-primary" : "border-line hover:border-primary-ring"
          }`}
        >
          <span className="mt-0.5 shrink-0">{selected.includes(it) ? "☑" : "☐"}</span>
          <span>{it}</span>
        </button>
      ))}
    </div>
  );
}
