import Link from "next/link";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/current-user";
import SiteHeader from "../SiteHeader";
import LogoutButton from "./LogoutButton";

export const dynamic = "force-dynamic";

export default async function MePage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <SiteHeader />
      <main className="flex flex-1 items-start justify-center p-4 pt-16">
        <div className="w-full max-w-md rounded-2xl border border-line bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-extrabold text-ink">Tài khoản của tôi</h1>

          <div className="mt-6 flex items-center gap-4">
            {user.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatar_url} alt={user.name ?? user.email} className="h-16 w-16 rounded-full object-cover" />
            ) : (
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-xl font-bold text-primary">
                {(user.name || user.email).slice(0, 1).toUpperCase()}
              </span>
            )}
            <div className="min-w-0">
              <p className="truncate text-lg font-semibold text-ink">{user.name || "—"}</p>
              <p className="truncate text-sm text-ink-muted">{user.email}</p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-2">
            <Link href="/chat" className="rounded-[10px] bg-primary py-2.5 text-center font-semibold text-white hover:bg-navy">
              Tin nhắn
            </Link>
            <Link href="/" className="rounded-[10px] border border-line py-2.5 text-center font-semibold text-ink-soft hover:bg-tint">
              Tìm trọ
            </Link>
          </div>
          <div className="mt-4 border-t border-line-soft pt-4">
            <LogoutButton />
          </div>
        </div>
      </main>
    </div>
  );
}
