import { NextResponse } from "next/server";
import { getListing, type ApiError } from "@/lib/api";
import { proxyToApi } from "@/lib/proxy";

// Sửa / ẩn tin (admin). Qua proxyToApi để access token 15 phút hết hạn giữa lúc admin đang điền form thì tự refresh,
// không báo "Chưa đăng nhập". id phải là số: id kiểu "..%2Fchat%2F…" từng đi tới path API khác kèm token người dùng.
// Đọc 1 tin cho client component (bản đồ lớn mở từ bản đồ nhỏ với tin ngoài bán kính nearby).
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  try {
    return NextResponse.json(await getListing(params.id));
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi lấy tin" }, { status: err.status ?? 500 });
  }
}

export async function PUT(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  return proxyToApi(req, `/listings/${params.id}`);
}

export async function DELETE(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  return proxyToApi(req, `/listings/${params.id}`);
}
