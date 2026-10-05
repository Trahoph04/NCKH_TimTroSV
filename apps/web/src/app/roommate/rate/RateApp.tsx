"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ProfileFacts, ProfileHeader } from "../ProfileSummary";
import type { RateCard, RateRes } from "../types";

const SCALE: [number, string][] = [
  [1, "Hoàn toàn không muốn ở chung"],
  [2, "Không muốn lắm"],
  [3, "Phân vân"],
  [4, "Khá muốn"],
  [5, "Rất muốn ở chung"],
];

export default function RateApp() {
  const [data, setData] = useState<RateRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/matching/rate", { cache: "no-store" });
      if (!r.ok) throw new Error();
      setData(await r.json());
      setErr(null);
    } catch {
      setErr("Không tải được thẻ chấm điểm. Thử lại sau.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function rate(card: RateCard, rating: number) {
    setSaving(card.card_code);
    // Cập nhật lạc quan, hoàn tác nếu lỗi: chấm 5 thẻ liên tiếp mà mỗi lần phải
    // chờ mạng trường thì người chấm bỏ dở giữa chừng.
    const prev = data;
    setData((d) =>
      d ? { ...d, items: d.items.map((i) => (i.card_code === card.card_code ? { ...i, rating } : i)) } : d,
    );
    try {
      const r = await fetch("/api/matching/rate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_code: card.card_code, rating }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(typeof d.detail === "string" ? d.detail : "Không lưu được điểm");
      }
      setErr(null);
    } catch (e) {
      setData(prev);
      setErr(e instanceof Error ? e.message : "Không lưu được điểm");
    } finally {
      setSaving(null);
    }
  }

  const done = data?.items.length ? data.items.every((i) => i.rating !== null) : false;
  const rated = data?.items.filter((i) => i.rating !== null).length ?? 0;

  return (
    <main className="flex-1 overflow-y-auto bg-paper">
      <div className="mx-auto max-w-3xl space-y-4 p-5">
        <Link href="/roommate?mode=random" className="text-sm font-medium text-primary">
          ← Về bộ thẻ
        </Link>
        <header className="rounded-2xl bg-white p-5">
          <h1 className="text-xl font-extrabold text-ink">Chấm điểm 5 hồ sơ</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Với mỗi hồ sơ, bạn <strong>muốn ở chung</strong> với người này tới mức nào? Không có
            đúng sai — chấm theo cảm nhận của bạn. Có thể đổi điểm tới khi rời trang.
          </p>
          {data && data.items.length > 0 && (
            <p className="mt-2 text-xs font-semibold text-ink-soft">
              Đã chấm {rated}/{data.items.length}
            </p>
          )}
        </header>

        {err && (
          <div className="flex items-center justify-between rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{err}</span>
            <button onClick={load} className="font-semibold underline">Thử lại</button>
          </div>
        )}

        {!data && !err && <p className="p-10 text-center text-sm text-ink-muted">Đang tải…</p>}

        {data && data.items.length === 0 && (
          <div className="rounded-2xl bg-white p-8 text-center text-sm text-ink-muted">
            {data.reason === "pool_empty"
              ? "Chưa có hồ sơ nào đi qua bộ lọc an toàn của bạn để chấm."
              : "Bạn cần điền đủ hồ sơ ở ghép trước khi chấm điểm."}{" "}
            <Link href="/roommate" className="font-semibold text-primary underline">Mở hồ sơ</Link>
          </div>
        )}

        {data?.items.map((c) => (
          <article key={c.card_code} className="overflow-hidden rounded-2xl bg-white shadow-sm">
            <div className="flex items-start justify-between gap-3 border-b border-line-soft p-5">
              <ProfileHeader p={c.profile} isSimulated={c.is_simulated} />
              {/* Mã thẻ để đối chiếu nếu phải chấm trên giấy — không mang thông tin nhóm */}
              <span className="shrink-0 rounded bg-tint px-2 py-1 font-mono text-xs text-ink-soft">
                {c.card_code}
              </span>
            </div>
            <div className="space-y-3 p-5">
              <ProfileFacts p={c.profile} />
            </div>
            <fieldset className="border-t border-line-soft p-4">
              <legend className="sr-only">Điểm cho thẻ {c.card_code}</legend>
              <div className="grid grid-cols-5 gap-2">
                {SCALE.map(([v, label]) => (
                  <button
                    key={v}
                    type="button"
                    disabled={saving === c.card_code}
                    aria-pressed={c.rating === v}
                    title={label}
                    onClick={() => rate(c, v)}
                    className={`rounded-xl border py-3 text-lg font-bold transition disabled:opacity-50 ${
                      c.rating === v
                        ? "border-primary bg-primary text-white"
                        : "border-line text-ink-soft hover:bg-tint"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-ink-faint">
                <span>{SCALE[0][1]}</span>
                <span>{SCALE[4][1]}</span>
              </div>
            </fieldset>
          </article>
        ))}

        {done && (
          <div className="rounded-2xl bg-green-50 p-5 text-center text-sm font-semibold text-green-800">
            Cảm ơn bạn! Đã ghi nhận đủ 5 điểm.
          </div>
        )}
      </div>
    </main>
  );
}
