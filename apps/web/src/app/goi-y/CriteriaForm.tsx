"use client";

import { useEffect, useState } from "react";
import {
  AMENITY_OPTIONS,
  BUDGET_OPTIONS,
  CAMPUS_OPTIONS,
  COMMUTE_OPTIONS,
  DEFAULT_CRITERIA,
  FACTOR_OPTIONS,
  HOUSING_OPTIONS,
  type Criteria,
} from "@/lib/recommend";

const sectionLabel = "text-[13px] font-semibold uppercase tracking-[.05em] text-ink-muted";

function chip(active: boolean, disabled = false): string {
  return `rounded-[9px] border px-3 py-2 text-[13.5px] transition ${
    active
      ? "border-primary bg-primary-soft font-semibold text-primary"
      : disabled
        ? "cursor-not-allowed border-line text-ink-faint"
        : "border-line text-ink-soft hover:border-primary-ring"
  }`;
}

// Câu hỏi giữ đúng thứ tự + cách hỏi của khảo sát (C1, A4, C4, C5, top-3) để tiêu chí người dùng nhập và
// tiêu chí trong khảo sát (dùng sinh trọng số) cùng một nghĩa.
export default function CriteriaForm({
  submitLabel,
  busy,
  onSubmit,
}: {
  submitLabel: string;
  busy: boolean;
  onSubmit: (c: Criteria) => void;
}) {
  const [c, setC] = useState<Criteria>(DEFAULT_CRITERIA);
  const [prefilled, setPrefilled] = useState(false);

  // Đã điền hồ sơ ghép bạn → lấy sẵn ngân sách + giới tính (lọc tin "chỉ nam/chỉ nữ"). Chưa đăng nhập: 401, bỏ qua.
  useEffect(() => {
    fetch("/api/recommend/prefill", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p: { budget?: number | null; gender?: string | null } | null) => {
        if (!p) return;
        setC((cur) => ({ ...cur, budget: p.budget ?? cur.budget, gender: p.gender ?? null }));
        if (p.budget) setPrefilled(true);
      })
      .catch(() => {});
  }, []);

  function toggle(key: "required" | "top_factors", value: string, max?: number) {
    setC((cur) => {
      const list = cur[key];
      if (list.includes(value)) return { ...cur, [key]: list.filter((v) => v !== value) };
      if (max && list.length >= max) return cur;
      return { ...cur, [key]: [...list, value] };
    });
  }

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(c);
      }}
    >
      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Ngân sách / tháng (chưa điện nước)</span>
        <div className="flex flex-wrap gap-2">
          {BUDGET_OPTIONS.map((o) => (
            <button key={o.value} type="button" onClick={() => setC({ ...c, budget: o.value })} className={chip(c.budget === o.value)}>
              {o.label}
            </button>
          ))}
        </div>
        {prefilled && <span className="text-xs text-ink-faint">Lấy từ hồ sơ ghép bạn của bạn — đổi được.</span>}
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Bạn học chủ yếu ở</span>
        <div className="flex gap-1.5 rounded-[11px] bg-tint p-1">
          {CAMPUS_OPTIONS.map((label, i) => (
            <button
              key={label}
              type="button"
              onClick={() => setC({ ...c, campus: i })}
              className={`flex-1 rounded-lg py-2 text-sm transition ${
                c.campus === i ? "bg-primary font-semibold text-white" : "text-ink-soft hover:bg-white/70"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Đi xe máy tới trường tối đa</span>
        <div className="flex flex-wrap gap-2">
          {COMMUTE_OPTIONS.map((o) => (
            <button key={o.value} type="button" onClick={() => setC({ ...c, max_minutes: o.value })} className={chip(c.max_minutes === o.value)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Loại chỗ ở</span>
        <div className="flex flex-wrap gap-2">
          {HOUSING_OPTIONS.map((o) => (
            <button key={o.value || "all"} type="button" onClick={() => setC({ ...c, housing: o.value })} className={chip(c.housing === o.value)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Tiện ích bạn cần</span>
        <div className="flex flex-wrap gap-2">
          {AMENITY_OPTIONS.map((o) => (
            <button key={o.value} type="button" onClick={() => toggle("required", o.value)} className={chip(c.required.includes(o.value))}>
              {o.label}
            </button>
          ))}
        </div>
        <span className="text-xs text-ink-faint">
          Nhiều tin không ghi đủ tiện ích, nên hệ thống không loại tin — tin không nhắc sẽ được đánh dấu &ldquo;nên hỏi chủ
          trọ&rdquo;.
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>3 điều bạn quan tâm nhất ({c.top_factors.length}/3)</span>
        <div className="flex flex-wrap gap-2">
          {FACTOR_OPTIONS.map((o) => {
            const on = c.top_factors.includes(o.value);
            const full = !on && c.top_factors.length >= 3;
            return (
              <button
                key={o.value}
                type="button"
                disabled={full}
                onClick={() => toggle("top_factors", o.value, 3)}
                className={chip(on, full)}
              >
                {o.label}
              </button>
            );
          })}
        </div>
        <span className="text-xs text-ink-faint">Bỏ trống thì dùng mức quan tâm trung bình của 31 sinh viên trong khảo sát.</span>
      </div>

      <button
        type="submit"
        disabled={busy}
        className="rounded-[11px] bg-primary py-3 text-[15.5px] font-semibold text-white transition hover:bg-navy disabled:opacity-60"
      >
        {busy ? "Đang tìm…" : submitLabel}
      </button>
    </form>
  );
}
