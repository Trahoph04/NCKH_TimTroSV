import { NextResponse } from "next/server";
import { getListingContact, type ApiError } from "@/lib/api";

// Liên hệ của 1 tin cho thẻ tin trên bản đồ (client component) — proxy vì FastAPI không bật CORS.
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  // id phải là số — lib/api.ts ghép thẳng id vào URL API
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  try {
    return NextResponse.json(await getListingContact(params.id));
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi lấy liên hệ" }, { status: err.status ?? 500 });
  }
}
