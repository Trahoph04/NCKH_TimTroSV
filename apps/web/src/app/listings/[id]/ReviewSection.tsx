"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  NEGATIVE_TAGS,
  RELATION_LABEL,
  RELATIONS,
  REVIEW_TAGS,
  TAG_LABEL,
  WARN_MIN_REPORTS,
  formatRating,
  type Review,
  type ReviewList,
} from "@/lib/reviews";

function Stars({ value, size = "text-base" }: { value: number; size?: string }) {
  // làm tròn tới nửa sao không cần: hiện số kèm theo nên chỉ cần ước lượng bằng mắt
  const full = Math.round(value);
  return (
    <span className={`${size} tracking-tight`} aria-label={`${formatRating(value)} trên 5 sao`}>
      <span className="text-amber-500">{"★".repeat(full)}</span>
      <span className="text-slate-300">{"★".repeat(5 - full)}</span>
    </span>
  );
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

const MAX_TAGS = 6;

// Đánh giá nhà trọ của sinh viên (thuyết minh dòng 6 "đánh giá"; tag tiêu cực = cảnh báo rủi ro 14.2).
export default function ReviewSection({ listingId, loggedIn }: { listingId: number; loggedIn: boolean }) {
  const [data, setData] = useState<ReviewList | null>(null);
  const [mine, setMine] = useState<Review | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(0);
  const [relation, setRelation] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [moreBusy, setMoreBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/listings/${listingId}/reviews`, { cache: "no-store" });
      if (!res.ok) throw new Error();
      setData((await res.json()) as ReviewList);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
    if (loggedIn) {
      const res = await fetch(`/api/listings/${listingId}/reviews/mine`, { cache: "no-store" }).catch(() => null);
      if (res?.ok) setMine((await res.json()) as Review | null);
    }
  }, [listingId, loggedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  function startEdit() {
    setRating(mine?.rating ?? 0);
    setRelation(mine?.relation ?? "");
    setTags(mine?.tags ?? []);
    setContent(mine?.content ?? "");
    setFormError(null);
    setEditing(true);
  }

  function toggleTag(key: string) {
    setTags((cur) => (cur.includes(key) ? cur.filter((t) => t !== key) : cur.length >= MAX_TAGS ? cur : [...cur, key]));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!rating) return setFormError("Chọn số sao");
    if (!relation) return setFormError("Cho biết bạn đang ở, đã ở hay chỉ đi xem phòng");
    setBusy(true);
    setFormError(null);
    try {
      const res = await fetch(`/api/listings/${listingId}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, relation, tags, content: content.trim() || null }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // 422 của FastAPI là mảng {msg} — lấy câu đầu (vd. "Không ghi số điện thoại hay đường link trong đánh giá")
        const detail = Array.isArray(body.detail) ? String(body.detail[0]?.msg ?? "").replace(/^Value error, /, "") : body.detail;
        setFormError(typeof detail === "string" && detail ? detail : "Không gửi được đánh giá");
        return;
      }
      setMine(body as Review);
      setEditing(false);
      await load();
    } catch {
      setFormError("Không kết nối được máy chủ");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    // bấm 2 lần: lần đầu chỉ hỏi lại (không dùng window.confirm)
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setConfirmDelete(false);
    setBusy(true);
    try {
      const res = await fetch(`/api/listings/${listingId}/reviews/mine`, { method: "DELETE" });
      if (res.ok || res.status === 404) {
        setMine(null);
        setEditing(false);
        setActionError(null);
        await load();
      } else {
        const body = await res.json().catch(() => ({}));
        setActionError(typeof body.detail === "string" ? body.detail : "Không xoá được đánh giá");
      }
    } catch {
      setActionError("Không kết nối được máy chủ");
    } finally {
      setBusy(false);
    }
  }

  // Tóm tắt (điểm, phân bố) tính trên MỌI đánh giá; danh sách tải từng trang 10 cái
  async function loadMore() {
    if (!data) return;
    setMoreBusy(true);
    try {
      const res = await fetch(`/api/listings/${listingId}/reviews?page=${data.page + 1}&size=${data.size}`, { cache: "no-store" });
      if (res.ok) {
        const next = (await res.json()) as ReviewList;
        setData((d) => (d ? { ...next, items: [...d.items, ...next.items] } : next));
      }
    } finally {
      setMoreBusy(false);
    }
  }

  const summary = data?.summary;
  const warnings = summary
    ? Object.entries(summary.tag_counts).filter(([t, n]) => NEGATIVE_TAGS.has(t) && n >= WARN_MIN_REPORTS)
    : [];

  return (
    <section className="mt-6 border-t border-slate-200 pt-5" aria-labelledby="reviews-heading">
      <h2 id="reviews-heading" className="text-lg font-bold text-slate-800">
        Đánh giá của sinh viên
      </h2>

      {loadError && <p className="mt-2 text-sm text-rose-600">Không tải được đánh giá.</p>}

      {summary && summary.total > 0 && summary.average != null && (
        <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-start">
          <div className="shrink-0 text-center sm:w-32">
            <p className="text-4xl font-extrabold text-slate-800">{formatRating(summary.average)}</p>
            <Stars value={summary.average} size="text-lg" />
            <p className="text-xs text-slate-500">{summary.total} đánh giá</p>
          </div>
          <div className="flex-1">
            {[5, 4, 3, 2, 1].map((star) => {
              const n = summary.rating_counts[String(star)] ?? 0;
              return (
                <div key={star} className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="w-6 text-right">{star}★</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <span className="block h-full rounded-full bg-amber-400" style={{ width: `${(n / summary.total) * 100}%` }} />
                  </span>
                  <span className="w-5">{n}</span>
                </div>
              );
            })}
            {Object.keys(summary.tag_counts).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(summary.tag_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([t, n]) => (
                    <span
                      key={t}
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        NEGATIVE_TAGS.has(t) ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      {TAG_LABEL[t] ?? t} · {n}
                    </span>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          <p className="font-semibold">Lưu ý từ người đã ở / đi xem</p>
          <ul className="mt-1 list-disc pl-5">
            {warnings.map(([t, n]) => (
              <li key={t}>
                {n} người báo “{TAG_LABEL[t] ?? t}”
              </li>
            ))}
          </ul>
          <Link href="/cam-nang#phap-ly" className="mt-1 inline-block font-semibold underline">
            Cần làm gì khi gặp trường hợp này →
          </Link>
        </div>
      )}

      {summary && summary.total === 0 && !editing && (
        <p className="mt-2 text-sm text-slate-500">Chưa có đánh giá nào. Bạn đã ở hoặc đi xem phòng này? Hãy là người đầu tiên.</p>
      )}

      {/* Viết / sửa đánh giá */}
      {!loggedIn ? (
        <p className="mt-3 text-sm">
          <Link href={`/login?next=${encodeURIComponent(`/listings/${listingId}`)}`} className="font-semibold text-primary underline">
            Đăng nhập
          </Link>{" "}
          để đánh giá nhà trọ này.
        </p>
      ) : editing ? (
        <form onSubmit={submit} className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-700">Chấm điểm</p>
          <div className="mt-1 flex gap-1" role="radiogroup" aria-label="Số sao">
            {[1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={rating === s}
                aria-label={`${s} sao`}
                onClick={() => setRating(s)}
                className={`text-3xl leading-none transition ${s <= rating ? "text-amber-500" : "text-slate-300 hover:text-amber-300"}`}
              >
                ★
              </button>
            ))}
          </div>

          <p className="mt-4 text-sm font-semibold text-slate-700">Bạn là</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5" role="radiogroup" aria-label="Quan hệ với nhà trọ">
            {RELATIONS.map((r) => (
              <button
                key={r.key}
                type="button"
                role="radio"
                aria-checked={relation === r.key}
                onClick={() => setRelation(r.key)}
                className={`rounded-full border px-3 py-1 text-sm transition ${
                  relation === r.key ? "border-primary bg-primary-soft font-semibold text-primary" : "border-slate-300 text-slate-600"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <p className="mt-4 text-sm font-semibold text-slate-700">
            Nhận xét nhanh <span className="font-normal text-slate-400">(tối đa {MAX_TAGS})</span>
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {REVIEW_TAGS.map((t) => {
              const on = tags.includes(t.key);
              return (
                <button
                  key={t.key}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleTag(t.key)}
                  className={`rounded-full border px-2.5 py-1 text-xs transition ${
                    on
                      ? t.negative
                        ? "border-rose-400 bg-rose-50 font-semibold text-rose-700"
                        : "border-emerald-400 bg-emerald-50 font-semibold text-emerald-700"
                      : "border-slate-300 text-slate-600 hover:border-slate-400"
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          <label htmlFor="review-content" className="mt-4 block text-sm font-semibold text-slate-700">
            Chia sẻ thêm <span className="font-normal text-slate-400">(không bắt buộc, không ghi SĐT/đường link)</span>
          </label>
          <textarea
            id="review-content"
            value={content}
            onChange={(e) => setContent(e.target.value.slice(0, 1000))}
            rows={3}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-primary"
            placeholder="Ví dụ: phòng đúng như ảnh, chủ trả cọc đầy đủ khi chuyển đi…"
          />
          <p className="text-right text-xs text-slate-400">{content.length}/1000</p>

          {formError && <p className="mt-1 text-sm text-rose-600">{formError}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="submit" disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-navy disabled:opacity-60">
              {mine ? "Lưu thay đổi" : "Gửi đánh giá"}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-600">
              Huỷ
            </button>
          </div>
        </form>
      ) : mine ? (
        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          Bạn đã đánh giá <Stars value={mine.rating} size="text-sm" />
          {mine.status === "hidden" && <span className="ml-1 text-rose-600">(đang bị quản trị viên ẩn)</span>}
          <span className="ml-2 inline-flex gap-3">
            <button type="button" onClick={startEdit} className="font-semibold text-primary underline">
              Sửa
            </button>
            {/* đánh giá bị ẩn không xoá được (xoá rồi gửi lại = thoát kiểm duyệt) — API cũng chặn 409 */}
            {mine.status !== "hidden" && (
              <button
                type="button"
                disabled={busy}
                onClick={remove}
                onBlur={() => setConfirmDelete(false)}
                className="font-semibold text-rose-600 underline"
              >
                <span aria-live="polite">{confirmDelete ? "Bấm lần nữa để xoá" : "Xoá"}</span>
              </button>
            )}
          </span>
          {actionError && <p className="mt-1 text-rose-600">{actionError}</p>}
        </div>
      ) : (
        <button type="button" onClick={startEdit} className="mt-3 rounded-md border border-primary px-4 py-2 text-sm font-semibold text-primary hover:bg-primary-soft">
          Viết đánh giá
        </button>
      )}

      {/* Danh sách */}
      {data && data.items.length > 0 && (
        <ul className="mt-5 flex flex-col gap-3">
          {data.items.map((r) => (
            <li key={r.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
                <Stars value={r.rating} size="text-sm" />
                <span className="font-semibold text-slate-700">{r.author}</span>
                {r.relation && <span className="text-xs text-slate-500">· {RELATION_LABEL[r.relation] ?? r.relation}</span>}
                <span className="text-xs text-slate-400">· {fmtDate(r.updated_at ?? r.created_at)}</span>
              </div>
              {r.tags.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
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
              {r.content && <p className="mt-1.5 whitespace-pre-line text-sm text-slate-700">{r.content}</p>}
            </li>
          ))}
        </ul>
      )}
      {data && summary && data.items.length < summary.total && (
        <button
          type="button"
          disabled={moreBusy}
          onClick={() => void loadMore()}
          className="mt-3 text-sm font-semibold text-primary underline disabled:opacity-50"
        >
          Xem thêm đánh giá ({summary.total - data.items.length})
        </button>
      )}
    </section>
  );
}
