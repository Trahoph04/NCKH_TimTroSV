import { NextResponse } from "next/server";
import { proxyToApi } from "@/lib/proxy";

// Đánh giá của chính mình cho 1 tin (xem để sửa / xoá).
export async function GET(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  return proxyToApi(req, `/listings/${params.id}/reviews/mine`);
}

export async function DELETE(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  return proxyToApi(req, `/listings/${params.id}/reviews/mine`);
}
