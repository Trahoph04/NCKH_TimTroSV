import type { ContactOut } from "@/lib/api";
import { formatPhone, sourceName } from "@/lib/format";

// Có số → hiện số (bấm để gọi) + Zalo/Facebook nếu có; không có số → đưa sang tin gốc trên trang nguồn.
export default function ContactBox({ contact }: { contact: ContactOut | null }) {
  if (!contact) return null;
  const btn = "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition";
  return (
    <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-800">Liên hệ chủ trọ</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {contact.phone && (
          <a href={`tel:${contact.phone}`} className={`${btn} bg-emerald-600 text-white hover:bg-emerald-700`}>
            📞 {formatPhone(contact.phone)}
          </a>
        )}
        {contact.zalo && (
          <a
            href={`https://zalo.me/${contact.zalo}`}
            target="_blank"
            rel="noopener noreferrer"
            className={`${btn} border border-sky-300 bg-white text-sky-700 hover:bg-sky-50`}
          >
            Zalo
          </a>
        )}
        {contact.facebook && (
          <a
            href={contact.facebook}
            target="_blank"
            rel="noopener noreferrer"
            className={`${btn} border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50`}
          >
            Facebook
          </a>
        )}
        {contact.source_url && (
          <a
            href={contact.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className={
              contact.phone || contact.zalo || contact.facebook
                ? "text-sm text-emerald-700 hover:underline"
                : `${btn} bg-emerald-600 text-white hover:bg-emerald-700`
            }
          >
            Xem tin gốc trên {sourceName(contact.source_url)} ↗
          </a>
        )}
        {!contact.phone && !contact.zalo && !contact.facebook && !contact.source_url && (
          <span className="text-sm text-slate-500">Chưa có thông tin liên hệ</span>
        )}
      </div>
      {!contact.phone && contact.source_url && (
        <p className="mt-2 text-xs text-slate-500">
          Tin không ghi số điện thoại — số liên hệ nằm trên trang nguồn.
        </p>
      )}
    </div>
  );
}
