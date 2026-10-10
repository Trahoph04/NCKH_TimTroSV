import { NextResponse } from "next/server";
import { getPoiSummary, type ApiError } from "@/lib/api";

export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const lat = Number(sp.get("lat"));
  const lng = Number(sp.get("lng"));
  const radius = Math.min(Number(sp.get("radius")) || 1000, 3000);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return NextResponse.json({ detail: "Thiếu lat/lng" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getPoiSummary(lat, lng, radius));
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi tải tiện ích" }, { status: err.status ?? 500 });
  }
}
