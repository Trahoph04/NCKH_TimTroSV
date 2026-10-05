"use client";

import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import { dayLabel, lastSeenText, scoreText } from "@/lib/chat/format";
import type { SocketStatus } from "@/lib/chat/useChatSocket";
import type { Conversation, Me, Message } from "@/lib/chat/types";
import { Avatar } from "./ConversationList";
import MessageItem from "./MessageItem";
import { Lightbox, ListingPicker } from "./Modals";

type Thread = { items: Message[]; hasMore: boolean; loaded: boolean };

type Props = {
  me: Me;
  conv: Conversation;
  thread?: Thread;
  online: boolean;
  lastSeen: string | null;
  typing: boolean;
  socketStatus: SocketStatus;
  onBack: () => void;
  onLoadOlder: () => Promise<void>;
  onSendText: (text: string) => void;
  onSendImages: (files: File[]) => void;
  onSendListing: (listingId: number, snapshot: Message["payload"]) => void;
  onTyping: (isTyping: boolean) => void;
  onShowProfile: () => void;
  onReport: () => void;
};

const QUICK = [
  { label: "Hẹn đi xem phòng", text: "Mình hẹn nhau đi xem phòng nhé? Mình rảnh vào " },
  { label: "Gửi ngân sách của mình", text: "Ngân sách của mình khoảng  triệu/tháng mỗi người, " },
];

const GROUP_GAP_MS = 5 * 60 * 1000;

