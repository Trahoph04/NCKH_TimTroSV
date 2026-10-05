import { proxyToApi } from "@/lib/proxy";

// Xin vé WebSocket + trả kèm địa chỉ WS đọc lúc CHẠY (không bake lúc build).
// CHAT_WS_URL chỉ cần khi web và API nằm ở 2 tên miền khác nhau (vd. tunnel
// https://xxx.trycloudflare.com) — LAN thì để trống, client tự suy ra ws://<IP>:8000.
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const res = await proxyToApi(req, "/chat/ws-ticket");
  if (!res.ok) return res;
  const body = (await res.json()) as { ticket: string; expires_in: number };
  return Response.json({ ...body, ws_url: process.env.CHAT_WS_URL || null });
}
