import { proxyToApi } from "@/lib/proxy";

// /api/chat/* → FastAPI /chat/* (hội thoại, tin nhắn, ảnh, vé WebSocket…).
// Quyền (thành viên hội thoại) kiểm ở backend; route này chỉ gắn token.
export const dynamic = "force-dynamic";

type Ctx = { params: { path: string[] } };

const forward = (req: Request, { params }: Ctx) =>
  proxyToApi(req, `/chat/${params.path.map(encodeURIComponent).join("/")}`);

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
