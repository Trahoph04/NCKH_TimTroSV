"use client";

import { useEffect, useState } from "react";
import { initials, priceShort } from "@/lib/chat/format";
import type { ListingSnapshot } from "@/lib/chat/types";
import type { ListingOut, SearchResult } from "@/lib/api";

function Shell({
  children,
  onClose,
  className = "max-w-md bg-white shadow-2xl",
}: {
  children: React.ReactNode;
  onClose: () => void;
  className?: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
    >
      <div className={`w-full rounded-2xl ${className}`}>{children}</div>
    </div>
  );
}

// ------------------------------------------------------------- Thành đôi!
export function MatchModal({
  meName,
  partnerName,
  onChat,
  onClose,
}: {
  meName: string;
  partnerName: string;
  onChat: () => void;
  onClose: () => void;
}) {
  return (
    <Shell onClose={onClose} className="max-w-sm overflow-hidden bg-white shadow-2xl">
      <div className="bg-gradient-to-br from-primary to-primary-bright px-6 pb-8 pt-10 text-center text-white">
        <div className="text-3xl font-extrabold tracking-tight">Thành đôi!</div>
        <p className="mt-1 text-sm text-white/85">Bạn và {partnerName} đã cùng thích nhau</p>
        <div className="mt-6 flex items-center justify-center">
          {[meName, partnerName].map((n, i) => (
            <span
              key={i}
              className={`flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-primary-soft text-2xl font-extrabold text-primary ${
                i ? "-ml-4" : ""
              }`}
            >
              {initials(n)}
            </span>
          ))}
        </div>
      </div>
      <div className="space-y-2 p-5">
        <button
          onClick={onChat}
          autoFocus
          className="w-full rounded-[10px] bg-primary py-3 font-semibold text-white hover:bg-navy"
        >
          Nhắn tin ngay
        </button>
        <button onClick={onClose} className="w-full rounded-[10px] py-2.5 text-sm font-semibold text-ink-muted hover:bg-tint">
          Để sau
        </button>
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------ Báo cáo
const REASONS = [
  ["spam", "Spam / quảng cáo"],
  ["harass", "Quấy rối, lời lẽ không phù hợp"],
  ["scam", "Lừa đảo, đòi chuyển tiền"],
  ["fake", "Hồ sơ giả mạo"],
  ["other", "Lý do khác"],
] as const;

export function ReportModal({
  name,
  onSubmit,
  onClose,
}: {
  name: string;
  onSubmit: (reason: string, note: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState<string>("spam");
  const [note, setNote] = useState("");
  return (
    <Shell onClose={onClose}>
      <div className="p-6">
        <h2 className="text-lg font-bold text-ink">Báo cáo {name}</h2>
        <p className="mt-1 text-sm text-ink-muted">Báo cáo được gửi ẩn danh tới nhóm quản trị.</p>
        <div className="mt-4 space-y-2">
          {REASONS.map(([k, label]) => (
            <label
              key={k}
              className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 text-sm ${
                reason === k ? "border-primary-bright bg-primary-soft" : "border-line"
              }`}
            >
              <input type="radio" name="reason" checked={reason === k} onChange={() => setReason(k)} />
              {label}
            </label>
          ))}
        </div>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
          placeholder="Mô tả thêm (không bắt buộc)"
          className="mt-3 h-20 w-full resize-none rounded-xl border border-line p-3 text-sm outline-none focus:border-primary-bright"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-[10px] px-4 py-2 text-sm font-semibold text-ink-muted hover:bg-tint">
            Huỷ
          </button>
          <button
            onClick={() => onSubmit(reason, note)}
            className="rounded-[10px] bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-navy"
          >
            Gửi báo cáo
          </button>
        </div>
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------ Xác nhận
export function ConfirmModal({
  title,
  body,
  confirmLabel,
  onConfirm,
  onClose,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Shell onClose={onClose}>
      <div className="p-6">
        <h2 className="text-lg font-bold text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">{body}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-[10px] px-4 py-2 text-sm font-semibold text-ink-muted hover:bg-tint">
            Không
          </button>
          <button
            onClick={onConfirm}
            className="rounded-[10px] bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Shell>
  );
}

// -------------------------------------------------- Chọn tin trọ để chia sẻ
export function ListingPicker({
  onPick,
  onClose,
}: {
  onPick: (id: number, snapshot: ListingSnapshot) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ListingOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/listings?size=10${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ""}`, {
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error();
        setItems(((await res.json()) as SearchResult).items);
        setError(null);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError("Không tải được danh sách tin");
      }
    }, 250);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q]);

  return (
    <Shell onClose={onClose} className="max-w-lg bg-white shadow-2xl">
      <div className="flex max-h-[80vh] flex-col">
        <div className="border-b border-line p-5">
          <h2 className="text-lg font-bold text-ink">Chia sẻ một tin trọ</h2>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm theo tên đường, khu vực… (vd: 3/2, Xuân Khánh)"
            className="mt-3 w-full rounded-[10px] border border-line bg-paper px-3 py-2.5 text-sm outline-none focus:border-primary-bright"
          />
        </div>
        <ul className="min-h-[200px] flex-1 space-y-1 overflow-y-auto p-3">
          {error && <li className="p-4 text-center text-sm text-rose-600">{error}</li>}
          {!error && items === null && <li className="p-4 text-center text-sm text-ink-muted">Đang tải…</li>}
          {items?.length === 0 && <li className="p-4 text-center text-sm text-ink-muted">Không có tin phù hợp.</li>}
          {items?.map((l) => (
            <li key={l.id}>
              <button
                onClick={() =>
                  onPick(l.id, {
                    listing_id: l.id,
                    title: l.title,
                    price: l.price,
                    area: l.area,
                    district: l.district,
                    address: l.address,
                    image: l.images[0] ?? null,
                    minutes_khu2: l.route_time_campus?.[1] != null ? Math.round(l.route_time_campus[1]) : null,
                  })
                }
                className="flex w-full gap-3 rounded-xl p-2 text-left hover:bg-tint"
              >
                <span className="photo-placeholder h-14 w-16 shrink-0 overflow-hidden rounded-lg">
                  {l.images[0] && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={l.images[0]} alt="" className="h-full w-full object-cover" />
                  )}
                </span>
                <span className="min-w-0">
                  <span className="line-clamp-2 text-sm font-semibold leading-snug text-ink">{l.title}</span>
                  <span className="text-sm font-bold text-primary-bright">{priceShort(l.price)}</span>
                  <span className="ml-2 text-xs text-ink-muted">{l.district ?? ""}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------- Xem ảnh
export function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  return (
    <Shell onClose={onClose} className="max-w-4xl">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="Ảnh trong cuộc trò chuyện" className="mx-auto max-h-[85vh] rounded-xl" onClick={onClose} />
    </Shell>
  );
}

export function Toast({ text }: { text: string }) {
  return (
    <div className="pointer-events-none fixed bottom-6 left-1/2 z-[60] -translate-x-1/2 rounded-full bg-navy px-4 py-2.5 text-sm font-medium text-white shadow-lg">
      {text}
    </div>
  );
}
