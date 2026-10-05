// Gọi API chat từ client component — luôn qua Route Handler /api/chat/* (cookie httpOnly).
import type { Conversation, ConversationDetail, Like, Message } from "./types";

export class ChatApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { ...init, cache: "no-store" });
  if (!res.ok) {
    let detail = `Lỗi ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = body.detail[0]?.msg ?? detail;
    } catch {
      /* body không phải JSON */
    }
    throw new ChatApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const chatApi = {
  conversations: () => req<{ items: Conversation[] }>("/api/chat/conversations").then((r) => r.items),
  conversation: (id: number) => req<ConversationDetail>(`/api/chat/conversations/${id}`),
  messages: (id: number, q: { after_id?: number; before_id?: number; limit?: number } = {}) => {
    const sp = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v != null && sp.set(k, String(v)));
    const qs = sp.toString();
    return req<{ items: Message[]; has_more: boolean }>(
      `/api/chat/conversations/${id}/messages${qs ? `?${qs}` : ""}`,
    );
  },
  sendText: (id: number, body: string, client_id: string) =>
    req<Message>(`/api/chat/conversations/${id}/messages`, json({ kind: "text", body, client_id })),
  sendListing: (id: number, listing_id: number, client_id: string) =>
    req<Message>(`/api/chat/conversations/${id}/messages`, json({ kind: "listing", listing_id, client_id })),
  sendImages: (id: number, files: File[], client_id: string) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("client_id", client_id);
    return req<Message>(`/api/chat/conversations/${id}/images`, { method: "POST", body: fd });
  },
  read: (id: number, message_id: number) =>
    req<{ last_read_message_id: number }>(`/api/chat/conversations/${id}/read`, json({ message_id })),
  unmatch: (id: number) => req<void>(`/api/chat/conversations/${id}`, { method: "DELETE" }),
  report: (id: number, reason: string, note: string) =>
    req<{ id: number }>(`/api/chat/conversations/${id}/report`, json({ reason, note: note || null })),
  unread: () => req<{ messages: number; likes: number }>("/api/chat/unread"),
  ticket: () => req<{ ticket: string; ws_url?: string | null }>("/api/chat/ws-ticket", { method: "POST" }),
  likes: () => req<{ items: Like[] }>("/api/matching/likes").then((r) => r.items),
  swipe: (target_id: number, decision: "like" | "pass") =>
    req<{ matched: boolean; conversation_id: number | null }>("/api/matching/swipe", json({ target_id, decision })),
};

export const mediaUrl = (id: string) => `/api/chat/media/${id}`;

const pageIsSecure = () => typeof window !== "undefined" && window.location.protocol === "https:";

/** Chuẩn hoá về ws(s)://host[:port]/chat/ws.
 *  - Nhận cả "https://x.trycloudflare.com", "x.trycloudflare.com", "wss://x/chat/ws".
 *  - Trang https ⇒ BẮT BUỘC wss: trình duyệt chặn ws:// từ trang https (mixed
 *    content) mà không báo lỗi gì ra UI ⇒ realtime chết im lặng sau tunnel.
 *  - Không có path ⇒ thêm /chat/ws (người đặt biến hay chỉ dán tên miền). */
export function normalizeWsUrl(raw: string, secure = pageIsSecure()): string {
  let s = raw.trim();
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = `${secure ? "wss" : "ws"}://${s}`;
  const u = new URL(s);
  if (u.protocol === "https:" || u.protocol === "wss:" || secure) u.protocol = "wss:";
  else u.protocol = "ws:";
  if (u.pathname === "" || u.pathname === "/") u.pathname = "/chat/ws";
  u.search = "";
  u.hash = "";
  return u.toString();
}

/** URL WebSocket tới FastAPI. Ưu tiên CHAT_WS_URL server trả kèm vé (tunnel/tên miền riêng).
 *  Không có thì: API ở localhost mà trang mở bằng IP LAN (máy khác / điện thoại)
 *  ⇒ thay host bằng host của trang — chính là máy đang chạy docker compose.
 *  Scheme lấy theo TRANG (không theo NEXT_PUBLIC_API_URL, vốn bake sẵn http lúc build). */
export function chatWsUrl(fromServer?: string | null): string {
  const explicit = fromServer || process.env.NEXT_PUBLIC_CHAT_WS_URL;
  if (explicit) return normalizeWsUrl(explicit);
  const api = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");
  if (["localhost", "127.0.0.1"].includes(api.hostname) && typeof window !== "undefined") {
    api.hostname = window.location.hostname;
  }
  api.pathname = "/chat/ws";
  return normalizeWsUrl(api.toString(), pageIsSecure() || api.protocol === "https:");
}

export function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
