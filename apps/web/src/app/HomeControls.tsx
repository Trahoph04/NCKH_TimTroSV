"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const DISTRICTS = ["Ninh Kiều", "Bình Thủy", "Cái Răng", "Ô Môn", "Thốt Nốt", "Phong Điền"];

// Backend chưa có filter theo phút đi xe (route_time) — dùng khoảng cách thật
// max_distance_ctu thay cho block "Thời gian tới trường" trong mockup.
const DISTANCE_OPTIONS = [
  { value: "1000", label: "≤ 1 km" },
  { value: "2000", label: "≤ 2 km" },
  { value: "3000", label: "≤ 3 km" },
];

const AREA_OPTIONS = ["15", "20", "25"];

// Khớp HousingType backend (listings/schemas.py). Bỏ trống = cả hai — mặc định hiện cả nhà mini
// vì 41 tin đang thấy được phân loại lại thành nhà mini (docs/specs/Map_MapLibre_POI.md).
export const HOUSING_OPTIONS = [
  { value: "", label: "Tất cả" },
  { value: "phong_tro", label: "Phòng trọ" },
  { value: "nha_mini", label: "Nhà mini" },
];

export const SORT_OPTIONS = [
  { value: "newest", label: "Mới nhất" },
  { value: "price_asc", label: "Giá thấp → cao" },
  { value: "price_desc", label: "Giá cao → thấp" },
  { value: "nearest", label: "Gần CTU nhất" },
  { value: "quality", label: "Chất lượng" },
];

export type HomeParams = {
  q?: string;
  district?: string;
  min_price?: string;
  max_price?: string;
  min_area?: string;
  max_distance_ctu?: string;
  housing?: string;
  sort?: string;
};

function vndToTrieu(vnd: string | undefined): string {
  const n = Number(vnd);
  if (!vnd || !Number.isFinite(n)) return "";
  const trieu = n / 1_000_000;
  return Number.isInteger(trieu) ? String(trieu) : trieu.toFixed(1);
}

function buildParams(values: HomeParams): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value && !(key === "sort" && value === "newest")) params.set(key, value);
  }
  return params;
}

export function HomeFilters({ current }: { current: HomeParams }) {
  const router = useRouter();
  const [minTrieu, setMinTrieu] = useState(vndToTrieu(current.min_price));
  const [maxTrieu, setMaxTrieu] = useState(vndToTrieu(current.max_price));
  const [district, setDistrict] = useState(current.district ?? "");
  const [distance, setDistance] = useState(current.max_distance_ctu ?? "");
  const [minArea, setMinArea] = useState(current.min_area ?? "");
  const [housing, setHousing] = useState(current.housing ?? "");

  function apply() {
    const toVnd = (trieu: string) => {
      const n = Number(trieu);
      return trieu && Number.isFinite(n) && n > 0 ? String(Math.round(n * 1_000_000)) : "";
    };
    const params = buildParams({
      q: current.q,
      sort: current.sort,
      district,
      min_price: toVnd(minTrieu),
      max_price: toVnd(maxTrieu),
      min_area: minArea,
      max_distance_ctu: distance,
      housing,
    });
    router.push(`/?${params.toString()}`);
  }

  const sectionLabel =
    "text-[13px] font-semibold uppercase tracking-[.05em] text-ink-muted";
  const chip = (active: boolean) =>
    `flex-1 rounded-[9px] border py-2 text-center text-[13.5px] transition ${
      active
        ? "border-primary bg-primary-soft font-semibold text-primary"
        : "border-line text-ink-soft hover:border-primary-ring"
    }`;

  return (
    <aside className="flex flex-col gap-6 rounded-2xl border border-line bg-white p-5 lg:sticky lg:top-5">
      <div className="flex items-center justify-between">
        <span className="text-[17px] font-bold text-ink">Bộ lọc</span>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-[13.5px] font-medium text-primary-bright hover:underline"
        >
          Xóa hết
        </button>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Loại chỗ ở</span>
        <div className="flex gap-2">
          {HOUSING_OPTIONS.map((opt) => (
            <button
              key={opt.value || "all"}
              type="button"
              onClick={() => setHousing(opt.value)}
              className={chip(housing === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Giá thuê / tháng (triệu)</span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            step={0.1}
            placeholder="1.0"
            value={minTrieu}
            onChange={(e) => setMinTrieu(e.target.value)}
            className="w-full rounded-[10px] border border-line px-3 py-2.5 text-[14.5px] text-ink outline-none focus:border-primary"
            aria-label="Giá tối thiểu (triệu)"
          />
          <span className="text-ink-faint">–</span>
          <input
            type="number"
            min={0}
            step={0.1}
            placeholder="2.5"
            value={maxTrieu}
            onChange={(e) => setMaxTrieu(e.target.value)}
            className="w-full rounded-[10px] border border-line px-3 py-2.5 text-[14.5px] text-ink outline-none focus:border-primary"
            aria-label="Giá tối đa (triệu)"
          />
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Khoảng cách tới CTU</span>
        <div className="flex gap-2">
          {DISTANCE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setDistance(distance === opt.value ? "" : opt.value)}
              className={chip(distance === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Quận / huyện</span>
        <div className="flex flex-col gap-1">
          {DISTRICTS.map((name) => {
            const active = district === name;
            return (
              <button
                key={name}
                type="button"
                onClick={() => setDistrict(active ? "" : name)}
                className="flex items-center gap-2.5 rounded-lg px-1 py-1.5 text-left text-[15px] text-ink transition hover:bg-paper"
              >
                <span
                  className={`flex h-[18px] w-[18px] items-center justify-center rounded-[5px] border transition ${
                    active ? "border-primary bg-primary text-white" : "border-[#c6d2e0] bg-white"
                  }`}
                >
                  {active && (
                    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6.5L4.6 9L10 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                  )}
                </span>
                {name}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className={sectionLabel}>Diện tích tối thiểu</span>
        <div className="flex flex-wrap gap-2">
          {AREA_OPTIONS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMinArea(minArea === value ? "" : value)}
              className={`rounded-[9px] border px-3.5 py-2 text-[13.5px] transition ${
                minArea === value
                  ? "border-primary bg-primary-soft font-semibold text-primary"
                  : "border-line text-ink-soft hover:border-primary-ring"
              }`}
            >
              {value} m²
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={apply}
        className="rounded-[11px] bg-primary py-3 text-[15.5px] font-semibold text-white transition hover:bg-navy"
      >
        Áp dụng bộ lọc
      </button>
    </aside>
  );
}

export function SortSelect({ current }: { current: HomeParams }) {
  const router = useRouter();

  function changeSort(sort: string) {
    const params = buildParams({ ...current, sort });
    router.push(`/?${params.toString()}`);
  }

  return (
    <label className="flex items-center gap-2.5 text-sm text-ink-muted">
      Sắp xếp
      <select
        value={current.sort ?? "newest"}
        onChange={(e) => changeSort(e.target.value)}
        className="rounded-[10px] border border-line bg-white px-3.5 py-2.5 text-[14.5px] font-medium text-ink outline-none focus:border-primary"
      >
        {SORT_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