export default function ChatThread(p: Props) {
  const { conv, thread, me } = p;
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [newBelow, setNewBelow] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const typingSent = useRef(0);
  const typingStop = useRef<ReturnType<typeof setTimeout>>();

  const items = thread?.items ?? [];
  const lastItem = items[items.length - 1];

  // ---- cuộn: lần đầu xuống đáy; tin mới → xuống đáy nếu đang ở đáy hoặc là tin của mình
  const prevLast = useRef<string | undefined>();
  const prevFirst = useRef<number | undefined>();
  const prevHeight = useRef(0);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const lastKey = lastItem ? `${lastItem.id}:${lastItem.client_id}` : undefined;
    const first = items[0]?.id;
    if (prevFirst.current !== undefined && first !== prevFirst.current && lastKey === prevLast.current) {
      // tải tin cũ hơn: giữ nguyên vị trí đang đọc
      el.scrollTop = el.scrollHeight - prevHeight.current + el.scrollTop;
    } else if (lastKey !== prevLast.current) {
      const mine = lastItem?.sender_id === me.id;
      if (prevLast.current === undefined || atBottom || mine) {
        el.scrollTop = el.scrollHeight;
        setNewBelow(false);
      } else {
        setNewBelow(true);
      }
    }
    prevLast.current = lastKey;
    prevFirst.current = first;
    prevHeight.current = el.scrollHeight;
  });

  // đang nhập hiện ra ở đáy → kéo xuống để thấy
  useEffect(() => {
    const el = scrollRef.current;
    if (p.typing && el && atBottom) el.scrollTop = el.scrollHeight;
  }, [p.typing, atBottom]);

  useEffect(() => () => {
    clearTimeout(typingStop.current);
  }, []);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setAtBottom(bottom);
    if (bottom) setNewBelow(false);
    prevHeight.current = el.scrollHeight;
  };

  const loadOlder = async () => {
    setLoadingOlder(true);
    try {
      await p.onLoadOlder();
    } finally {
      setLoadingOlder(false);
    }
  };

  // ---- composer
  const signalTyping = (value: string) => {
    const now = Date.now();
    if (value && now - typingSent.current > 2500) {
      p.onTyping(true);
      typingSent.current = now;
    }
    clearTimeout(typingStop.current);
    typingStop.current = setTimeout(() => {
      p.onTyping(false);
      typingSent.current = 0;
    }, value ? 3500 : 0);
  };

  const submit = () => {
    const body = text.trim();
    if (!body) return;
    p.onSendText(body);
    setText("");
    clearTimeout(typingStop.current);
    if (typingSent.current) p.onTyping(false);
    typingSent.current = 0;
    inputRef.current?.focus();
  };

  const insertQuick = (t: string) => {
    setText((cur) => (cur ? `${cur} ${t}` : t));
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
      }
    });
  };

  // auto-grow textarea
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [text]);

  // "Đã xem"/"Đã gửi" chỉ hiện dưới tin CUỐI của mình
  const lastMineId = [...items].reverse().find((m) => m.sender_id === me.id && !m.status)?.id;
  const score = scoreText(conv.score);
  const firstName = conv.partner.name.split(" ").slice(-1)[0];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* header */}
      <header className="flex items-center justify-between gap-3 border-b border-line bg-white px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={p.onBack}
            className="-ml-1 rounded-lg p-1.5 text-ink-soft hover:bg-tint md:hidden"
            aria-label="Quay lại danh sách"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12.5 4.5 7 10l5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <Avatar name={conv.partner.name} size={42} online={p.online} />
          <div className="min-w-0">
            <div className="truncate font-bold text-ink">{conv.partner.name}</div>
            <div className={`text-xs ${p.online ? "text-emerald-600" : "text-ink-muted"}`}>
              {p.typing ? "Đang nhập…" : p.online ? "Đang hoạt động" : lastSeenText(p.lastSeen)}
            </div>
          </div>
          {score && (
            <span className="hidden shrink-0 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 sm:inline">
              Đã ghép {score}
            </span>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={p.onShowProfile}
            className="rounded-[10px] border border-line px-3 py-2 text-sm font-semibold text-ink-soft hover:bg-tint xl:hidden"
          >
            Xem hồ sơ
          </button>
          <button
            onClick={p.onReport}
            className="hidden rounded-[10px] border border-line px-3 py-2 text-sm font-semibold text-ink-soft hover:bg-tint sm:block"
          >
            Báo cáo
          </button>
        </div>
      </header>

      {p.socketStatus === "offline" && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-800">
          Mất kết nối realtime — đang tự đồng bộ mỗi 3 giây và kết nối lại…
        </div>
      )}

      {/* messages */}
      <div ref={scrollRef} onScroll={onScroll} className="relative min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8">
        {!thread?.loaded ? (
          <div className="flex h-full items-center justify-center text-sm text-ink-muted">Đang tải tin nhắn…</div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col">
            {thread.hasMore ? (
              <button
                onClick={loadOlder}
                disabled={loadingOlder}
                className="mx-auto mb-4 rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-ink-soft hover:bg-tint"
              >
                {loadingOlder ? "Đang tải…" : "Xem tin cũ hơn"}
              </button>
            ) : (
              <div className="mx-auto mb-4 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
                {score ? `Đã ghép ở ${score}` : "Đã ghép đôi"} · {dayLabel(conv.created_at).toLowerCase()}
              </div>
            )}

            {items.map((m, i) => {
              const prev = items[i - 1];
              const next = items[i + 1];
              const newDay = !prev || dayLabel(prev.created_at) !== dayLabel(m.created_at);
              const sameAsPrev =
                !!prev && !newDay && prev.sender_id === m.sender_id && prev.kind !== "system" &&
                new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() < GROUP_GAP_MS;
              const lastOfGroup =
                !next || next.sender_id !== m.sender_id || next.kind === "system" ||
                dayLabel(next.created_at) !== dayLabel(m.created_at) ||
                new Date(next.created_at).getTime() - new Date(m.created_at).getTime() >= GROUP_GAP_MS;
              return (
                <Fragment key={m.status ? `p-${m.client_id}` : m.id}>
                  {newDay && i > 0 && (
                    <div className="my-3 text-center text-xs font-medium text-ink-faint">{dayLabel(m.created_at)}</div>
                  )}
                  <MessageItem
                    m={m}
                    mine={m.sender_id === me.id}
                    partnerName={conv.partner.name}
                    showAvatar={!sameAsPrev}
                    showMeta={lastOfGroup}
                    receipt={
                      m.id === lastMineId
                        ? conv.partner_last_read >= m.id
                          ? "Đã xem"
                          : "Đã gửi"
                        : undefined
                    }
                    onOpenImage={setLightbox}
                  />
                </Fragment>
              );
            })}

            {p.typing && (
              <div className="mt-2 flex items-center gap-2">
                <Avatar name={conv.partner.name} size={30} />
                <div className="flex gap-1 rounded-2xl border border-line bg-white px-3 py-3" aria-label="Đang nhập">
                  {[0, 150, 300].map((d) => (
                    <span
                      key={d}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-faint"
                      style={{ animationDelay: `${d}ms` }}
                    />
                  ))}
                </div>
                <span className="text-xs text-ink-faint">{firstName} đang nhập…</span>
              </div>
            )}
          </div>
        )}
      </div>

      {newBelow && (
        <div className="relative">
          <button
            onClick={() => {
              scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
              setNewBelow(false);
            }}
            className="absolute -top-12 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-white shadow-lg"
          >
            Tin nhắn mới ↓
          </button>
        </div>
      )}

      {/* composer */}
      <div className="border-t border-line bg-white px-4 pb-3 pt-3 sm:px-6">
        <div className="flex items-end gap-2">
          <button
            onClick={() => setPickerOpen(true)}
            title="Chia sẻ một tin trọ"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] border border-line text-xl text-ink-soft hover:bg-tint"
          >
            +
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            title="Gửi ảnh"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] border border-line hover:bg-tint"
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden>
              <rect x="2.5" y="3.5" width="15" height="13" rx="2.5" stroke="#5b7189" strokeWidth="1.7" />
              <circle cx="7.5" cy="8" r="1.6" fill="#5b7189" />
              <path d="m3 15 4.5-4 3 2.5 3-3 3.5 3.5" stroke="#5b7189" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            multiple
            hidden
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = "";
              if (files.length) p.onSendImages(files);
            }}
          />
          <textarea
            ref={inputRef}
            rows={1}
            value={text}
            maxLength={2000}
            onChange={(e) => {
              setText(e.target.value);
              signalTyping(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={`Nhắn cho ${firstName}…`}
            className="min-h-[44px] flex-1 resize-none rounded-[10px] border border-line bg-paper px-4 py-[11px] text-[15px] leading-[22px] text-ink outline-none focus:border-primary-bright focus:bg-white"
          />
          <button
            onClick={submit}
            disabled={!text.trim()}
            className="h-11 shrink-0 rounded-[10px] bg-primary-bright px-5 font-semibold text-white transition hover:bg-primary disabled:opacity-40"
          >
            Gửi
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            onClick={() => setPickerOpen(true)}
            className="rounded-full border border-primary-ring bg-primary-soft px-3 py-1 text-xs font-medium text-primary hover:bg-primary-ring"
          >
            Chia sẻ một tin trọ
          </button>
          {QUICK.map((q) => (
            <button
              key={q.label}
              onClick={() => insertQuick(q.text)}
              className="rounded-full border border-primary-ring bg-primary-soft px-3 py-1 text-xs font-medium text-primary hover:bg-primary-ring"
            >
              {q.label}
            </button>
          ))}
        </div>
      </div>

      {pickerOpen && (
        <ListingPicker
          onPick={(id, snap) => {
            setPickerOpen(false);
            p.onSendListing(id, snap);
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}
      {lightbox && <Lightbox src={lightbox} onClose={() => setLightbox(null)} />}
    </div>
  );
}

