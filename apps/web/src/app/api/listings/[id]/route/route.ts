import { NextResponse } from "next/server";
import { getListingRoute, type ApiError } from "@/lib/api";

// Đường đi khu CTU → tin cho bản đồ. Proxy vì FastAPI không bật CORS: browser gọi thẳng :8000
// kèm Content-Type JSON sẽ bị preflight chặn.
export async function GET(req: Request, { params }: { params: { id: string } }) {
  const campus = Number(new URL(req.url).searchParams.get("campus") ?? 1);
  try {
    return NextResponse.json(await getListingRoute(params.id, campus));
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi lấy đường đi" }, { status: err.status ?? 500 });
  }
}
