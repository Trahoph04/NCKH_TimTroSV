"use client";

import Link from "next/link";
import { mediaUrl } from "@/lib/chat/client";
import { priceShort, timeHM } from "@/lib/chat/format";
import type { ImageRef, ListingSnapshot, Message } from "@/lib/chat/types";
import { Avatar } from "./ConversationList";

type Props = {
  m: Message;
  mine: boolean;
  partnerName: string;
  showAvatar: boolean;
  showMeta: boolean;
  receipt?: "Đã xem" | "Đã gửi";
  onOpenImage: (src: string) => void;
};

export default function MessageItem({ m, mine, partnerName, showAvatar, showMeta, receipt, onOpenImage }: Props) {
  if (m.kind === "system") {
    return (
      <div className="my-2 text-center">
        <span className="inline-block rounded-full bg-tint px-3 py-1 text-xs text-ink-muted">{m.body}</span>
      </div>
    );
  }

  const meta = (
    <span className={`mt-1 block text-[11px] text-ink-faint ${mine ? "text-right" : ""}`}>
      {m.status === "sending" ? (
        "Đang gửi…"
      ) : m.status === "failed" ? (
        <button onClick={m.retry} className="font-semibold text-rose-600 hover:underline">
          Gửi lỗi · Thử lại
        </button>
      ) : (
        <>
          {timeHM(m.created_at)}
          {receipt && <span className={receipt === "Đã xem" ? "text-primary-bright" : ""}> · {receipt}</span>}
        </>
      )}
    </span>
  );

  return (
    <div className={`flex items-end gap-2 ${mine ? "justify-end" : ""} ${showAvatar ? "mt-3" : "mt-1"}`}>
      {!mine && (showMeta ? <Avatar name={partnerName} size={30} /> : <span className="w-[30px] shrink-0" />)}
      <div className={`flex max-w-[78%] flex-col sm:max-w-[65%] ${mine ? "items-end" : "items-start"} ${m.status === "sending" ? "opacity-70" : ""}`}>
        {m.kind === "image" && <Images m={m} onOpen={onOpenImage} />}
        {m.kind === "listing" && m.payload && <ListingCard s={m.payload as ListingSnapshot} />}
        {m.body && (
          <div
            className={`whitespace-pre-wrap break-words px-4 py-2.5 text-[15px] leading-[22px] ${
              m.kind !== "text" ? "mt-1" : ""
            } ${
              mine
                ? "rounded-2xl rounded-br-md bg-primary text-white"
                : "rounded-2xl rounded-bl-md border border-line bg-white text-ink"
            }`}
          >
            {m.body}
          </div>
        )}
        {(showMeta || m.status || receipt) && meta}
      </div>
    </div>
  );
}

function Images({ m, onOpen }: { m: Message; onOpen: (src: string) => void }) {
  const refs = (m.payload as { images?: ImageRef[] } | null)?.images;
  const srcs = refs?.map((r) => mediaUrl(r.id)) ?? m.local_images ?? [];
  const n = srcs.length;
  const shown = srcs.slice(0, 4);
  // Ảnh đơn: giữ chỗ đúng tỉ lệ w/h server trả về TRƯỚC khi ảnh tải xong. Không
  // có thì khung cao 0 → ảnh tải xong nở ra đẩy nội dung, khung chat trượt khỏi
  // đáy hội thoại (người dùng đang đọc tin mới nhất thì bị đẩy lên).
  const single = n === 1 ? refs?.[0] : undefined;
  const ratio = single && single.w > 0 && single.h > 0 ? `${single.w} / ${single.h}` : undefined;
  return (
    <div className={`grid gap-1 overflow-hidden rounded-2xl ${n === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
      {shown.map((src, i) => (
        <button
          key={src}
          onClick={() => onOpen(src)}
          className={`photo-placeholder relative block overflow-hidden ${n === 1 ? "max-h-80 w-64 sm:w-72" : "h-32 w-32 sm:h-36 sm:w-36"}`}
          style={ratio ? { aspectRatio: ratio } : undefined}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt={`Ảnh ${i + 1}`}
            loading="lazy"
            width={single?.w}
            height={single?.h}
            className={`h-full w-full ${n === 1 ? "object-contain" : "object-cover"}`}
          />
        </button>
      ))}
    </div>
  );
}

function ListingCard({ s }: { s: ListingSnapshot }) {
  return (
    <div className="w-72 overflow-hidden rounded-2xl border border-line bg-white">
      <div className="flex gap-3 p-3">
        <div className="photo-placeholder h-16 w-20 shrink-0 overflow-hidden rounded-lg">
          {s.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={s.image} alt="" className="h-full w-full object-cover" />
          )}
        </div>
        <div className="min-w-0">
          <div className="line-clamp-2 text-sm font-bold leading-snug text-ink">{s.title}</div>
          <div className="mt-0.5 font-bold text-primary-bright">
            {priceShort(s.price)}
            {s.area ? <span className="ml-1 text-xs font-normal text-ink-muted">· {s.area} m²</span> : null}
          </div>
          <div className="truncate text-xs text-ink-muted">
            {s.minutes_khu2 != null ? `${s.minutes_khu2} phút tới khu II` : s.district ?? ""}
          </div>
        </div>
      </div>
      <Link
        href={`/listings/${s.listing_id}`}
        target="_blank"
        className="mx-3 mb-3 block rounded-[10px] border border-line py-2 text-center text-sm font-semibold text-primary hover:bg-primary-soft"
      >
        Mở tin này
      </Link>
    </div>
  );
}
