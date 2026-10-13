"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { NEGATIVE_TAGS, RELATION_LABEL, TAG_LABEL, type Review } from "@/lib/reviews";

type AdminReview = Review & { listing_title: string | null; author_email: string | null };
type Page = { total: number; page: number; size: number; items: AdminReview[] };
type Filter = "" | "visible" | "hidden";

const SIZE = 20;
const FILTERS: { value: Filter; label: string }[] = [
  { value: "", label: "Tất cả" },
  { value: "visible", label: "Đang hiện" },
  { value: "hidden", label: "Đã ẩn" },
];

export default function ReviewsAdmin() {
  const [filter, setFilter] = useState<Filter>("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const latest = useRef(0);

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ page: String(page), size: String(SIZE) });
    if (filter) qs.set("status", filter);
    const ticket = ++latest.current;
    try {
      const res = await fetch(`/api/admin/reviews?${qs}`, { cache: "no-store" });
      const body = await res.json().catch(() => ({}));
      if (ticket !== latest.current) return;
      if (!res.ok) {
        setError(typeof body.detail === "string" ? body.detail : "Không tải được danh sách");
        return;
      }
      setData(body as Page);
      setError(null);
    } catch {
      if (ticket === latest.current) setError("Không kết nối được máy chủ");
    }
  }, [page, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function setStatus(r: AdminReview, status: "visible" | "hidden") {
    setBusyId(r.id);
    try {
      const res = await fetch(`/api/admin/reviews/${r.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(typeof body.detail === "string" ? body.detail : "Không cập nhật được");
        return;
      }
      setError(null);
      setData((d) => (d ? { ...d, items: d.items.map((x) => (x.id === r.id ? { ...x, status } : x)) } : d));
    } catch {
      setError("Không kết nối được máy chủ");
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / SIZE)) : 1;

  return (
    <div className="mt-6">
      <div className="flex gap-1.5" role="group" aria-label="Lọc đánh giá">
        {FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            onClick={() => {
              setPage(1);
              setFilter(f.value);
            }}
            className={`rounded-full border px-3 py-1 text-[13px] transition ${
              filter === f.value ? "border-primary bg-primary-soft font-semibold text-primary" : "border-line text-ink-soft hover:border-primary-ring"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</p>}
      {data && <p className="mt-4 text-sm text-ink-muted">{data.total} đánh giá</p>}
      {data && data.items.length === 0 && <p className="mt-8 text-center text-ink-muted">Chưa có đánh giá nào.</p>}

      <ul className="mt-3 flex flex-col gap-2.5">
        {data?.items.map((r) => (
          <li
            key={r.id}
            className={`rounded-[13px] border bg-white p-4 ${r.status === "hidden" ? "border-rose-200 opacity-75" : "border-line-soft"}`}
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <Link href={`/listings/${r.listing_id}`} className="line-clamp-1 font-semibold text-ink hover:text-primary">
                  {r.listing_title ?? `Tin #${r.listing_id}`}
                </Link>
                <p className="text-sm">
                  <span className="text-amber-500">{"★".repeat(r.rating)}</span>
                  <span className="text-slate-300">{"★".repeat(5 - r.rating)}</span>
                  <span className="ml-2 text-ink-soft">{r.author}</span>
                  {r.author_email && <span className="text-ink-muted"> · {r.author_email}</span>}
                  {r.relation && <span className="text-ink-muted"> · {RELATION_LABEL[r.relation] ?? r.relation}</span>}
                  {r.status === "hidden" && <span className="ml-2 font-semibold text-rose-600">Đã ẩn</span>}
                </p>
                {r.tags.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {r.tags.map((t) => (
                      <span
                        key={t}
                        className={`rounded-full px-2 py-0.5 text-[11px] ${NEGATIVE_TAGS.has(t) ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}
                      >
                        {TAG_LABEL[t] ?? t}
                      </span>
                    ))}
                  </div>
                )}
                {r.content && <p className="mt-1.5 whitespace-pre-line text-sm text-ink-soft">{r.content}</p>}
              </div>
              <button
                type="button"
                disabled={busyId === r.id}
                onClick={() => void setStatus(r, r.status === "hidden" ? "visible" : "hidden")}
                className={`shrink-0 rounded-lg border px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${
                  r.status === "hidden" ? "border-line text-ink-soft hover:text-primary" : "border-rose-200 text-rose-600 hover:bg-rose-50"
                }`}
              >
                {r.status === "hidden" ? "Hiện lại" : "Ẩn đánh giá"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      {data && totalPages > 1 && (
        <div className="mt-5 flex items-center justify-center gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">
            ← Trước
          </button>
          <span className="text-ink-muted">
            Trang {page}/{totalPages}
          </span>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">
            Sau →
          </button>
        </div>
      )}
    </div>
  );
}
