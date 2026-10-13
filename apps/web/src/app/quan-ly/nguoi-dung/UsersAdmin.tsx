"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type AdminUser = {
  id: number;
  email: string;
  name: string | null;
  role: string;
  created_at: string | null;
  last_seen_at: string | null;
  locked: boolean;
  providers: string[];
  mssv: string | null;
  has_roommate_profile: boolean;
};
type Page = { total: number; page: number; size: number; items: AdminUser[] };
type Filter = "" | "admin" | "locked";

const SIZE = 20;
const FILTERS: { value: Filter; label: string }[] = [
  { value: "", label: "Tất cả" },
  { value: "admin", label: "Admin" },
  { value: "locked", label: "Đang bị khoá" },
];
const PROVIDER_LABEL: Record<string, string> = { local: "Email", google: "Google", ctu: "MSSV" };

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function UsersAdmin({ currentUserId }: { currentUserId: number }) {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  // Hành động đổi quyền/khoá cần bấm 2 lần (lần đầu hiện "Xác nhận?") — không dùng window.confirm
  const [confirm, setConfirm] = useState<string | null>(null);
  const latest = useRef(0);

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ page: String(page), size: String(SIZE) });
    if (query) qs.set("q", query);
    if (filter === "admin") qs.set("role", "admin");
    if (filter === "locked") qs.set("locked", "true");
    const ticket = ++latest.current;
    try {
      const res = await fetch(`/api/admin/users?${qs}`, { cache: "no-store" });
      const body = await res.json().catch(() => ({}));
      if (ticket !== latest.current) return; // đổi bộ lọc nhanh: kết quả cũ về muộn không được đè
      if (!res.ok) {
        setError(typeof body.detail === "string" ? body.detail : "Không tải được danh sách");
        return;
      }
      setData(body as Page);
      setError(null);
    } catch {
      if (ticket === latest.current) setError("Không kết nối được máy chủ");
    }
  }, [page, query, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function update(user: AdminUser, change: { role?: string; locked?: boolean }) {
    setBusyId(user.id);
    setConfirm(null);
    try {
      const res = await fetch(`/api/admin/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(change),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof body.detail === "string" ? body.detail : "Không cập nhật được");
        return;
      }
      setError(null);
      setData((d) => (d ? { ...d, items: d.items.map((u) => (u.id === user.id ? (body as AdminUser) : u)) } : d));
    } catch {
      setError("Không kết nối được máy chủ");
    } finally {
      setBusyId(null);
    }
  }

  function action(user: AdminUser, key: string, label: string, change: { role?: string; locked?: boolean }, danger = false) {
    const id = `${user.id}:${key}`;
    const asking = confirm === id;
    return (
      <button
        type="button"
        disabled={busyId === user.id}
        onClick={() => (asking ? void update(user, change) : setConfirm(id))}
        onBlur={() => setConfirm((cur) => (cur === id ? null : cur))}
        className={`rounded-lg border px-2.5 py-1 text-xs font-semibold transition disabled:opacity-50 ${
          asking
            ? "border-rose-500 bg-rose-500 text-white"
            : danger
            ? "border-rose-200 text-rose-600 hover:bg-rose-50"
            : "border-line text-ink-soft hover:border-primary-ring hover:text-primary"
        }`}
      >
        <span aria-live="polite">{asking ? "Bấm lần nữa để xác nhận" : label}</span>
      </button>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / SIZE)) : 1;

  return (
    <div className="mt-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setQuery(q.trim());
        }}
        className="flex flex-col gap-3 sm:flex-row sm:items-center"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm theo email, tên hoặc MSSV"
          aria-label="Tìm người dùng"
          className="w-full rounded-[10px] border border-line bg-white px-3.5 py-2.5 text-sm outline-none focus:border-primary-ring sm:max-w-sm"
        />
        <button type="submit" className="rounded-[10px] bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy">
          Tìm
        </button>
        <div className="flex gap-1.5" role="group" aria-label="Lọc người dùng">
          {FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              type="button"
              onClick={() => {
                setPage(1);
                setFilter(f.value);
              }}
              className={`rounded-full border px-3 py-1 text-[13px] transition ${
                filter === f.value
                  ? "border-primary bg-primary-soft font-semibold text-primary"
                  : "border-line text-ink-soft hover:border-primary-ring"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </form>

      {error && <p className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</p>}

      {data && (
        <p className="mt-4 text-sm text-ink-muted">
          {data.total} người dùng{query ? ` khớp “${query}”` : ""}
        </p>
      )}

      {data && data.items.length === 0 && (
        <p className="mt-8 text-center text-ink-muted">Không có người dùng nào khớp.</p>
      )}

      <ul className="mt-3 flex flex-col gap-2.5">
        {data?.items.map((u) => {
          const self = u.id === currentUserId;
          return (
            <li
              key={u.id}
              className={`flex flex-col gap-3 rounded-[13px] border bg-white p-4 sm:flex-row sm:items-center sm:justify-between ${
                u.locked ? "border-rose-200" : "border-line-soft"
              }`}
            >
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-semibold text-ink">{u.name || "(chưa đặt tên)"}</span>
                  {u.role === "admin" && (
                    <span className="rounded-md bg-primary-soft px-1.5 py-0.5 text-[11.5px] font-semibold text-primary">Admin</span>
                  )}
                  {u.locked && (
                    <span className="rounded-md bg-rose-50 px-1.5 py-0.5 text-[11.5px] font-semibold text-rose-600">Đã khoá</span>
                  )}
                  {self && <span className="text-[12px] text-ink-faint">(bạn)</span>}
                </p>
                <p className="truncate text-sm text-ink-soft">{u.email}</p>
                <p className="mt-0.5 text-[12.5px] text-ink-muted">
                  {[
                    u.providers.map((p) => PROVIDER_LABEL[p] ?? p).join(", ") || "—",
                    u.mssv ? `MSSV ${u.mssv}` : null,
                    u.has_roommate_profile ? "có hồ sơ ở ghép" : null,
                    `tạo ${fmtDate(u.created_at)}`,
                    u.last_seen_at ? `hoạt động ${fmtDate(u.last_seen_at)}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              {!self && (
                <div className="flex shrink-0 flex-wrap gap-2">
                  {u.role === "admin"
                    ? action(u, "demote", "Bỏ quyền admin", { role: "user" })
                    : action(u, "promote", "Cấp quyền admin", { role: "admin" })}
                  {u.locked
                    ? action(u, "unlock", "Mở khoá", { locked: false })
                    : action(u, "lock", "Khoá tài khoản", { locked: true }, true)}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {data && totalPages > 1 && (
        <div className="mt-5 flex items-center justify-center gap-3 text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40"
          >
            ← Trước
          </button>
          <span className="text-ink-muted">
            Trang {page}/{totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40"
          >
            Sau →
          </button>
        </div>
      )}
    </div>
  );
}
