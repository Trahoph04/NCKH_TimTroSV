"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import * as L from "./labels";
import ProfileForm from "./ProfileForm";
import { ProfileFacts, ProfileHeader } from "./ProfileSummary";
import type { DeckItem, DeckMode, DeckRes, LikeItem, ProfileRes } from "./types";

type Tab = "deck" | "likes" | "passed" | "profile";

export default function RoommateApp({
  me,
  mode = "ranked",
}: {
  me: { id: number; name: string };
  // "random" = buổi thử nghiệm: thứ tự ngẫu nhiên, KHÔNG hiện % hay lý do (thiết
  // kế 3.6). Server tự ẩn tín hiệu, FE chỉ cần gọi đúng mode.
  mode?: DeckMode;
}) {
  const [tab, setTab] = useState<Tab>("deck");
  const [prof, setProf] = useState<ProfileRes | null>(null);
  const [deck, setDeck] = useState<DeckRes | null>(null);
  const [likes, setLikes] = useState<LikeItem[]>([]);
  const [passed, setPassed] = useState<LikeItem[]>([]);
  // Mọi loader đều phải có trạng thái LỖI riêng: nuốt lỗi rồi render empty-state
  // sẽ nói dối người dùng ("chưa có ai phù hợp") khi thực ra API không gọi được.
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [matched, setMatched] = useState<{ convId: number; name: string } | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const r = await fetch("/api/matching/profile", { cache: "no-store" });
      if (!r.ok) throw new Error();
      setProf(await r.json());
      setErr(null);
    } catch {
      setErr("Không tải được hồ sơ. Thử lại sau.");
    }
  }, []);

  const loadDeck = useCallback(async () => {
    try {
      const r = await fetch(`/api/matching/deck?limit=10&mode=${mode}`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      setDeck(await r.json());
      setErr(null);
    } catch {
      setErr("Không tải được bộ thẻ. Thử lại sau.");
    }
  }, [mode]);

  const loadList = useCallback(async (which: "likes" | "passed") => {
    try {
      const r = await fetch(`/api/matching/${which}`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      const d = await r.json();
      (which === "likes" ? setLikes : setPassed)(d.items ?? []);
      setErr(null);
    } catch {
      setErr("Không tải được danh sách. Thử lại sau.");
    }
  }, []);

  useEffect(() => {
    void loadProfile();
    void loadDeck();
  }, [loadProfile, loadDeck]);

  useEffect(() => {
    if (tab === "likes") void loadList("likes");
    if (tab === "passed") void loadList("passed");
  }, [tab, loadList]);

  async function swipe(targetId: number, decision: "like" | "pass", name: string) {
    setBusy(true);
    try {
      const r = await fetch("/api/matching/swipe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // KHÔNG gửi deck_position/deck_mode: server đọc từ deck_log. Client tự
        // khai vị trí thẻ thì bằng chứng khử thiên lệch vị trí mất giá trị.
        body: JSON.stringify({ target_id: targetId, decision }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(typeof d.detail === "string" ? d.detail : "Không ghi được lựa chọn");
        return;
      }
      if (d.matched && d.conversation_id) setMatched({ convId: d.conversation_id, name });
      if (d.unmatched) void loadList("passed");
      // Bỏ thẻ vừa quyết khỏi deck tại chỗ, không chờ tải lại — tránh nhấp nháy
      setDeck((p) => (p ? { ...p, items: p.items.filter((i) => i.user_id !== targetId) } : p));
      setLikes((p) => p.filter((i) => i.user_id !== targetId));
      setErr(null);
    } catch {
      setErr("Không kết nối được máy chủ");
    } finally {
      setBusy(false);
    }
  }

  // Lời mời kèm lời nhắn = "Quan tâm" + một câu giới thiệu. Đi song song với
  // quẹt (thiết kế 2.10): match 2 chiều nhân đôi tỉ lệ rụng, lời nhắn cho người
  // kia lý do cụ thể để đáp lại.
  async function invite(targetId: number, note: string, name: string): Promise<boolean> {
    setBusy(true);
    try {
      const r = await fetch("/api/matching/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_id: targetId, note: note.trim() || null }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(typeof d.detail === "string" ? d.detail : "Không gửi được lời mời");
        return false;
      }
      if (d.matched && d.conversation_id) setMatched({ convId: d.conversation_id, name });
      setDeck((p) => (p ? { ...p, items: p.items.filter((i) => i.user_id !== targetId) } : p));
      setErr(null);
      return true;
    } catch {
      setErr("Không kết nối được máy chủ");
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (!prof) {
    return (
      <main className="p-10 text-center text-sm text-ink-muted">
        {err ? <ErrBox msg={err} onRetry={loadProfile} /> : "Đang tải…"}
      </main>
    );
  }

  if (tab === "profile" || !prof.profile || !prof.in_pool) {
    return (
      <main className="flex-1 overflow-y-auto bg-paper">
        {prof.profile && prof.in_pool && (
          <div className="mx-auto max-w-2xl px-5 pt-5">
            <button onClick={() => setTab("deck")} className="text-sm font-medium text-primary">
              ← Về bộ thẻ
            </button>
          </div>
        )}
        {!prof.in_pool && prof.profile && (
          <p className="mx-auto mt-5 max-w-2xl rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Hồ sơ còn thiếu <strong>giới tính</strong> hoặc phần lối sống, nên chưa vào
            được danh sách ghép. Điền tiếp giúp tụi mình nhé.
          </p>
        )}
        <ProfileForm
          initial={prof.profile}
          options={prof.options}
          onSaved={() => {
            void loadProfile();
            void loadDeck();
            setTab("deck");
          }}
        />
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-y-auto bg-paper">
      <div className="mx-auto max-w-3xl p-5">
        <nav className="mb-5 flex gap-1 rounded-xl bg-white p-1 text-sm font-medium shadow-sm">
          {([
            ["deck", `Bộ thẻ${deck?.items.length ? ` (${deck.items.length})` : ""}`],
            ["likes", `Lời mời${likes.length ? ` (${likes.length})` : ""}`],
            ["passed", "Đã bỏ qua"],
            ["profile", "Hồ sơ"],
          ] as [Tab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 rounded-lg px-3 py-2 transition ${
                tab === t ? "bg-primary text-white" : "text-ink-soft hover:bg-tint"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>

        {mode === "random" && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-tint px-4 py-3 text-sm text-ink-soft">
            <span>
              <strong>Buổi thử nghiệm:</strong> thẻ được xáo ngẫu nhiên và không hiện % tương thích.
            </span>
            <Link href="/roommate/rate" className="font-semibold text-primary underline">
              Chấm điểm 5 thẻ →
            </Link>
          </div>
        )}

        {err && <ErrBox msg={err} onRetry={tab === "deck" ? loadDeck : loadProfile} />}

        {tab === "deck" && (
          <>
            {deck && deck.items.length === 0 ? (
              <EmptyDeck reason={deck.reason} poolTotal={deck.pool_total} onRefresh={loadDeck} />
            ) : (
              <div className="space-y-4">
                {deck?.items.map((it) => (
                  <Card key={it.user_id} item={it} busy={busy} onSwipe={swipe} onInvite={invite} />
                ))}
              </div>
            )}
          </>
        )}

        {tab === "likes" && (
          <ListTab
            items={likes}
            empty="Chưa có ai gửi lời mời. Cứ quẹt tiếp ở Bộ thẻ nhé."
            action={(p) => (
              <div className="flex gap-2">
                <button
                  disabled={busy}
                  onClick={() => swipe(p.user_id, "pass", p.name || "Bạn ấy")}
                  className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink-soft disabled:opacity-50"
                >
                  Bỏ qua
                </button>
                <button
                  disabled={busy}
                  onClick={() => swipe(p.user_id, "like", p.name || "Bạn ấy")}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Quan tâm
                </button>
              </div>
            )}
          />
        )}

        {tab === "passed" && (
          <>
            <p className="mb-3 text-xs text-ink-muted">
              Bỏ qua <strong>không vĩnh viễn</strong>: sau 7 ngày thẻ sẽ quay lại bộ thẻ của bạn.
            </p>
            <ListTab
              items={passed}
              empty="Bạn chưa bỏ qua thẻ nào."
              action={(p) => (
                <button
                  disabled={busy}
                  onClick={() => swipe(p.user_id, "like", p.name || "Bạn ấy")}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Đổi ý — Quan tâm
                </button>
              )}
            />
          </>
        )}
      </div>

      {matched && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-5">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center">
            <p className="text-4xl">🎉</p>
            <h2 className="mt-2 text-xl font-extrabold text-ink">Thành đôi!</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Bạn và <strong>{matched.name}</strong> đều quan tâm nhau. Nhắn một câu
              chào để bắt đầu nhé.
            </p>
            <Link
              href={`/chat?c=${matched.convId}`}
              className="mt-4 block rounded-xl bg-primary py-3 font-semibold text-white"
            >
              Mở khung chat
            </Link>
            <button onClick={() => setMatched(null)} className="mt-2 w-full py-2 text-sm text-ink-muted">
              Để sau
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

function ErrBox({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
      <span>{msg}</span>
      <button onClick={onRetry} className="font-semibold underline">Thử lại</button>
    </div>
  );
}

function EmptyDeck({
  reason, poolTotal, onRefresh,
}: { reason: DeckRes["reason"]; poolTotal: number; onRefresh: () => void }) {
  // Mỗi `reason` là một hướng dẫn khác nhau. Dùng chung một câu "không có ai"
  // sẽ làm người dùng tưởng hệ thống rỗng, trong khi thật ra họ thiếu hồ sơ.
  const text =
    reason === "no_profile"
      ? "Bạn chưa có hồ sơ ở ghép. Điền 12 câu để bắt đầu."
      : reason === "profile_incomplete"
      ? "Hồ sơ còn thiếu giới tính hoặc phần lối sống."
      : reason === "deck_done"
      ? "Hết thẻ hôm nay rồi. Có bạn mới tụi mình báo bạn ngay."
      : "Chưa có ai đi qua được bộ lọc an toàn của bạn. Pool sẽ lớn dần khi có thêm bạn tham gia.";
  return (
    <div className="rounded-2xl bg-white p-8 text-center">
      <p className="text-3xl">🗂️</p>
      <p className="mt-3 font-semibold text-ink">{text}</p>
      {poolTotal > 0 && (
        <p className="mt-1 text-xs text-ink-muted">Pool sau lọc an toàn: {poolTotal} người</p>
      )}
      <button onClick={onRefresh} className="mt-4 text-sm font-semibold text-primary underline">
        Tải lại
      </button>
    </div>
  );
}

function Card({
  item, busy, onSwipe, onInvite,
}: {
  item: DeckItem;
  busy: boolean;
  onSwipe: (id: number, d: "like" | "pass", name: string) => void;
  onInvite: (id: number, note: string, name: string) => Promise<boolean>;
}) {
  const p = item.profile;
  const name = p?.name || "Sinh viên CTU";
  const [composing, setComposing] = useState(false);
  const [note, setNote] = useState("");
  return (
    <article className="overflow-hidden rounded-2xl bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-line-soft p-5">
        <ProfileHeader p={p} isSimulated={item.is_simulated} />
        {item.score !== null && (
          <div className="shrink-0 text-right">
            <p className="text-2xl font-extrabold text-primary">{Math.round(item.score * 100)}%</p>
            <p className="text-[11px] text-ink-faint">tương thích</p>
          </div>
        )}
      </div>

      <div className="space-y-3 p-5">
        <ProfileFacts p={p} />

        {item.reasons.length > 0 && (
          <ul className="space-y-1">
            {item.reasons.map((r) => (
              <li key={r} className="flex gap-2 text-sm text-ink-soft">
                <span className="text-green-600">●</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Vi phạm deal-breaker MỀM hiện rõ chữ và tách riêng khỏi "lưu ý" thường:
            người dùng đã nói rõ họ không chấp nhận điều đó, ẩn đi là lừa họ.
            Quyền quyết định vẫn thuộc về họ. */}
        {item.soft_flags.length > 0 ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            ⚠ Bạn ấy có {item.soft_flags.length} điều bạn từng nói không chấp nhận:{" "}
            <strong>{item.soft_flags.join(", ").toLowerCase()}</strong>
          </p>
        ) : (
          item.caveat && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">⚠ {item.caveat}</p>
          )
        )}
      </div>

      {composing && (
        <div className="space-y-2 border-t border-line-soft p-4">
          <label htmlFor={`note-${item.user_id}`} className="text-xs font-medium text-ink-soft">
            Lời nhắn kèm lời mời (không bắt buộc)
          </label>
          <textarea
            id={`note-${item.user_id}`}
            value={note}
            maxLength={300}
            rows={2}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Vd. Mình học Khu 2, cần phòng từ tháng sau, ngủ sớm…"
            className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setComposing(false)}
              className="rounded-lg px-3 py-2 text-sm text-ink-muted"
            >
              Huỷ
            </button>
            <button
              disabled={busy}
              onClick={async () => {
                if (await onInvite(item.user_id, note, name)) setComposing(false);
              }}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Gửi lời mời
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-2 border-t border-line-soft p-4">
        <button
          disabled={busy}
          onClick={() => onSwipe(item.user_id, "pass", name)}
          className="flex-1 rounded-xl border border-line py-3 font-semibold text-ink-soft transition hover:bg-tint disabled:opacity-50"
        >
          Bỏ qua
        </button>
        <button
          disabled={busy}
          onClick={() => setComposing((v) => !v)}
          title="Quan tâm kèm một lời nhắn"
          className="rounded-xl border border-primary px-4 py-3 text-sm font-semibold text-primary transition hover:bg-tint disabled:opacity-50"
        >
          ✉ Nhắn
        </button>
        <button
          disabled={busy}
          onClick={() => onSwipe(item.user_id, "like", name)}
          className="flex-1 rounded-xl bg-primary py-3 font-semibold text-white transition hover:bg-primary-bright disabled:opacity-50"
        >
          Quan tâm
        </button>
      </div>
    </article>
  );
}

function ListTab({
  items, empty, action,
}: { items: LikeItem[]; empty: string; action: (p: LikeItem) => React.ReactNode }) {
  if (items.length === 0) {
    return <div className="rounded-2xl bg-white p-8 text-center text-sm text-ink-muted">{empty}</div>;
  }
  return (
    <div className="space-y-3">
      {items.map((p) => (
        <div key={p.user_id} className="flex items-center justify-between gap-4 rounded-2xl bg-white p-4">
          <div>
            <p className="font-bold text-ink">{p.name || "Sinh viên CTU"}</p>
            <p className="text-sm text-ink-muted">
              {p.gender === "nam" ? "Nam" : p.gender === "nu" ? "Nữ" : "—"}
              {p.don_vi ? ` · ${p.don_vi}` : ""}
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              Giờ ngủ {L.at(L.SLEEP, p.sleep_time)} · {L.at(L.CLEAN, p.cleanliness)}
            </p>
            {p.note && (
              <p className="mt-2 rounded-lg bg-tint px-3 py-2 text-sm text-ink-soft">✉ “{p.note}”</p>
            )}
          </div>
          {action(p)}
        </div>
      ))}
    </div>
  );
}
