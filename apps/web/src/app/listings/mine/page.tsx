import Link from "next/link";
import { redirect } from "next/navigation";
import { getMyListings, type ApiError, type ListingOut } from "@/lib/api";
import { getAccessToken } from "@/lib/session";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import ListingCard from "@/app/ListingCard";

export const dynamic = "force-dynamic";

export default async function MyListingsPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect(reauthUrl("/listings/mine"));
  }

  const token = getAccessToken();
  let items: ListingOut[] = [];
  let errorMessage: string | null = null;
  try {
    items = token ? await getMyListings(token) : [];
  } catch (e) {
    errorMessage = (e as ApiError).detail ?? "Không thể tải tin của bạn";
  }

  return (
    <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-bold text-slate-800">Tin của tôi</h1>

        {errorMessage && (
          <p className="mt-6 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">
            {errorMessage}
          </p>
        )}

        {!errorMessage && items.length === 0 && (
          <p className="mt-10 text-center text-slate-500">
            Bạn chưa đăng tin nào —{" "}
            <Link href="/listings/new" className="text-emerald-600 hover:text-emerald-700">
              đăng tin ngay
            </Link>
          </p>
        )}

        {items.length > 0 && (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((listing) => (
              <div key={listing.id} className="relative">
                <ListingCard listing={listing} />
                <Link
                  href={`/listings/${listing.id}/edit`}
                  className="absolute right-2 top-2 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-emerald-700 shadow-sm hover:bg-white"
                >
                  Sửa
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
