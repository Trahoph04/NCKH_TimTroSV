import { notFound, redirect } from "next/navigation";
import { getListing, type ApiError } from "@/lib/api";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import ListingForm from "../../ListingForm";

export const dynamic = "force-dynamic";

export default async function EditListingPage({
  params,
}: {
  params: { id: string };
}) {
  const user = await getCurrentUser();
  if (!user) {
    redirect(reauthUrl(`/listings/${params.id}/edit`));
  }

  let listing;
  try {
    listing = await getListing(params.id);
  } catch (e) {
    if ((e as ApiError).status === 404) notFound();
    throw e;
  }

  return (
    <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="mx-auto max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-800">Sửa tin</h1>
        <div className="mt-6">
          <ListingForm
            mode="edit"
            listingId={listing.id}
            initial={{
              title: listing.title,
              price: listing.price,
              area: listing.area,
              address: listing.address,
              district: listing.district,
              description: listing.description,
              images: listing.images,
            }}
          />
        </div>
      </div>
    </main>
  );
}
