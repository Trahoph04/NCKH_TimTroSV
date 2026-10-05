"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { priceShort, profileRows } from "@/lib/chat/format";
import type { ContactState, Conversation, ConversationDetail } from "@/lib/chat/types";
import { Avatar } from "./ConversationList";

type Props = {
  conv: Conversation;
  detail?: ConversationDetail;
  online: boolean;
  onClose: () => void;
  onReport: () => void;
  onUnmatch: () => void;
};

// ----------------------------------------------------------------- T3
// Liên hệ chỉ hiện khi CẢ HAI bên bấm đồng ý (POST .../contact-consent).
// Panel tự hỏi /api/chat/conversations/{id}/contact-consent và tự giữ trạng
// thái, nên ChatApp không cần truyền thêm prop nào.

// 15s: không phải realtime, chỉ để người bấm TRƯỚC thấy trạng thái mở ra mà
// không phải F5. Nhịp dày hơn không đáng — hai bên thường bấm cách nhau vài giờ.
const CONSENT_POLL_MS = 15_000;

/** Số chữ ký đã có. Đồng ý là MỘT CHIỀU (không có endpoint rút lại) nên "nhiều
 *  chữ ký hơn" đồng nghĩa "mới hơn" — dùng để chọn giữa hai nguồn trạng thái. */
const consentRank = (s: ContactState) => (s.unlocked ? 3 : 0) + (s.mine ? 1 : 0) + (s.theirs ? 1 : 0);

