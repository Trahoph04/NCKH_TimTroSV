"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { chatApi, ChatApiError, newClientId } from "@/lib/chat/client";
import type {
  ChatEvent,
  Conversation,
  ConversationDetail,
  Like,
  Me,
  Message,
} from "@/lib/chat/types";
import { useChatSocket } from "@/lib/chat/useChatSocket";
import ChatThread from "./ChatThread";
import ConversationList from "./ConversationList";
import { ConfirmModal, MatchModal, ReportModal, Toast } from "./Modals";
import ProfilePanel from "./ProfilePanel";

type Thread = { items: Message[]; hasMore: boolean; loaded: boolean };

const POLL_MS = 3000; // fallback khi WebSocket rớt (khớp thiết kế ban đầu: polling 3s)
const TYPING_TTL_MS = 6000;

/** Gộp tin mới vào thread: bỏ trùng theo id, thay bản optimistic cùng client_id. */
function merge(items: Message[], incoming: Message[]): Message[] {
  let out = items;
  for (const m of incoming) {
    if (out.some((x) => x.id === m.id && !x.status)) continue;
    const pendingIdx = m.client_id ? out.findIndex((x) => x.status && x.client_id === m.client_id) : -1;
    if (pendingIdx >= 0) {
      const old = out[pendingIdx];
      old.local_images?.forEach((u) => URL.revokeObjectURL(u));
      out = [...out.slice(0, pendingIdx), m, ...out.slice(pendingIdx + 1)];
    } else {
      out = [...out, m];
    }
  }
  const real = out.filter((m) => !m.status).sort((a, b) => a.id - b.id);
  const pending = out.filter((m) => m.status);
  return [...real, ...pending];
}

/** Lỗi fetch thuần (mất mạng, API chết) không có `.status` và message là "Failed to fetch" —
 *  vô nghĩa với người dùng, nên chỉ ChatApiError mới được lấy detail do API trả. */
function errText(e: unknown): string {
  return e instanceof ChatApiError ? e.message : "mất kết nối tới máy chủ";
}

function lastRealId(t?: Thread): number | undefined {
  if (!t) return undefined;
  for (let i = t.items.length - 1; i >= 0; i--) if (!t.items[i].status) return t.items[i].id;
  return undefined;
}

