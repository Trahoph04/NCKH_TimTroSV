import { NextResponse } from "next/server";
import { refresh } from "./api";
import { API_URL } from "./config";
import { getAccessToken, getRefreshToken, setAuthCookies } from "./session";

// Proxy Route Handler → FastAPI, gắn Bearer từ cookie httpOnly.
// Khác các route cũ: chat là phiên dài (mở tab cả buổi) nên access token 15 phút
// chắc chắn hết hạn giữa chừng → tự refresh 1 lần rồi gọi lại, set cookie mới.
// Chỉ dùng trong Route Handler (được phép set cookie).

// retry-after: 429 của rate limit (app/ratelimit.py) cần nó để FE biết chờ bao lâu
const PASS_HEADERS = ["content-type", "cache-control", "content-length", "etag", "last-modified", "retry-after"];

async function tryRefresh(): Promise<string | undefined> {
  const rt = getRefreshToken();
  if (!rt) return undefined;
  try {
    const t = await refresh(rt);
    setAuthCookies(t.access_token, t.refresh_token);
    return t.access_token;
  } catch {
    return undefined;
  }
}

export async function proxyToApi(req: Request, upstreamPath: string): Promise<Response> {
  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();
  const contentType = req.headers.get("content-type");
  const target = `${API_URL}${upstreamPath}${new URL(req.url).search}`;

  const call = (token: string) =>
    fetch(target, {
      method,
      body,
      headers: {
        ...(contentType ? { "Content-Type": contentType } : {}),
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

  let token = getAccessToken() ?? (await tryRefresh());
  if (!token) {
    return NextResponse.json({ detail: "Chưa đăng nhập" }, { status: 401 });
  }

  let res: Response;
  try {
    res = await call(token);
    if (res.status === 401) {
      token = await tryRefresh();
      if (!token) return NextResponse.json({ detail: "Phiên đăng nhập hết hạn" }, { status: 401 });
      res = await call(token);
    }
  } catch {
    return NextResponse.json({ detail: "Không kết nối được máy chủ" }, { status: 502 });
  }

  const headers = new Headers();
  for (const h of PASS_HEADERS) {
    const v = res.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(res.status === 204 ? null : res.body, { status: res.status, headers });
}
