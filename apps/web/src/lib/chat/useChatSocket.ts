"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi, ChatApiError, chatWsUrl } from "./client";
import type { ChatEvent } from "./types";

export type SocketStatus = "connecting" | "open" | "offline";

const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000];
const PING_MS = 25_000; // server giữ presence 90s ⇒ chịu được rớt 3 nhịp

/**
 * Một WebSocket cho cả trang chat.
 * - Xin vé 60s qua /api/chat/ws-ticket (cookie httpOnly) rồi nối thẳng tới FastAPI.
 * - Rớt mạng → tự nối lại theo backoff; tab quay lại / có mạng lại → nối ngay.
 * - status !== "open" ⇒ ChatApp tự chuyển sang polling REST (không mất tin vì tin luôn ở DB).
 */
export function useChatSocket(onEvent: (ev: ChatEvent) => void) {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    let stopped = false;
    let connecting = false;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const schedule = () => {
      if (stopped) return;
      clearTimeout(retryTimer);
      retryTimer = setTimeout(connect, BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]);
      attempt += 1;
    };

    async function connect() {
      if (stopped || connecting || wsRef.current) return;
      connecting = true;
      let ticket: string;
      let wsUrl: string | null | undefined;
      try {
        ({ ticket, ws_url: wsUrl } = await chatApi.ticket());
      } catch (e) {
        connecting = false;
        setStatus("offline");
        if (e instanceof ChatApiError && e.status === 401) return; // hết phiên: polling cũng sẽ 401
        schedule();
        return;
      }
      if (stopped) {
        connecting = false;
        return;
      }
      // Cả chatWsUrl() (new URL với NEXT_PUBLIC_API_URL sai) lẫn constructor WebSocket đều có thể
      // throw ngay: URL không hợp lệ, scheme bị chặn, hoặc trang https nối ws:// (mixed content).
      // Throw ở đây mà không nhả cờ `connecting` thì mọi connect()/wake() sau đều return sớm
      // ⇒ realtime chết hẳn tới khi F5. Nên: nhả cờ + báo offline + vẫn đặt hẹn nối lại.
      let created: WebSocket | null = null;
      try {
        created = new WebSocket(`${chatWsUrl(wsUrl)}?ticket=${encodeURIComponent(ticket)}`);
      } catch {
        /* xử lý ngay dưới — giữ nguyên một đường thoát duy nhất */
      }
      if (!created) {
        connecting = false;
        setStatus("offline"); // ChatApp thấy !== "open" ⇒ chuyển sang polling REST, không mất tin
        schedule();
        return;
      }
      const ws = created; // const để các handler bên dưới giữ đúng kiểu WebSocket (đã loại null)
      wsRef.current = ws;
      connecting = false;

      ws.onopen = () => {
        attempt = 0;
        setStatus("open");
        clearInterval(pingTimer);
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}');
        }, PING_MS);
      };
      ws.onmessage = (e) => {
        try {
          handlerRef.current(JSON.parse(e.data) as ChatEvent);
        } catch {
          /* frame lỗi: bỏ qua */
        }
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        if (wsRef.current === ws) wsRef.current = null;
        if (stopped) return;
        setStatus("offline");
        schedule();
      };
      ws.onerror = () => ws.close();
    }

    const wake = () => {
      if (document.visibilityState === "visible" && !wsRef.current && !connecting && !stopped) {
        clearTimeout(retryTimer);
        attempt = 0;
        connect();
      }
    };

    connect();
    window.addEventListener("online", wake);
    document.addEventListener("visibilitychange", wake);
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      window.removeEventListener("online", wake);
      document.removeEventListener("visibilitychange", wake);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const send = useCallback((frame: object) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(frame));
      return true;
    }
    return false;
  }, []);

  return { status, send };
}
