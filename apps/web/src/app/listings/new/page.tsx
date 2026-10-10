import { requireAdminPage } from "@/lib/current-user";
import ListingForm from "../ListingForm";

export const dynamic = "force-dynamic";

// Chỉ admin nhập tin tay — sinh viên không đăng tin (ADR-024)
export default async function NewListingPage() {
  await requireAdminPage("/listings/new");
  return (
    <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="mx-auto max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-800">Thêm nhà trọ</h1>
        <div className="mt-6">
          <ListingForm mode="create" />
        </div>
      </div>
    </main>
  );
}
