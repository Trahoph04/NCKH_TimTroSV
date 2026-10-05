"use client";

import { useMemo, useState } from "react";
import { initials, listTime, previewText, profileChips, scoreText } from "@/lib/chat/format";
import type { Conversation, Like, Me } from "@/lib/chat/types";

export function Avatar({
  name,
  size = 48,
  online,
  className = "",
}: {
  name: string;
  size?: number;
  online?: boolean;
  className?: string;
}) {
  return (
    <span className={`relative inline-flex shrink-0 ${className}`} style={{ width: size, height: size }}>
      <span
        className="flex h-full w-full items-center justify-center rounded-full bg-primary-soft font-bold text-primary"
        style={{ fontSize: Math.round(size * 0.34) }}
      >
        {initials(name)}
      </span>
      {online !== undefined && (
        <span
          className={`absolute bottom-0 right-0 rounded-full border-2 border-white ${online ? "bg-emerald-500" : "bg-slate-300"}`}
          style={{ width: Math.max(10, size * 0.26), height: Math.max(10, size * 0.26) }}
          aria-label={online ? "Đang hoạt động" : "Ngoại tuyến"}
        />
      )}
    </span>
  );
}

type Props = {
  me: Me;
  convs: Conversation[];
  loading: boolean;
  activeId: number | null;
  onSelect: (id: number) => void;
  tab: "matched" | "likes";
  onTab: (t: "matched" | "likes") => void;
  likes: Like[];
  onRespond: (like: Like, decision: "like" | "pass") => void;
  online: Record<number, boolean>;
  typing: Record<number, number>;
};

