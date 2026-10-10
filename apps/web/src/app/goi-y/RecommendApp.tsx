"use client";

import Link from "next/link";
import { useState } from "react";
import { formatPrice, listingTags } from "@/lib/format";
import { CAMPUS_OPTIONS, FACTOR_OPTIONS, toPayload, type Criteria, type RecommendResult } from "@/lib/recommend";
import CriteriaForm from "./CriteriaForm";

const FACTOR_LABEL: Record<string, string> = Object.fromEntries(FACTOR_OPTIONS.map((f) => [f.value, f.label]));

export default function RecommendApp() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<RecommendResult | null>(null);
  const [campus, setCampus] = useState(1);

  async function run(c: Criteria) {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(c)),
      });
      if (!r.ok) throw new Error();
      setRes(await r.json());
      setCampus(c.campus);
    } catch {
      setErr("Không lấy được gợi ý. Thử lại sau.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto grid w-full max-w-[1160px] items-start gap-7 px-5 py-8 sm:px-10 lg:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-line bg-white p-5 lg:sticky lg:top-5">
        <h1 className="text-[19px] font-bold text-ink">Gợi ý phòng cho bạn</h1>
        <p className="mb-4 mt-1 text-[13.5px] text-ink-muted">
          Chọn tiêu chí — hệ thống xếp hạng tin trọ theo đúng những gì bạn cần và giải thích vì sao.
        </p>
        <CriteriaForm submitLabel="Gợi ý cho tôi" busy={busy} onSubmit={run} />
      </aside>

      <div className="flex flex-col gap-4">
        {err && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{err}</p>}
        {!res && !err && (
          <div className="rounded-2xl border border-dashed border-line bg-white px-6 py-14 text-center text-ink-muted">
            Chọn tiêu chí bên trái rồi bấm <b>Gợi ý cho tôi</b>.
          </div>
        )}

        {res && (
          <>
            <div className="flex flex-col gap-1">
              <h2 className="text-[20px] font-bold text-ink">{res.items.length} phòng phù hợp nhất</h2>
              <p className="text-sm text-ink-muted">
                Chọn từ {res.candidates} tin thoả ngân sách và thời gian đi; đã tránh gợi ý nhiều tin trùng một vị trí.
              </p>
              {res.relaxed.length > 0 && (
                <p className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-[13.5px] text-amber-800">
                  Có ít tin đúng hoàn toàn tiêu chí nên đã nới: {res.relaxed.join(", ")}.
                </p>
              )}
            </div>

            {res.items.map((it) => {
              const l = it.listing;
              const tags = listingTags(l);
              const approx = l.geocode_confidence !== "high";
              return (
                <article key={l.id} className="flex flex-col gap-4 rounded-2xl border border-line bg-white p-4 sm:flex-row">
                  {l.images[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={l.images[0]} alt="" loading="lazy" className="h-40 w-full shrink-0 rounded-xl object-cover sm:h-[132px] sm:w-[176px]" />
                  ) : (
                    <span className="photo-placeholder h-40 w-full shrink-0 rounded-xl sm:h-[132px] sm:w-[176px]" />
                  )}
                  <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="line-clamp-2 text-[16px] font-semibold leading-snug text-ink">{l.title}</h3>
                      <span
                        className="shrink-0 rounded-lg bg-primary-soft px-2.5 py-1 text-[13px] font-bold text-primary"
                        title="Mức phù hợp với tiêu chí bạn chọn"
                      >
                        {it.match}% phù hợp
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[17px] font-bold text-primary">{formatPrice(l.price)}</span>
                      {tags.map((t) => (
                        <span key={t.label} className={`rounded-md px-2 py-0.5 text-[12px] font-semibold ${t.className}`}>
                          {t.label}
                        </span>
                      ))}
                    </div>
                    {l.address && (
                      <p className="line-clamp-1 text-[13px] text-ink-muted">
                        {l.address}
                        {approx && " · vị trí tương đối"}
                      </p>
                    )}
                    <ul className="mt-1 flex flex-col gap-0.5 text-[13.5px] text-ink-soft">
                      {it.reasons.map((r) => (
                        <li key={r} className="flex gap-1.5">
                          <span className="text-emerald-600">✓</span>
                          {r}
                        </li>
                      ))}
                    </ul>
                    {it.ask.length > 0 && (
                      <p className="text-[13px] text-amber-700">Nên hỏi chủ trọ: {it.ask.join(", ")} (tin không ghi)</p>
                    )}
                    <Link href={`/listings/${l.id}`} className="mt-1 self-start text-sm font-semibold text-primary-bright hover:underline">
                      Xem chi tiết →
                    </Link>
                  </div>
                </article>
              );
            })}

            <details className="rounded-2xl border border-line bg-white px-5 py-4 text-[13.5px] text-ink-soft">
              <summary className="cursor-pointer font-semibold text-ink">Hệ thống xếp hạng như thế nào?</summary>
              <p className="mt-2">
                Mỗi tin được chấm theo các yếu tố sinh viên CTU quan tâm (khảo sát 31 bạn), có tính tới 3 điều bạn chọn.
                Trọng số lần này:
              </p>
              <ul className="mt-2 flex flex-col gap-1">
                {Object.entries(res.weights)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, w]) => (
                    <li key={k} className="flex items-center gap-2">
                      <span className="w-40 shrink-0">{FACTOR_LABEL[k] ?? k}</span>
                      <span className="h-2 rounded bg-primary/70" style={{ width: `${Math.round(w * 240)}px` }} />
                      <span className="text-ink-muted">{Math.round(w * 100)}%</span>
                    </li>
                  ))}
              </ul>
              <p className="mt-2 text-ink-muted">
                Thời gian đi tính theo đường thật tới {CAMPUS_OPTIONS[campus]} (OpenRouteService). Tiện ích tin không ghi được
                tính là &ldquo;chưa rõ&rdquo;, không bị coi là không có. &ldquo;An ninh khu vực&rdquo; chưa có dữ liệu nên
                chưa tính.
              </p>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
