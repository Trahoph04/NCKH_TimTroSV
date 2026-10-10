import { proxyToApi } from "@/lib/proxy";

// /api/recommend/{prefill, eval/session, eval/judge} → FastAPI, cần đăng nhập (gắn Bearer từ cookie).
export const dynamic = "force-dynamic";

type Ctx = { params: { path: string[] } };

const forward = (req: Request, { params }: Ctx) =>
  proxyToApi(req, `/recommend/${params.path.map(encodeURIComponent).join("/")}`);

export const GET = forward;
export const POST = forward;
