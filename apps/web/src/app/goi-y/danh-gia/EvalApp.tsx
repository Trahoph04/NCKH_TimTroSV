"use client";

import { useCallback, useEffect, useState } from "react";
import { formatPrice, listingTags } from "@/lib/format";
import { CAMPUS_OPTIONS, toPayload, type Criteria, type EvalCard, type EvalSession } from "@/lib/recommend";
import CriteriaForm from "../CriteriaForm";

const SCALE: [number, string, string][] = [
  [0, "Không quan tâm", "border-line text-ink-soft"],
  [1, "Có thể xem thử", "border-amber-300 text-amber-800"],
  [2, "Sẽ liên hệ", "border-emerald-400 text-emerald-800"],
];
const ACTIVE: Record<number, string> = {
  0: "bg-slate-600 text-white border-slate-600",
  1: "bg-amber-500 text-white border-amber-500",
  2: "bg-emerald-600 text-white border-emerald-600",
};

export default function EvalApp() {
  const [sess, setSess] = useState<EvalSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [newRound, setNewRound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/recommend/eval/session", { cache: "no-store" });
      if (!r.ok) throw new Error();
      setSess(await r.json());
    } catch {
      setErr("Không tải được lượt đánh giá. Thử lại sau.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function start(c: Criteria) {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/recommend/eval/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(c)),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(typeof d.detail === "string" ? d.detail : "Không tạo được lượt đánh giá");
      }
      setSess(await r.json());
      setNewRound(false);
      window.scrollTo({ top: 0 });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không tạo được lượt đánh giá");
    } finally {
      setBusy(false);
    }
  }

  async function judge(card: EvalCard, relevance: number) {
    if (!sess) return;
    // Cập nhật lạc quan, hoàn tác nếu lỗi — chờ mạng trường sau mỗi thẻ thì người chấm bỏ dở.
    const prev = sess;
    const cards = sess.cards.map((c) => (c.card_code === card.card_code ? { ...c, relevance } : c));
    const judged = cards.filter((c) => c.relevance !== null).length;
    setSess({ ...sess, cards, judged, completed: judged === cards.length });
    try {
      const r = await fetch("/api/recommend/eval/judge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_code: card.card_code, relevance }),
      });
      if (!r.ok) throw new Error();
      setErr(null);
    } catch {
      setSess(prev);
      setErr("Không lưu được, bấm lại giúp mình.");
    }
  }

  if (loading) return <p className="px-5 py-10 text-center text-ink-muted">Đang tải…</p>;

  const showForm = !sess || newRound;
  return (
    <section className="mx-auto flex w-full max-w-[860px] flex-col gap-5 px-5 py-8">
      <div>
        <h1 className="text-[22px] font-bold text-ink">Đánh giá gợi ý phòng</h1>
        <p className="mt-1 text-[14px] text-ink-muted">
          Phiếu đánh giá hệ gợi ý của đề tài NCKH. Hãy chọn tiêu chí như khi bạn tìm phòng thật; sau đó với mỗi tin, cho biết
          bạn có liên hệ chủ trọ không. Thứ tự các tin là ngẫu nhiên.
        </p>
      </div>
      {err && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{err}</p>}

      {showForm ? (
        <div className="rounded-2xl border border-line bg-white p-5">
          <CriteriaForm submitLabel="Bắt đầu đánh giá" busy={busy} onSubmit={start} />
        </div>
      ) : (
        sess && (
          <>
            <div className="sticky top-0 z-10 flex flex-col gap-2 rounded-xl border border-line bg-white/95 px-4 py-3 backdrop-blur">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-ink">
                  Đã đánh giá {sess.judged}/{sess.cards.length} tin
                </span>
                {sess.completed && <span className="font-semibold text-emerald-700">Xong — cảm ơn bạn!</span>}
              </div>
              <div className="h-2 overflow-hidden rounded bg-tint">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${(100 * sess.judged) / Math.max(1, sess.cards.length)}%` }}
                />
              </div>
            </div>

            {sess.cards.map((card) => {
              const l = card.listing;
              const tags = listingTags(l);
              return (
                <article key={card.card_code} className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:flex-row">
                  {l.images[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={l.images[0]} alt="" loading="lazy" className="h-40 w-full shrink-0 rounded-xl object-cover sm:h-[120px] sm:w-[160px]" />
                  ) : (
                    <span className="photo-placeholder h-40 w-full shrink-0 rounded-xl sm:h-[120px] sm:w-[160px]" />
                  )}
                  <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <h3 className="line-clamp-2 text-[15.5px] font-semibold leading-snug text-ink">{l.title}</h3>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[16px] font-bold text-primary">{formatPrice(l.price)}</span>
                      {tags.map((t) => (
                        <span key={t.label} className={`rounded-md px-2 py-0.5 text-[12px] font-semibold ${t.className}`}>
                          {t.label}
                        </span>
                      ))}
                    </div>
                    <p className="text-[13px] text-ink-muted">
                      {[
                        l.area != null ? `${l.area} m²` : null,
                        card.minutes != null ? `${Math.round(card.minutes)} phút tới ${CAMPUS_OPTIONS[sess.campus].replace("Khu", "khu")}` : null,
                        l.district,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    {l.address && <p className="line-clamp-1 text-[13px] text-ink-faint">{l.address}</p>}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {SCALE.map(([v, label, cls]) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => void judge(card, v)}
                          className={`rounded-[9px] border px-3 py-1.5 text-[13.5px] font-medium transition ${
                            card.relevance === v ? ACTIVE[v] : `${cls} hover:bg-paper`
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                      <a
                        href={`/listings/${l.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-auto text-[13px] font-medium text-primary-bright hover:underline"
                      >
                        Xem chi tiết ↗
                      </a>
                    </div>
                    <span className="text-[11px] text-ink-faint">Mã thẻ {card.card_code}</span>
                  </div>
                </article>
              );
            })}

            {sess.completed && (
              <button
                type="button"
                onClick={() => setNewRound(true)}
                className="self-center rounded-[11px] border border-primary px-5 py-2.5 text-sm font-semibold text-primary hover:bg-primary-soft"
              >
                Đánh giá thêm với tiêu chí khác
              </button>
            )}
          </>
        )
      )}
    </section>
  );
}
