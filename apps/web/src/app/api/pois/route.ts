import { NextResponse } from "next/server";
import { getPois, type ApiError } from "@/lib/api";

// Tiện ích OSM quanh 1 điểm cho bản đồ (public, chỉ proxy để browser không gọi khác origin).
export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const lat = Number(sp.get("lat"));
  const lng = Number(sp.get("lng"));
  const radius = Math.min(Number(sp.get("radius")) || 1000, 3000);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return NextResponse.json({ detail: "Thiếu lat/lng" }, { status: 400 });
  }
  try {
    return NextResponse.json(await getPois(lat, lng, radius));
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi tải tiện ích" }, { status: err.status ?? 500 });
  }
}