export default function ChatApp({ me, initialConversationId }: { me: Me; initialConversationId: number | null }) {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [convsError, setConvsError] = useState<string | null>(null);
  const [likesError, setLikesError] = useState<string | null>(null);
  const [threadErrors, setThreadErrors] = useState<Record<number, string | undefined>>({});
  const [activeId, setActiveId] = useState<number | null>(initialConversationId);
  const [details, setDetails] = useState<Record<number, ConversationDetail>>({});
  const [threads, setThreads] = useState<Record<number, Thread>>({});
  const [typing, setTyping] = useState<Record<number, number>>({});
  const [online, setOnline] = useState<Record<number, boolean>>({});
  const [lastSeen, setLastSeen] = useState<Record<number, string>>({});
  const [likes, setLikes] = useState<Like[]>([]);
  const [tab, setTab] = useState<"matched" | "likes">("matched");
  const [matchModal, setMatchModal] = useState<{ conversationId: number; name: string } | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [unmatchOpen, setUnmatchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [visible, setVisible] = useState(true);

  const activeRef = useRef(activeId);
  activeRef.current = activeId;
  const threadsRef = useRef(threads);
  threadsRef.current = threads;
  const visibleRef = useRef(visible);
  visibleRef.current = visible;
  // Tin realtime tới trong lúc GET lịch sử đang bay thì không nằm trong response của GET đó ⇒ đệm lại
  // để gộp vào sau. Trước đây tin bị bỏ khỏi thread nhưng vẫn cộng badge chưa đọc ⇒ badge ảo.
  const pendingIncoming = useRef<Record<number, Message[]>>({});
  // Cờ "đang nạp" của từng thread — phải nhả trong finally, một lần GET lỗi mà không nhả là
  // thread kẹt "Đang tải tin nhắn…" vĩnh viễn (polling/WS cũng không vào lại được).
  const loadingThread = useRef<Record<number, boolean>>({});

  const flash = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast((t) => (t === msg ? null : t)), 3500);
  }, []);

  // ------------------------------------------------------------ tải dữ liệu
  const loadConvs = useCallback(async () => {
    try {
      const items = await chatApi.conversations();
      setConvs((prev) =>
        items.map((c) => {
          // giữ unread=0 cho hội thoại đang mở (tránh nhấp nháy badge khi polling)
          const old = prev.find((p) => p.id === c.id);
          return old && activeRef.current === c.id && visibleRef.current ? { ...c, unread: 0 } : c;
        }),
      );
      setOnline((prev) => {
        const next = { ...prev };
        items.forEach((c) => (next[c.partner.id] = Boolean(c.partner.online)));
        return next;
      });
      setLastSeen((prev) => {
        const next = { ...prev };
        items.forEach((c) => c.partner.last_seen_at && (next[c.partner.id] = c.partner.last_seen_at));
        return next;
      });
      setConvsError(null);
    } catch (e) {
      if (e instanceof ChatApiError && e.status === 401) {
        window.location.href = "/login?next=/chat";
        return; // finally vẫn chạy: tắt skeleton trước khi trang chuyển sang /login
      }
      // Phải phân biệt "rỗng" với "lỗi": trước đây API chết cũng ra "Chưa có ai ghép đôi với bạn"
      // — nói sai về dữ liệu của chính người dùng, họ tưởng mất hết match.
      setConvsError(`Không tải được danh sách ghép đôi — ${errText(e)}.`);
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  const loadLikes = useCallback(async () => {
    try {
      setLikes(await chatApi.likes());
      setLikesError(null);
    } catch (e) {
      // Tab Lời mời không chặn chat, nhưng im lặng thì danh sách rỗng cũng là một lời nói sai.
      setLikesError(`Không tải được lời mời ghép đôi — ${errText(e)}.`);
    }
  }, []);

  const loadDetail = useCallback(async (id: number) => {
    try {
      const d = await chatApi.conversation(id);
      setDetails((prev) => ({ ...prev, [id]: d }));
    } catch (e) {
      if (e instanceof ChatApiError && e.status === 404) {
        setConvs((prev) => prev.filter((c) => c.id !== id));
        if (activeRef.current === id) setActiveId(null);
      }
    }
  }, []);

  const loadThread = useCallback(async (id: number) => {
    if (loadingThread.current[id]) return; // tránh 2 GET song song (polling 3s + mở hội thoại)
    loadingThread.current[id] = true;
    try {
      const r = await chatApi.messages(id, { limit: 40 });
      // gộp luôn tin realtime đã đệm trong lúc chờ GET — chúng sinh ra SAU khi query chạy
      const buffered = pendingIncoming.current[id] ?? [];
      delete pendingIncoming.current[id];
      setThreads((prev) => ({
        ...prev,
        [id]: {
          items: merge(merge(prev[id]?.items.filter((m) => m.status) ?? [], r.items), buffered),
          hasMore: r.has_more,
          loaded: true,
        },
      }));
      setThreadErrors((prev) => (prev[id] == null ? prev : { ...prev, [id]: undefined }));
    } catch (e) {
      // Bỏ đệm: lần thử lại GET lại từ DB nên tin đệm đã nằm trong response, giữ lại chỉ tốn bộ nhớ.
      delete pendingIncoming.current[id];
      if (e instanceof ChatApiError && e.status === 401) {
        window.location.href = "/login?next=/chat";
        return;
      }
      // Lưu lỗi theo từng hội thoại: chỉ xoá khi nạp lại THÀNH CÔNG, không xoá ở đầu mỗi lần thử —
      // polling 3s sẽ tự thử lại, nếu xoá sớm thì khối lỗi nhấp nháy liên tục.
      setThreadErrors((prev) => ({ ...prev, [id]: errText(e) }));
    } finally {
      loadingThread.current[id] = false;
    }
  }, []);

  const syncThread = useCallback(async (id: number) => {
    const t = threadsRef.current[id];
    if (!t?.loaded) return loadThread(id);
    const after = lastRealId(t) ?? 0;
    try {
      const r = await chatApi.messages(id, { after_id: after, limit: 100 });
      if (r.items.length)
        setThreads((prev) => ({ ...prev, [id]: { ...prev[id], items: merge(prev[id].items, r.items) } }));
    } catch {
      /* lần sau thử lại */
    }
  }, [loadThread]);

  const loadOlder = useCallback(
    async (id: number) => {
      const t = threadsRef.current[id];
      const first = t?.items.find((m) => !m.status);
      if (!t || !first) return;
      try {
        const r = await chatApi.messages(id, { before_id: first.id, limit: 40 });
        setThreads((prev) => ({
          ...prev,
          [id]: { ...prev[id], items: merge(r.items, prev[id].items), hasMore: r.has_more },
        }));
      } catch (e) {
        // ChatThread chỉ bọc try/finally quanh onLoadOlder ⇒ throw ở đây thoát ra thành
        // unhandled rejection: nút "Xem tin cũ hơn" hết spinner mà không báo gì. Giữ lỗi ở đây.
        flash(`Không tải được tin cũ hơn — ${errText(e)}.`);
      }
    },
    [flash],
  );

  // --------------------------------------------------------- sự kiện realtime
  const applyIncoming = useCallback(
    (convId: number, msg: Message) => {
      // Thread đang nạp dở: tin này sinh ra sau khi GET lịch sử chạy nên response không có nó.
      // Đệm lại (chỉ khi thực sự có GET đang bay nên không phình bộ nhớ) để loadThread gộp vào —
      // trước đây tin bị bỏ hẳn mà badge chưa đọc vẫn +1 ⇒ badge ảo không cách nào tắt.
      if (!threadsRef.current[convId]?.loaded && loadingThread.current[convId]) {
        pendingIncoming.current[convId] = [...(pendingIncoming.current[convId] ?? []), msg];
      }
      setThreads((prev) =>
        prev[convId]?.loaded ? { ...prev, [convId]: { ...prev[convId], items: merge(prev[convId].items, [msg]) } } : prev,
      );
      let known = true;
      setConvs((prev) => {
        const idx = prev.findIndex((c) => c.id === convId);
        if (idx < 0) {
          known = false;
          return prev;
        }
        const c = prev[idx];
        // Tin của chính mình tới HAI lần: response POST (sendWith) + tiếng vọng
        // message.new qua WS. Đã thấy tin này (hoặc tin mới hơn) ở last_message
        // thì không cộng đếm lần nữa — bản trước +1 hai lần cho mỗi tin gửi đi.
        if (c.last_message && c.last_message.id >= msg.id) return prev;
        const fromPartner = msg.sender_id != null && msg.sender_id !== me.id;
        const seeing = activeRef.current === convId && visibleRef.current;
        const updated: Conversation = {
          ...c,
          last_message: msg,
          last_message_at: msg.created_at,
          user_message_count: c.user_message_count + (msg.sender_id != null ? 1 : 0),
          unread: fromPartner && !seeing ? c.unread + 1 : c.unread,
        };
        return [updated, ...prev.slice(0, idx), ...prev.slice(idx + 1)];
      });
      if (!known) loadConvs();
      if (msg.sender_id != null && msg.sender_id !== me.id) setTyping((p) => ({ ...p, [convId]: 0 }));
      if (msg.kind === "listing") loadDetail(convId);
    },
    [me.id, loadConvs, loadDetail],
  );

  const onEvent = useCallback(
    (ev: ChatEvent) => {
      switch (ev.type) {
        case "hello":
          setOnline((prev) => {
            const next: Record<number, boolean> = {};
            Object.keys(prev).forEach((k) => (next[Number(k)] = false));
            ev.online.forEach((id) => (next[id] = true));
            return next;
          });
          break;
        case "message.new":
          applyIncoming(ev.conversation_id, ev.message);
          break;
        case "read":
          setConvs((prev) =>
            prev.map((c) => {
              if (c.id !== ev.conversation_id) return c;
              return ev.user_id === me.id
                ? { ...c, my_last_read: Math.max(c.my_last_read, ev.message_id), unread: 0 } // tab khác của mình đã đọc
                : { ...c, partner_last_read: Math.max(c.partner_last_read, ev.message_id) };
            }),
          );
          break;
        case "typing": {
          const until = ev.is_typing ? Date.now() + TYPING_TTL_MS : 0;
          setTyping((p) => ({ ...p, [ev.conversation_id]: until }));
          if (ev.is_typing)
            setTimeout(
              () => setTyping((p) => (p[ev.conversation_id] === until ? { ...p, [ev.conversation_id]: 0 } : p)),
              TYPING_TTL_MS,
            );
          break;
        }
        case "presence":
          setOnline((p) => ({ ...p, [ev.user_id]: ev.online }));
          if (!ev.online && ev.last_seen_at) setLastSeen((p) => ({ ...p, [ev.user_id]: ev.last_seen_at! }));
          break;
        case "match.new":
          loadConvs();
          loadLikes();
          // Phía BỊ ĐỘNG (người kia vừa bấm thích đáp lại) cũng phải có khoảnh
          // khắc "Thành đôi!" — bản trước bỏ qua conversation_id nên chỉ người
          // bấm sau mới thấy. Người bấm sau cũng nhận sự kiện này: respondLike
          // đặt đúng modal đó, `m ?? …` giữ nguyên nên không bật hai lần.
          chatApi
            .conversation(ev.conversation_id)
            .then((d) => setMatchModal((m) => m ?? { conversationId: ev.conversation_id, name: d.partner.name }))
            .catch(() => {});
          break;
        case "like.new":
          loadLikes();
          break;
        case "contact.consent":
          // Tải lại detail (đã kèm khối `contact`) ⇒ ProfilePanel chọn nguồn nhiều chữ
          // ký hơn và đổi trạng thái NGAY. Thiếu case này thì người đồng ý TRƯỚC phải
          // chờ nhịp hỏi lại 15s của panel — lúc demo 15 giây im lặng trông như hỏng.
          loadDetail(ev.conversation_id);
          break;
        case "conversation.removed":
          threadsRef.current[ev.conversation_id]?.items.forEach((m) =>
            m.local_images?.forEach((u) => URL.revokeObjectURL(u)),
          );
          setConvs((prev) => prev.filter((c) => c.id !== ev.conversation_id));
          if (activeRef.current === ev.conversation_id) {
            setActiveId(null);
            if (ev.by_user_id !== me.id) flash("Cuộc trò chuyện đã kết thúc — bạn ấy đã huỷ ghép.");
          }
          break;
      }
    },
    [applyIncoming, flash, loadConvs, loadDetail, loadLikes, me.id],
  );

  const { status, send } = useChatSocket(onEvent);

  // ----------------------------------------------------------- vòng đời
  useEffect(() => {
    loadConvs();
    loadLikes();
  }, [loadConvs, loadLikes]);

  useEffect(() => {
    const onVis = () => setVisible(document.visibilityState === "visible");
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  // mở hội thoại: tải tin + hồ sơ, cập nhật URL (?c=) để F5 vẫn ở đúng chỗ
  useEffect(() => {
    if (activeId == null) {
      window.history.replaceState(null, "", "/chat");
      return;
    }
    window.history.replaceState(null, "", `/chat?c=${activeId}`);
    if (!threadsRef.current[activeId]?.loaded) loadThread(activeId);
    else syncThread(activeId);
    loadDetail(activeId);
    setProfileOpen(false);
  }, [activeId, loadThread, syncThread, loadDetail]);

  // socket mở lại sau khi rớt ⇒ đồng bộ phần đã lỡ
  const prevStatus = useRef(status);
  useEffect(() => {
    if (status === "open" && prevStatus.current === "offline") {
      loadConvs();
      loadLikes();
      if (activeRef.current != null) syncThread(activeRef.current);
    }
    prevStatus.current = status;
  }, [status, loadConvs, loadLikes, syncThread]);

  // fallback polling khi không có WebSocket
  useEffect(() => {
    if (status === "open") return;
    let tick = 0;
    const t = setInterval(() => {
      tick += 1;
      if (activeRef.current != null) syncThread(activeRef.current);
      if (tick % 3 === 0) {
        loadConvs();
        loadLikes();
      }
    }, POLL_MS);
    return () => clearInterval(t);
  }, [status, syncThread, loadConvs, loadLikes]);

  const active = useMemo(() => convs.find((c) => c.id === activeId) ?? null, [convs, activeId]);
  const activeThread = activeId != null ? threads[activeId] : undefined;

  // đánh dấu đã xem khi đang nhìn hội thoại
  useEffect(() => {
    if (!active || !visible || !activeThread?.loaded) return;
    const lastPartner = [...activeThread.items]
      .reverse()
      .find((m) => !m.status && m.sender_id != null && m.sender_id !== me.id);
    const lastAny = lastRealId(activeThread) ?? 0;
    if (active.unread > 0 || (lastPartner && lastPartner.id > active.my_last_read)) {
      setConvs((prev) => prev.map((c) => (c.id === active.id ? { ...c, unread: 0, my_last_read: lastAny } : c)));
      chatApi.read(active.id, lastAny).catch(() => {});
    }
  }, [active, activeThread, visible, me.id]);

  // badge "Tin nhắn" trên header = tin chưa đọc + lời mời đang chờ (khớp
  // /chat/unread mà các trang khác hỏi). Chưa tải xong danh sách thì KHÔNG đẩy:
  // đẩy 0 lúc convs còn rỗng là xoá badge đúng về 0 rồi mới nhảy lại.
  useEffect(() => {
    if (loadingConvs) return;
    const total = convs.reduce((s, c) => s + c.unread, 0) + likes.length;
    window.dispatchEvent(new CustomEvent("chat:unread", { detail: total }));
  }, [convs, likes, loadingConvs]);

  // Rời trang: thu hồi object URL ảnh xem trước của các tin chưa gửi được.
  // merge() chỉ thu hồi khi tin thật về thay bản optimistic — tin thất bại hẳn
  // thì URL (và cả File trong bộ nhớ) nằm lại tới khi đóng tab.
  useEffect(
    () => () => {
      Object.values(threadsRef.current).forEach((t) =>
        t.items.forEach((m) => m.status && m.local_images?.forEach((u) => URL.revokeObjectURL(u))),
      );
    },
    [],
  );

  // ------------------------------------------------------------- gửi tin
  const pushPending = (convId: number, m: Message) =>
    setThreads((prev) => {
      const t = prev[convId] ?? { items: [], hasMore: false, loaded: true };
      return { ...prev, [convId]: { ...t, items: [...t.items.filter((x) => x.client_id !== m.client_id), m] } };
    });

  const markFailed = (convId: number, clientId: string, retry: () => void) =>
    setThreads((prev) => {
      const t = prev[convId];
      if (!t) return prev;
      return {
        ...prev,
        [convId]: {
          ...t,
          items: t.items.map((x) => (x.client_id === clientId && x.status ? { ...x, status: "failed", retry } : x)),
        },
      };
    });

  const sendWith = useCallback(
    (
      convId: number,
      draft: Pick<Message, "kind" | "body" | "payload"> & { local_images?: string[] },
      call: (clientId: string) => Promise<Message>,
      clientId = newClientId(),
    ) => {
      const pending: Message = {
        id: -Date.now(),
        conversation_id: convId,
        sender_id: me.id,
        client_id: clientId,
        created_at: new Date().toISOString(),
        status: "sending",
        ...draft,
      };
      pushPending(convId, pending);
      call(clientId)
        .then((msg) => applyIncoming(convId, msg))
        .catch((e) => {
          if (e instanceof ChatApiError && e.status === 404) {
            flash("Không gửi được: hội thoại không còn tồn tại.");
            loadConvs();
          } else if (e instanceof ChatApiError && e.status === 422) {
            flash(e.message);
          }
          markFailed(convId, clientId, () => sendWith(convId, draft, call, clientId));
        });
    },
    [me.id, applyIncoming, flash, loadConvs],
  );

  const sendText = (text: string) => {
    if (activeId == null) return;
    const id = activeId;
    sendWith(id, { kind: "text", body: text, payload: null }, (cid) => chatApi.sendText(id, text, cid));
  };

  const sendListing = (listingId: number, snapshot: Message["payload"]) => {
    if (activeId == null) return;
    const id = activeId;
    sendWith(id, { kind: "listing", body: null, payload: snapshot }, (cid) => chatApi.sendListing(id, listingId, cid));
  };

  const sendImages = (files: File[]) => {
    if (activeId == null || files.length === 0) return;
    const id = activeId;
    const picked = files.slice(0, 4);
    if (files.length > 4) flash("Mỗi lần gửi tối đa 4 ảnh — đã lấy 4 ảnh đầu.");
    const local = picked.map((f) => URL.createObjectURL(f));
    sendWith(id, { kind: "image", body: null, payload: null, local_images: local }, (cid) =>
      chatApi.sendImages(id, picked, cid),
    );
  };

  const sendTyping = useCallback(
    (isTyping: boolean, convId: number) => {
      send({ type: "typing", conversation_id: convId, is_typing: isTyping });
    },
    [send],
  );

  // ------------------------------------------------------ lời mời / huỷ ghép
  const respondLike = async (like: Like, decision: "like" | "pass") => {
    setLikes((prev) => prev.filter((l) => l.user_id !== like.user_id));
    try {
      const r = await chatApi.swipe(like.user_id, decision);
      if (r.matched && r.conversation_id) {
        await loadConvs();
        setMatchModal({ conversationId: r.conversation_id, name: like.name });
      }
    } catch (e) {
      flash(e instanceof Error ? e.message : "Có lỗi, thử lại nhé");
      loadLikes();
    }
  };

  const doUnmatch = async () => {
    if (!active) return;
    const id = active.id;
    setUnmatchOpen(false);
    try {
      await chatApi.unmatch(id);
      setConvs((prev) => prev.filter((c) => c.id !== id));
      setActiveId(null);
      flash("Đã huỷ ghép và xoá cuộc trò chuyện.");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Không huỷ ghép được");
    }
  };

  const doReport = async (reason: string, note: string) => {
    if (!active) return;
    setReportOpen(false);
    try {
      await chatApi.report(active.id, reason, note);
      flash("Đã gửi báo cáo. Cảm ơn bạn — nhóm sẽ xem xét.");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Không gửi được báo cáo");
    }
  };

  const detail = activeId != null ? details[activeId] : undefined;
  const activeThreadError = activeId != null ? threadErrors[activeId] : undefined;
  const listError = convsError ?? likesError;
  const retryLists = useCallback(async () => {
    await Promise.all([loadConvs(), loadLikes()]); // cả hai đều tự catch nên await không bao giờ throw
  }, [loadConvs, loadLikes]);
  const partnerOnline = active ? online[active.partner.id] ?? Boolean(active.partner.online) : false;
  const partnerLastSeen = active ? lastSeen[active.partner.id] ?? active.partner.last_seen_at : null;
  const isTyping = activeId != null && (typing[activeId] ?? 0) > Date.now();

  return (
    <div className="flex min-h-0 flex-1 bg-white">
      <aside
        className={`${active ? "hidden md:flex" : "flex"} w-full shrink-0 flex-col border-r border-line md:w-[340px]`}
      >
        {listError && <ListErrorBanner text={listError} onRetry={retryLists} />}
        <ConversationList
          me={me}
          convs={convs}
          loading={loadingConvs}
          activeId={activeId}
          onSelect={(id) => {
            setTab("matched");
            setActiveId(id);
          }}
          tab={tab}
          onTab={setTab}
          likes={likes}
          onRespond={respondLike}
          online={online}
          typing={typing}
        />
      </aside>

      <section className={`${active ? "flex" : "hidden md:flex"} min-w-0 flex-1 flex-col bg-paper`}>
        {active && activeThreadError && !activeThread?.loaded ? (
          // Thread chưa bao giờ nạp được: KHÔNG để ChatThread hiện "Đang tải tin nhắn…" mãi,
          // vì không còn gì kích hoạt nạp lại khi WS đang mở (polling chỉ chạy lúc WS rớt).
          <ThreadErrorState
            key={active.id}
            name={active.partner.name}
            detail={activeThreadError}
            onBack={() => setActiveId(null)}
            onRetry={() => loadThread(active.id)}
          />
        ) : active ? (
          <ChatThread
            key={active.id}
            me={me}
            conv={active}
            thread={activeThread}
            online={partnerOnline}
            lastSeen={partnerLastSeen}
            typing={isTyping}
            socketStatus={status}
            onBack={() => setActiveId(null)}
            onLoadOlder={() => loadOlder(active.id)}
            onSendText={sendText}
            onSendImages={sendImages}
            onSendListing={sendListing}
            onTyping={sendTyping}
            onShowProfile={() => setProfileOpen((v) => !v)}
            onReport={() => setReportOpen(true)}
          />
        ) : (
          <EmptyState
            hasConvs={convs.length > 0}
            likes={likes.length}
            error={convsError}
            onLikes={() => setTab("likes")}
            onRetry={retryLists}
          />
        )}
      </section>

      {active && (
        <aside
          className={`${profileOpen ? "fixed inset-0 z-40 flex bg-black/30 xl:static xl:bg-transparent" : "hidden xl:flex"} xl:w-[300px] xl:shrink-0`}
          onClick={(e) => e.target === e.currentTarget && setProfileOpen(false)}
        >
          <ProfilePanel
            conv={active}
            detail={detail}
            online={partnerOnline}
            onClose={() => setProfileOpen(false)}
            onReport={() => setReportOpen(true)}
            onUnmatch={() => setUnmatchOpen(true)}
          />
        </aside>
      )}

      {matchModal && (
        <MatchModal
          meName={me.name}
          partnerName={matchModal.name}
          onChat={() => {
            setActiveId(matchModal.conversationId);
            setTab("matched");
            setMatchModal(null);
          }}
          onClose={() => setMatchModal(null)}
        />
      )}
      {reportOpen && active && (
        <ReportModal name={active.partner.name} onSubmit={doReport} onClose={() => setReportOpen(false)} />
      )}
      {unmatchOpen && active && (
        <ConfirmModal
          title={`Huỷ ghép với ${active.partner.name}?`}
          body="Toàn bộ tin nhắn và ảnh của cuộc trò chuyện sẽ bị xoá vĩnh viễn ở cả hai phía. Hai bạn sẽ không tự ghép lại."
          confirmLabel="Huỷ ghép & xoá"
          onConfirm={doUnmatch}
          onClose={() => setUnmatchOpen(false)}
        />
      )}
      {toast && <Toast text={toast} />}
    </div>
  );
}

/** Nút thử lại dùng chung: tự khoá trong lúc chờ để người dùng biết cú bấm đã được nhận. */
function RetryButton({
  onRetry,
  idle,
  busyLabel,
  className,
}: {
  onRetry: () => Promise<void>;
  idle: string;
  busyLabel: string;
  className: string;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await onRetry();
        } finally {
          // finally: thử lại thất bại cũng phải mở khoá nút, không thì bấm được đúng một lần
          setBusy(false);
        }
      }}
      className={className}
    >
      {busy ? busyLabel : idle}
    </button>
  );
}

/** Dải cảnh báo trên cột danh sách — ConversationList bên dưới vẫn hiện "Chưa có ai ghép đôi",
 *  nên phải nói rõ ngay phía trên rằng đó là lỗi tải chứ không phải dữ liệu thật. */
function ListErrorBanner({ text, onRetry }: { text: string; onRetry: () => Promise<void> }) {
  return (
    <div className="flex items-start justify-between gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
      <span className="min-w-0 leading-5">{text}</span>
      <RetryButton
        onRetry={onRetry}
        idle="Thử lại"
        busyLabel="Đang thử…"
        className="shrink-0 rounded-lg border border-amber-300 bg-white px-2 py-1 font-semibold hover:bg-amber-100 disabled:opacity-50"
      />
    </div>
  );
}

/** Thay cho ChatThread khi thread chưa bao giờ nạp được — thà nói thật là lỗi còn hơn
 *  để spinner "Đang tải tin nhắn…" xoay vĩnh viễn mà không có đường thử lại. */
function ThreadErrorState({
  name,
  detail,
  onBack,
  onRetry,
}: {
  name: string;
  detail: string;
  onBack: () => void;
  onRetry: () => Promise<void>;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-3 sm:px-6">
        <button
          onClick={onBack}
          className="-ml-1 rounded-lg p-1.5 text-ink-soft hover:bg-tint md:hidden"
          aria-label="Quay lại danh sách"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M12.5 4.5 7 10l5.5 5.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <div className="truncate font-bold text-ink">{name}</div>
      </header>
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber-50 text-2xl">⚠️</div>
        <h2 className="text-base font-bold text-ink">Không tải được tin nhắn</h2>
        <p className="max-w-sm text-sm text-ink-muted">
          Lý do: {detail}. Tin nhắn vẫn nằm nguyên trên máy chủ — không mất gì cả.
        </p>
        <RetryButton
          onRetry={onRetry}
          idle="Thử lại"
          busyLabel="Đang tải lại…"
          className="mt-1 rounded-[10px] bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy disabled:opacity-60"
        />
      </div>
    </div>
  );
}

function EmptyState({
  hasConvs,
  likes,
  error,
  onLikes,
  onRetry,
}: {
  hasConvs: boolean;
  likes: number;
  error: string | null;
  onLikes: () => void;
  onRetry: () => Promise<void>;
}) {
  // Lỗi tải ≠ chưa có ai ghép đôi. Gộp hai trạng thái này là nói sai về dữ liệu của người dùng.
  if (error)
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-50 text-2xl">⚠️</div>
        <h2 className="text-lg font-bold text-ink">Không tải được danh sách</h2>
        <p className="max-w-sm text-sm text-ink-muted">
          {error} Đây là lỗi tải dữ liệu, không phải là bạn chưa có ai ghép đôi.
        </p>
        <RetryButton
          onRetry={onRetry}
          idle="Thử lại"
          busyLabel="Đang thử…"
          className="mt-1 rounded-[10px] bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy disabled:opacity-60"
        />
      </div>
    );
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-2xl">💬</div>
      <h2 className="text-lg font-bold text-ink">
        {hasConvs ? "Chọn một cuộc trò chuyện" : "Chưa có ai ghép đôi với bạn"}
      </h2>
      <p className="max-w-sm text-sm text-ink-muted">
        Chỉ những bạn đã <b>cùng thích nhau</b> mới nhắn tin được — để không ai bị làm phiền bởi người lạ.
      </p>
      {likes > 0 && (
        <button
          onClick={onLikes}
          className="mt-2 rounded-[10px] bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy"
        >
          Xem {likes} lời mời đang chờ
        </button>
      )}
    </div>
  );
}
