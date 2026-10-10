import { proxyToApi } from "@/lib/proxy";

// /api/chatbot/* → FastAPI /chatbot/* (hỏi đáp, lịch sử, phản hồi). Tách khỏi /api/chat/* —
// đó là chat realtime ghép bạn. Chủ lịch sử lấy từ token ở backend, route này chỉ gắn token.
export const dynamic = "force-dynamic";
// câu hỏi pháp lý qua Qwen local có thể mất 1–2 phút
export const maxDuration = 300;

type Ctx = { params: { path: string[] } };

const forward = (req: Request, { params }: Ctx) =>
  proxyToApi(req, `/chatbot/${params.path.map(encodeURIComponent).join("/")}`);

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