export default function ProfilePanel({ conv, detail, online, onClose, onReport, onUnmatch }: Props) {
  const prof = detail?.partner_profile ?? null;
  const rows = profileRows(prof);
  const shared = detail?.shared_listings ?? [];

  // Gắn kèm id hội thoại thay vì xoá state trong useEffect: effect chạy SAU khi
  // render, nên cách kia còn đúng một frame hiện trạng thái đồng ý của người
  // TRƯỚC đó — đúng cái không được phép sai ở màn này.
  const [fetched, setFetched] = useState<{ id: number; state: ContactState } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const polled = fetched && fetched.id === conv.id ? fetched.state : null;
  // `detail` của ChatApp cũng có thể còn là hội thoại VỪA rời khỏi (nó tải không
  // đồng bộ) — so id trước khi dùng.
  const fromDetail =
    detail && detail.id === conv.id
      ? detail.contact ?? null
      : null;
  // Hai nguồn, lấy bản nhiều chữ ký hơn: ChatApp tải lại detail vì lý do khác
  // (tin mới đến) nên có thể biết "bên kia vừa đồng ý" trước nhịp poll 15s của
  // panel — mà cũng có thể ngược lại. Chọn bừa một nguồn là có cửa sổ hiện sai.
  let contact = polled ?? fromDetail;
  if (polled && fromDetail && consentRank(fromDetail) > consentRank(polled)) contact = fromDetail;

  useEffect(() => {
    setErr(null);
  }, [conv.id]);

  const pull = useCallback(async () => {
    try {
      const res = await fetch(`/api/chat/conversations/${conv.id}/contact-consent`, { cache: "no-store" });
      if (!res.ok) return;
      setFetched({ id: conv.id, state: (await res.json()) as ContactState });
    } catch {
      // Mạng rớt: giữ nguyên trạng thái đang hiện (đọc lại là vô hại), nhịp sau
      // thử tiếp. Không dựng cờ lỗi đỏ cho một lần đọc nền thất bại.
    }
  }, [conv.id]);

  const known = contact !== null;
  useEffect(() => {
    if (!known) void pull();
  }, [known, pull]);

  // Chỉ hỏi lại khi ĐANG CHỜ bên kia; đã mở hoặc chưa ai bấm thì không có gì để
  // chờ, poll tiếp chỉ là rác request.
  const waiting = contact?.waiting_for_other ?? false;
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(() => {
      if (!document.hidden) void pull();
    }, CONSENT_POLL_MS);
    return () => clearInterval(t);
  }, [waiting, pull]);

  const consent = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`/api/chat/conversations/${conv.id}/contact-consent`, {
        method: "POST",
        cache: "no-store",
      });
      if (!res.ok) throw new Error(String(res.status));
      setFetched({ id: conv.id, state: (await res.json()) as ContactState });
    } catch {
      setErr("Chưa gửi được. Kiểm tra mạng rồi bấm lại.");
    } finally {
      setBusy(false);
    }
  }, [conv.id]);

  const partner = contact?.partner ?? null;
  const firstName = conv.partner.name.split(" ").slice(-1)[0] || conv.partner.name;

  return (
    <div className="ml-auto flex h-full w-[86%] max-w-[320px] flex-col overflow-y-auto border-l border-line bg-white xl:ml-0 xl:w-full xl:max-w-none">
      <div className="flex justify-end p-2 xl:hidden">
        <button onClick={onClose} className="rounded-lg px-2 py-1 text-ink-muted hover:bg-tint" aria-label="Đóng">
          ✕
        </button>
      </div>

      <div className="flex flex-col items-center px-5 pb-5 pt-2 text-center xl:pt-6">
        <Avatar name={conv.partner.name} size={64} online={online} />
        <div className="mt-2 text-lg font-bold text-ink">{conv.partner.name}</div>
        <div className="text-sm text-ink-muted">{prof?.don_vi ?? conv.partner.don_vi ?? "Sinh viên CTU"}</div>
        {prof?.email_verified && (
          <span className="mt-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
            Tài khoản đã xác thực email
          </span>
        )}
        {(prof?.is_simulated ?? conv.partner.is_simulated) && (
          <span className="mt-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            Hồ sơ mô phỏng (dữ liệu demo)
          </span>
        )}
      </div>

      <section className="border-t border-line-soft px-5 py-4">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Hồ sơ ở ghép</h3>
        {rows.length === 0 && !prof?.bio ? (
          <p className="text-sm text-ink-faint">Bạn ấy chưa điền hồ sơ ở ghép.</p>
        ) : (
          <dl className="divide-y divide-line-soft text-sm">
            {rows.map((r) => (
              <div key={r.k} className="flex justify-between gap-3 py-2">
                <dt className="text-ink-muted">{r.k}</dt>
                <dd className="text-right font-semibold text-ink">{r.v}</dd>
              </div>
            ))}
          </dl>
        )}
        {prof?.bio && <p className="mt-2 rounded-lg bg-tint px-3 py-2 text-sm italic text-ink-soft">“{prof.bio}”</p>}
      </section>

      {/* -------------------------------------------------- T3: lộ liên hệ */}
      <section className="border-t border-line-soft px-5 py-4">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Thông tin liên hệ</h3>

        {contact === null ? (
          <p className="text-sm text-ink-faint">Đang kiểm tra…</p>
        ) : contact.unlocked && partner ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
            <div className="text-sm font-bold text-emerald-800">Cả hai đã đồng ý — đây là liên hệ của bạn ấy</div>
            <dl className="mt-2 space-y-2 text-sm">
              {partner.email && (
                <div>
                  <dt className="text-xs font-semibold text-emerald-900/70">Email</dt>
                  <dd>
                    <a href={`mailto:${partner.email}`} className="break-all font-semibold text-primary-bright underline">
                      {partner.email}
                    </a>
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-xs font-semibold text-emerald-900/70">Số điện thoại</dt>
                <dd>
                  {partner.phone ? (
                    <a href={`tel:${partner.phone}`} className="font-semibold text-primary-bright underline">
                      {partner.phone}
                    </a>
                  ) : (
                    // Phiếu khảo sát KHÔNG thu số điện thoại ⇒ phần lớn hồ sơ
                    // không có số. Nói thẳng ra, đừng vẽ nút Zalo chết.
                    <span className="text-ink-muted">Bạn ấy chưa nhập số — hẹn nhau qua email hoặc chat ở đây.</span>
                  )}
                </dd>
              </div>
            </dl>
            {partner.zalo_url && (
              <a
                href={partner.zalo_url}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-3 block rounded-[10px] bg-primary py-2 text-center text-sm font-semibold text-white hover:bg-primary-bright"
              >
                Mở Zalo
              </a>
            )}
            <p className="mt-2 text-[11px] leading-relaxed text-emerald-900/80">
              Bạn ấy cũng đang thấy email (và số điện thoại nếu bạn đã nhập) của bạn. MSSV của cả hai không được chia
              sẻ.
            </p>
          </div>
        ) : contact.waiting_for_other ? (
          <div className="rounded-xl border border-primary-ring bg-primary-soft p-3">
            <div className="text-sm font-bold text-navy">Đang chờ {firstName} đồng ý</div>
            <p className="mt-1 text-xs leading-relaxed text-ink-soft">
              Bạn đã đồng ý cho bạn ấy xem liên hệ của mình. Liên hệ của bạn ấy sẽ hiện ở đây ngay khi bạn ấy cũng bấm
              đồng ý — cần cả hai bên, không có cách nào xem một chiều.
            </p>
            <button
              onClick={() => void pull()}
              className="mt-2 rounded-[10px] border border-primary-ring bg-white px-3 py-1.5 text-xs font-semibold text-primary hover:bg-tint"
            >
              Kiểm tra lại
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-line bg-tint p-3">
            <p className="text-xs leading-relaxed text-ink-soft">
              Bây giờ bạn ấy chỉ thấy <strong>tên</strong> và <strong>tóm tắt thói quen sinh hoạt</strong> của bạn. Bấm
              đồng ý thì bạn ấy xem được <strong>email</strong> của bạn (và <strong>số điện thoại</strong> nếu bạn đã
              nhập trong hồ sơ). <strong>MSSV không bao giờ được chia sẻ.</strong>
            </p>
            <p className="mt-2 text-xs font-semibold leading-relaxed text-ink">
              Cần cả hai bên cùng đồng ý: bạn chỉ thấy liên hệ của bạn ấy sau khi bạn ấy cũng bấm.
            </p>
            {contact.theirs && (
              <p className="mt-2 rounded-lg bg-white px-2 py-1.5 text-xs font-semibold text-emerald-700">
                {firstName} đã đồng ý và đang chờ bạn.
              </p>
            )}
            <button
              onClick={() => void consent()}
              disabled={busy}
              className="mt-3 w-full rounded-[10px] bg-primary py-2 text-sm font-semibold text-white hover:bg-primary-bright disabled:opacity-60"
            >
              {busy ? "Đang gửi…" : "Cho phép bạn ấy xem liên hệ của bạn"}
            </button>
            {err && <p className="mt-2 text-xs font-semibold text-rose-600">{err}</p>}
          </div>
        )}
      </section>

      <section className="border-t border-line-soft px-5 py-4">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Tin đã chia sẻ</h3>
        {shared.length === 0 ? (
          <p className="text-sm text-ink-faint">Chưa có tin trọ nào — bấm “Chia sẻ một tin trọ” để gửi.</p>
        ) : (
          <ul className="space-y-2">
            {shared.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/listings/${s.payload.listing_id}`}
                  target="_blank"
                  className="flex gap-3 rounded-xl border border-line p-2 hover:bg-tint"
                >
                  <span className="photo-placeholder h-12 w-14 shrink-0 overflow-hidden rounded-lg">
                    {s.payload.image && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={s.payload.image} alt="" className="h-full w-full object-cover" />
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-sm font-semibold leading-snug text-ink">{s.payload.title}</span>
                    <span className="text-sm font-bold text-primary-bright">{priceShort(s.payload.price)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-auto space-y-3 px-5 pb-5 pt-2">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-left">
          <div className="text-sm font-bold text-amber-800">Nhắc an toàn</div>
          <p className="mt-1 text-xs leading-relaxed text-amber-900">
            Không chuyển tiền cọc qua chat. Hẹn gặp ở nơi công cộng hoặc đi xem phòng cùng nhau. Thấy dấu hiệu lừa
            đảo, hãy bấm Báo cáo.
          </p>
        </div>
        <p className="text-[11px] leading-relaxed text-ink-faint">
          Tin nhắn được lưu trên máy chủ của nhóm nghiên cứu, chỉ hai bạn xem được và sẽ bị xoá sau khi nghiệm thu đề
          tài (10/2026). Không dùng cho mục đích khác.
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onReport}
            className="rounded-[10px] border border-line py-2 text-sm font-semibold text-ink-soft hover:bg-tint"
          >
            Báo cáo
          </button>
          <button
            onClick={onUnmatch}
            className="rounded-[10px] border border-rose-200 py-2 text-sm font-semibold text-rose-600 hover:bg-rose-50"
          >
            Huỷ ghép
          </button>
        </div>
      </div>
    </div>
  );
}