export default function ConversationList(p: Props) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();

  const filtered = useMemo(
    () =>
      p.convs.filter(
        (c) =>
          !query ||
          c.partner.name.toLowerCase().includes(query) ||
          (c.last_message?.body ?? "").toLowerCase().includes(query),
      ),
    [p.convs, query],
  );
  const fresh = filtered.filter((c) => c.user_message_count === 0);
  const talking = filtered.filter((c) => c.user_message_count > 0);
  const unreadTotal = p.convs.reduce((s, c) => s + c.unread, 0);
  const isOnline = (c: Conversation) => p.online[c.partner.id] ?? Boolean(c.partner.online);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-3 px-5 pb-3 pt-5">
        <h1 className="text-xl font-extrabold text-ink">Tin nhắn</h1>
        <label className="flex items-center gap-2 rounded-[10px] border border-line bg-paper px-3 py-2">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden>
            <circle cx="9" cy="9" r="6.2" stroke="#5b7189" strokeWidth="1.8" />
            <line x1="13.6" y1="13.6" x2="17.5" y2="17.5" stroke="#5b7189" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm bạn hoặc tin nhắn…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
        <div className="grid grid-cols-2 rounded-[10px] bg-tint p-1 text-sm font-semibold">
          {(
            [
              ["matched", "Đã ghép", unreadTotal],
              ["likes", "Lời mời", p.likes.length],
            ] as const
          ).map(([key, label, count]) => (
            <button
              key={key}
              onClick={() => p.onTab(key)}
              className={`flex items-center justify-center gap-1.5 rounded-lg py-2 transition ${
                p.tab === key ? "bg-white text-primary shadow-sm" : "text-ink-muted hover:text-ink"
              }`}
            >
              {label}
              {count > 0 && (
                <span className="rounded-full bg-primary px-1.5 text-[11px] leading-[18px] text-white">{count}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {p.tab === "likes" ? (
          <LikesList likes={p.likes} onRespond={p.onRespond} />
        ) : p.loading ? (
          <ListSkeleton />
        ) : p.convs.length === 0 ? (
          <p className="px-3 py-10 text-center text-sm text-ink-muted">
            Chưa có ai ghép đôi. Khi hai bạn cùng thích nhau, cuộc trò chuyện sẽ hiện ở đây.
          </p>
        ) : (
          <>
            {fresh.length > 0 && (
              <div className="mb-2 px-2">
                <div className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Mới ghép</div>
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {fresh.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => p.onSelect(c.id)}
                      className={`flex w-[68px] shrink-0 flex-col items-center gap-1 rounded-xl p-1 ${
                        p.activeId === c.id ? "bg-primary-soft" : "hover:bg-tint"
                      }`}
                    >
                      <span className="rounded-full ring-2 ring-primary ring-offset-2">
                        <Avatar name={c.partner.name} size={52} online={isOnline(c)} />
                      </span>
                      <span className="w-full truncate text-center text-xs font-semibold text-ink">
                        {c.partner.name.split(" ").slice(-1)[0]}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {talking.length > 0 && fresh.length > 0 && (
              <div className="mb-1 px-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Trò chuyện</div>
            )}
            <ul className="space-y-1">
              {talking.map((c) => {
                const active = p.activeId === c.id;
                const typingNow = (p.typing[c.id] ?? 0) > Date.now();
                const score = scoreText(c.score);
                return (
                  <li key={c.id}>
                    <button
                      onClick={() => p.onSelect(c.id)}
                      className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition ${
                        active ? "border-primary-ring bg-primary-soft" : "border-transparent hover:bg-tint"
                      }`}
                    >
                      <Avatar name={c.partner.name} online={isOnline(c)} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline justify-between gap-2">
                          <span className={`truncate text-[15px] text-ink ${c.unread ? "font-extrabold" : "font-bold"}`}>
                            {c.partner.name}
                          </span>
                          <span className="shrink-0 text-xs text-ink-faint">
                            {c.last_message ? listTime(c.last_message.created_at) : ""}
                          </span>
                        </span>
                        <span className="mt-0.5 flex items-center justify-between gap-2">
                          <span
                            className={`truncate text-sm ${
                              typingNow ? "italic text-primary" : c.unread ? "font-semibold text-ink" : "text-ink-muted"
                            }`}
                          >
                            {typingNow ? "Đang nhập…" : previewText(c, p.me.id)}
                          </span>
                          {c.unread > 0 && (
                            <span className="shrink-0 rounded-full bg-primary px-1.5 text-[11px] font-bold leading-[18px] text-white">
                              {c.unread > 99 ? "99+" : c.unread}
                            </span>
                          )}
                        </span>
                        {(score || c.partner.don_vi) && (
                          <span className="mt-0.5 block truncate text-xs text-emerald-700">
                            {[score && `Ghép ${score}`, c.partner.don_vi].filter(Boolean).join(" · ")}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {filtered.length === 0 && (
              <p className="px-3 py-8 text-center text-sm text-ink-muted">Không tìm thấy “{q}”.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function LikesList({ likes, onRespond }: { likes: Like[]; onRespond: Props["onRespond"] }) {
  if (likes.length === 0)
    return (
      <p className="px-3 py-10 text-center text-sm text-ink-muted">
        Chưa có lời mời mới. Ai thích hồ sơ của bạn sẽ hiện ở đây — bạn thích lại là hai bạn ghép đôi.
      </p>
    );
  return (
    <ul className="space-y-3 px-1">
      {likes.map((l) => (
        <li key={l.user_id} className="rounded-2xl border border-line bg-white p-4">
          <div className="flex items-center gap-3">
            <Avatar name={l.name} size={44} />
            <div className="min-w-0">
              <div className="truncate font-bold text-ink">{l.name}</div>
              <div className="truncate text-xs text-ink-muted">{l.don_vi ?? "Sinh viên CTU"}</div>
            </div>
            {l.is_simulated && (
              <span className="ml-auto shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                Hồ sơ mô phỏng
              </span>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {profileChips(l).map((c) => (
              <span key={c} className="rounded-full bg-tint px-2 py-0.5 text-xs text-ink-soft">
                {c}
              </span>
            ))}
          </div>
          {l.bio && <p className="mt-2 line-clamp-2 text-sm text-ink-soft">“{l.bio}”</p>}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => onRespond(l, "pass")}
              className="rounded-[10px] border border-line py-2 text-sm font-semibold text-ink-soft hover:bg-tint"
            >
              Bỏ qua
            </button>
            <button
              onClick={() => onRespond(l, "like")}
              className="rounded-[10px] bg-primary py-2 text-sm font-semibold text-white hover:bg-navy"
            >
              Thích lại
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ListSkeleton() {
  return (
    <ul className="space-y-2 px-2 pt-2" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <li key={i} className="flex animate-pulse items-center gap-3 py-2">
          <span className="h-12 w-12 rounded-full bg-line-soft" />
          <span className="flex-1 space-y-2">
            <span className="block h-3 w-1/2 rounded bg-line-soft" />
            <span className="block h-3 w-3/4 rounded bg-line-soft" />
          </span>
        </li>
      ))}
    </ul>
  );
}
