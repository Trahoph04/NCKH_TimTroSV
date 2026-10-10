"use client";

import Link from "next/link";
import ChatbotAnswer from "./ChatbotAnswer";
import { usePathname } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

type Source = {
  kind: "listing" | "legal_document";
  listing_id: number | null;
  document_id: number | null;
  chunk_id: number | null;
  rank: number;
  similarity_score: number;
  title: string;
  source: string;
  source_url: string | null;
  source_path: string | null;
  page_kind?: 'physical_pdf' | 'logical_document' | 'web_excerpt' | 'editorial_guidance' | null;
  category: string | null;
  page_from: number | null;
  page_to: number | null;
  heading: string | null;
  excerpt?: string | null;
};

type Listing = {
  id: number;
  corpus_schema?: string;
  title: string;
  price: number | null;
  area: number | null;
  address: string | null;
  district: string | null;
  amenities: Record<string, unknown>;
  distance_to_ctu: number | null;
  route_time_campus: number[] | null;
  source_url: string | null;
  similarity_score: number;
  vector_score: number;
  bm25_score: number;
  rank: number;
  match_reasons: string[];
};

type Turn = {
  conversationState?: ConversationState | null;
  key: string;
  role: "user" | "assistant";
  content: string;
  listings?: Listing[];
  sources?: Source[];
  degraded?: boolean;
  generationProvider?: string;
  eventId?: number | null;
  feedback?: -1 | 1;
  reusedAnswer?: boolean;
};

type AskResponse = {
  conversation_id?: string | null;
  turn_id?: number | null;
  reused_answer?: boolean;
  conversation_state?: ConversationState | null;
  answer: string;
  listings: Listing[];
  sources: Source[];
  degraded: boolean;
  degraded_reasons: string[];
  retrieval_mode: string;
  generation_provider: string;
  generation_model: string | null;
  latency_ms: number;
  event_id: number | null;
  citation_accuracy: number;
};

type Conversation = { id: string; title: string; updated_at: string; turn_count: number };
type SavedTurn = { id: number; question: string; response: AskResponse; created_at: string };
type SavedConversation = { id: string; title: string; turns: SavedTurn[]; has_more: boolean };

function savedTurns(items: SavedTurn[]): Turn[] {
  return items.flatMap(item => [
    { key: `user-saved-${item.id}`, role: "user" as const, content: item.question },
    { key: `assistant-saved-${item.id}`, role: "assistant" as const, content: item.response.answer,
      conversationState: item.response.conversation_state, listings: item.response.listings,
      sources: item.response.sources, degraded: item.response.degraded,
      generationProvider: item.response.generation_provider, eventId: item.response.event_id,
      reusedAnswer: item.response.reused_answer },
  ]);
}

type ConversationState = {
  filters: Record<string, unknown>;
  listing_ids: number[];
  selected_listing_id: number | null;
};

type WidgetMode = "closed" | "compact" | "expanded";

const WELCOME: Turn = {
  key: "welcome",
  role: "assistant",
  content:
    "Chào bạn! Mình là Trợ lý Trọ CTU. Mình có thể tìm phòng, hỏi đáp về ký túc xá CTU hoặc tra cứu quy định về hợp đồng thuê, điện nước, cư trú và PCCC.",
};

const QUICK_PROMPTS = [
  "Phòng dưới 2 triệu gần CTU",
  "Ở Ninh Kiều, có máy lạnh và wifi",
  "Tân sinh viên đăng ký KTX CTU như thế nào?",
  "Chủ trọ được thu tiền điện như thế nào theo quy định?",
];

function catalogSource(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && (url.hostname === "chotot.com" || url.hostname.endsWith(".chotot.com")) ? url.href : null;
  } catch { return null; }
}

// key = parsed_amenities của crawler repo này (khác catalog branch PHUC)
const amenityLabels: Record<string, string> = {
  wifi: "Wi-Fi",
  air_conditioner: "Máy lạnh",
  parking: "Chỗ để xe",
  private_wc: "WC riêng",
  fridge: "Tủ lạnh",
  washing_machine: "Máy giặt",
  kitchen: "Bếp",
  free_hours: "Giờ tự do",
  balcony: "Ban công",
};

function money(value: number | null) {
  return value == null
    ? "Chưa có giá"
    : new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
      }).format(value);
}

function distance(value: number | null) {
  if (value == null) return null;
  return value >= 1000 ? `${(value / 1000).toFixed(1)} km đến CTU` : `${Math.round(value)} m đến CTU`;
}

function Icon({ name }: { name: "chat" | "expand" | "shrink" | "close" | "send" | "reset" | "history" }) {
  const paths = {
    chat: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z" />,
    expand: <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />,
    shrink: <path d="M4 14h6v6M20 10h-6V4M10 14l-7 7M14 10l7-7" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    send: <path d="m22 2-7 20-4-9-9-4 20-7ZM11 13 22 2" />,
    reset: <path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5" />,
    history: <path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" />,
  };
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      {paths[name]}
    </svg>
  );
}

// Nút mở widget né control cố định của từng trang: /map có nút zoom MapLibre ở góc phải dưới,
// trang chi tiết tin có MiniMap ở góc phải dưới (listings/[id]/MiniMap.tsx).
function dock(pathname: string): { launcher: string; panel: string } {
  if (pathname.startsWith("/map")) return { launcher: "bottom-28 right-3", panel: "bottom-3 right-3" };
  if (/^\/listings\/\d+\/?$/.test(pathname)) return { launcher: "bottom-5 left-5", panel: "bottom-3 left-3" };
  return { launcher: "bottom-5 right-5", panel: "bottom-3 right-3" };
}

export default function ChatbotWidget() {
  const pathname = usePathname();
  const [mode, setMode] = useState<WidgetMode>("closed");
  const [turns, setTurns] = useState<Turn[]>([WELCOME]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // proxy trả 401 khi chưa đăng nhập — lịch sử chatbot gắn với tài khoản nên bắt buộc đăng nhập
  const [needLogin, setNeedLogin] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [moreConversations, setMoreConversations] = useState(false);
  const [olderTurns, setOlderTurns] = useState(false);
  const [firstSavedId, setFirstSavedId] = useState<number | null>(null);
  const epochRef = useRef(0);
  const restoreRef = useRef(true);
  const skipScrollRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const latestTurnRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (pathname === "/tro-ly") setMode("compact");
    if (pathname === "/login" || pathname === "/register") {
      epochRef.current++;
      setTurns([WELCOME]);
      setConversationId(null);
      setConversations([]);
      setShowHistory(false);
      setLoading(false);
      setError(null);
      setOlderTurns(false);
      setNeedLogin(false);
      restoreRef.current = true;
    }
  }, [pathname]);

  useEffect(() => {
    if (mode === "closed" || !restoreRef.current) return;
    restoreRef.current = false;
    const epoch = epochRef.current;
    void (async () => {
      try {
        const response = await fetch("/api/chatbot/conversations?limit=30", { cache: "no-store" });
        if (!response.ok || epoch !== epochRef.current) return;
        const data = await response.json();
        setConversations(data.items);
        setMoreConversations(data.has_more);
        if (data.items.length > 0) await openConversation(data.items[0].id, epoch);
      } catch { /* History can be retried from the history button. */ }
    })();
  }, [mode, pathname]);

  useEffect(() => {
    if (skipScrollRef.current) { skipScrollRef.current = false; return; }
    const container = scrollRef.current;
    const latest = latestTurnRef.current;
    if (!container) return;
    const assistant = turns[turns.length - 1]?.role === "assistant";
    const top = assistant && latest
      ? latest.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 12
      : container.scrollHeight;
    container.scrollTo({ top, behavior: "auto" });
  }, [turns.length, loading]);

  useEffect(() => {
    if (mode !== "closed") window.setTimeout(() => inputRef.current?.focus(), 180);
  }, [mode]);

  async function send(text: string) {
    const cleanText = text.trim();
    if (cleanText.length < 2 || loading) return;
    setMessage("");
    setError(null);
    setLoading(true);
    const epoch = ++epochRef.current;
    restoreRef.current = false;
    const history = turns
      .filter((turn) => turn.key !== "welcome")
      .slice(-10)
      .map((turn) => ({ role: turn.role, content: turn.content.slice(0, 2000) }));
    setTurns((items) => [
      ...items,
      { key: `user-${Date.now()}`, role: "user", content: cleanText },
    ]);
    try {
      const response = await fetch("/api/chatbot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: cleanText, conversation_id: conversationId, conversation_history: history,
          conversation_state: [...turns].reverse().find((turn) => turn.role === "assistant" && turn.conversationState)?.conversationState }),
      });
      if (response.status === 401) {
        setNeedLogin(true);
        throw new Error("Đăng nhập để dùng Trợ lý Trọ CTU — lịch sử trò chuyện được lưu theo tài khoản.");
      }
      setNeedLogin(false);
      const body = await response.json();
      if (!response.ok) {
        // 422 của FastAPI trả detail là mảng lỗi — không hiện nguyên văn cho người dùng
        throw new Error(typeof body.detail === "string" ? body.detail : "Không thể gửi câu hỏi");
      }
      const result = body as AskResponse;
      if (epoch !== epochRef.current) return;
      setConversationId(result.conversation_id ?? conversationId);
      setTurns((items) => [
        ...items,
        {
          key: `assistant-${Date.now()}`,
          role: "assistant",
          content: result.answer,
          conversationState: result.conversation_state,
          listings: result.listings,
          sources: result.sources,
          degraded: result.degraded,
          generationProvider: result.generation_provider,
          eventId: result.event_id,
          reusedAnswer: result.reused_answer,
        },
      ]);
    } catch (caught) {
      if (epoch === epochRef.current) setError(caught instanceof Error ? caught.message : "Đã có lỗi xảy ra");
    } finally {
      if (epoch === epochRef.current) setLoading(false);
    }
  }

  async function loadHistory(append = false) {
    setHistoryBusy(true);
    setHistoryError(null);
    const epoch = epochRef.current;
    try {
      const response = await fetch(`/api/chatbot/conversations?limit=30&offset=${append ? conversations.length : 0}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Không thể tải lịch sử");
      if (epoch !== epochRef.current) return;
      setConversations(items => append ? [...items, ...data.items] : data.items);
      setMoreConversations(data.has_more);
    } catch (caught) {
      if (epoch === epochRef.current) setHistoryError(caught instanceof Error ? caught.message : "Không thể tải lịch sử");
    } finally { setHistoryBusy(false); }
  }

  async function openConversation(id: string, expectedEpoch?: number, before?: number) {
    const epoch = expectedEpoch ?? ++epochRef.current;
    setHistoryBusy(true);
    setHistoryError(null);
    try {
      const response = await fetch(`/api/chatbot/conversations/${id}?limit=50${before ? `&before_id=${before}` : ""}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Không thể mở cuộc trò chuyện");
      if (epoch !== epochRef.current) return;
      const saved = data as SavedConversation;
      if (before) {
        skipScrollRef.current = true;
        setTurns(items => [WELCOME, ...savedTurns(saved.turns), ...items.filter(t => t.key !== "welcome")]);
      } else setTurns([WELCOME, ...savedTurns(saved.turns)]);
      setConversationId(id);
      setFirstSavedId(saved.turns[0]?.id ?? null);
      setOlderTurns(saved.has_more);
      setShowHistory(false);
      setError(null);
      setMessage("");
    } catch (caught) {
      if (epoch === epochRef.current) {
        const detail = caught instanceof Error ? caught.message : "Không thể mở cuộc trò chuyện";
        setHistoryError(detail);
        setError(detail);
      }
    } finally { setHistoryBusy(false); }
  }

  async function deleteConversation(id: string) {
    setHistoryBusy(true);
    setHistoryError(null);
    try {
      const response = await fetch(`/api/chatbot/conversations/${id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Không thể xóa cuộc trò chuyện");
      }
      setConversations(items => items.filter(item => item.id !== id));
      if (conversationId === id) resetConversation();
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Không thể xóa cuộc trò chuyện");
    } finally { setHistoryBusy(false); }
  }

  async function sendFeedback(key: string, eventId: number | null | undefined, rating: -1 | 1) {
    const response = await fetch("/api/chatbot/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId, rating }),
    });
    if (!response.ok) return;
    setTurns((items) => items.map((item) => (item.key === key ? { ...item, feedback: rating } : item)));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(message);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(message);
    }
  }

  function resetConversation() {
    epochRef.current++;
    restoreRef.current = false;
    setConversationId(null);
    setOlderTurns(false);
    setFirstSavedId(null);
    setShowHistory(false);
    setTurns([WELCOME]);
    setError(null);
    setMessage("");
  }

  // /chat (chat ghép bạn) chiếm cả màn hình, ô nhập tin ở đáy — nút nổi sẽ che nút gửi.
  if (pathname.startsWith("/admin") || pathname.startsWith("/chat")) return null;
  const position = dock(pathname);

  if (mode === "closed") {
    return (
      <button
        type="button"
        onClick={() => setMode("compact")}
        className={`group fixed ${position.launcher} z-[1200] flex items-center gap-3 rounded-full bg-primary p-3.5 text-white shadow-[0_12px_35px_rgba(0,74,143,0.38)] transition hover:-translate-y-1 hover:bg-navy focus:outline-none focus:ring-4 focus:ring-blue-200 sm:px-5`}
        aria-label="Mở Trợ lý Trọ CTU"
      >
        <span className="relative grid h-7 w-7 place-items-center">
          <Icon name="chat" />
          <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-primary bg-emerald-400" />
        </span>
        <span className="hidden text-sm font-semibold sm:inline">Trợ lý Trọ CTU</span>
      </button>
    );
  }

  const expanded = mode === "expanded";
  return (
    <section
      aria-label="Trợ lý tìm nhà trọ CTU"
      className={`fixed z-[1200] flex overflow-hidden border border-blue-100 bg-white shadow-[0_24px_70px_rgba(15,45,80,0.28)] transition-all duration-300 ${
        expanded
          ? "inset-0 rounded-none sm:inset-5 sm:rounded-3xl"
          : `${position.panel} h-[min(680px,calc(100dvh-1.5rem))] w-[min(400px,calc(100vw-1.5rem))] rounded-3xl`
      }`}
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative shrink-0 overflow-hidden bg-gradient-to-br from-primary-bright via-primary to-navy px-4 py-3.5 text-white">
          <div className="absolute -right-10 -top-14 h-36 w-36 rounded-full border border-white/10 bg-white/5" />
          <div className="relative flex flex-wrap items-center gap-3">
            {/* logo toàn tông xanh — đặt trên ô trắng, để thẳng trên nền gradient xanh thì chìm */}
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white shadow-sm">
              <img src="/brand/logo-mark.png" alt="" width={253} height={256} className="h-8 w-8 object-contain" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="truncate font-bold">Trợ lý Trọ CTU</h2>
              <p className="flex items-center gap-1.5 text-xs text-blue-100">
                <span className="h-2 w-2 rounded-full bg-emerald-300" />
                Tìm phòng · Ký túc xá · Hỏi đáp thuê trọ
              </p>
            </div>
            <button type="button" onClick={() => setMode("closed")} title="Đóng" className="rounded-xl p-2 text-blue-100 transition hover:bg-white/15 hover:text-white">
              <Icon name="close" />
            </button>
            <div className="flex w-full items-center gap-2 border-t border-white/10 pt-2">
            <button type="button" disabled={loading || historyBusy} onClick={() => { setShowHistory(!showHistory); if (!showHistory) void loadHistory(); }} title="Lịch sử trò chuyện" aria-label="Lịch sử trò chuyện" className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-xs text-blue-100 transition hover:bg-white/15 hover:text-white disabled:opacity-40">
              <Icon name="history" />
              Lịch sử
            </button>
            <button type="button" disabled={loading || historyBusy} onClick={resetConversation} title="Cuộc trò chuyện mới" className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-xs text-blue-100 transition hover:bg-white/15 hover:text-white disabled:opacity-40">
              <Icon name="reset" />
              Chat mới
            </button>
            <button type="button" onClick={() => setMode(expanded ? "compact" : "expanded")} title={expanded ? "Thu nhỏ" : "Phóng to"} className="ml-auto rounded-xl p-1 text-blue-100 transition hover:bg-white/15 hover:text-white">
              <Icon name={expanded ? "shrink" : "expand"} />
            </button>
            </div>
          </div>
        </header>

        {showHistory ? (
          <div className="min-h-0 flex-1 overflow-y-auto bg-paper p-4" aria-label="Lịch sử đã lưu">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="font-bold text-slate-800">Lịch sử của bạn</h3>
              <button type="button" onClick={() => setShowHistory(false)} className="text-xs font-medium text-primary">Quay lại chat</button>
            </div>
            {historyError && <p role="alert" className="mb-3 text-sm text-rose-700">{historyError}</p>}
            {!historyBusy && !historyError && conversations.length === 0 && <p className="text-sm text-slate-500">Chưa có cuộc trò chuyện đã lưu.</p>}
            <div className="space-y-2">
              {conversations.map(item => (
                <div key={item.id} className={`flex items-center gap-2 rounded-xl border bg-white p-3 ${item.id === conversationId ? "border-blue-400" : "border-blue-100"}`}>
                  <button type="button" disabled={historyBusy} onClick={() => void openConversation(item.id)} className="min-w-0 flex-1 text-left">
                    <p className="line-clamp-2 break-words text-sm font-medium text-slate-800">{item.title}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{item.turn_count} câu hỏi · {new Date(item.updated_at).toLocaleString("vi-VN")}</p>
                  </button>
                  <button type="button" disabled={historyBusy} aria-label={`Xóa cuộc trò chuyện: ${item.title}`} onClick={() => void deleteConversation(item.id)} className="shrink-0 rounded-lg px-2 py-1 text-xs text-rose-600 hover:bg-rose-50">Xóa</button>
                </div>
              ))}
            </div>
            {historyBusy && <p role="status" className="mt-3 text-xs text-slate-500">Đang tải lịch sử…</p>}
            {moreConversations && <button type="button" disabled={historyBusy} onClick={() => void loadHistory(true)} className="mt-3 text-sm font-medium text-primary">Xem lịch sử cũ hơn</button>}
          </div>
        ) : <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper px-3 py-4 sm:px-4">
          <div className={`mx-auto space-y-4 ${expanded ? "max-w-5xl" : "max-w-full"}`}>
            {olderTurns && conversationId && firstSavedId && <button type="button" disabled={historyBusy || loading} onClick={() => void openConversation(conversationId, undefined, firstSavedId)} className="text-xs font-medium text-primary">Xem tin nhắn cũ hơn</button>}
            {turns.map((turn, index) => (
              <article key={turn.key} ref={index === turns.length - 1 ? latestTurnRef : undefined} className={turn.role === "user" ? "ml-auto max-w-[85%] break-words [overflow-wrap:anywhere]" : "mr-auto min-w-0 max-w-full"}>
                <div
                  className={
                    turn.role === "user"
                      ? "ml-auto w-fit rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-6 text-white shadow-sm"
                      : "max-w-full rounded-2xl rounded-bl-md border border-blue-50 bg-white px-4 py-3 text-sm leading-6 text-slate-700 shadow-sm"
                  }
                >
                  {turn.role === "assistant" ? <ChatbotAnswer content={turn.content} sources={turn.sources} /> : turn.content}
                </div>
                {turn.reusedAnswer && <p className="mt-1 px-2 text-[11px] text-slate-500">Đã dùng lại câu trả lời đã lưu.</p>}
                {turn.degraded && (
                  <p className="mt-1.5 px-2 text-[11px] text-amber-700">
                    {turn.generationProvider === "template"
                      ? "Chưa có câu trả lời AI đáng tin cậy; đang hiển thị thông tin theo nguồn."
                      : "Câu trả lời còn giới hạn; hãy đọc lưu ý và đối chiếu nguồn."}
                  </p>
                )}
                {turn.role === "assistant" && turn.eventId && (
                  <div className="mt-2 flex items-center gap-2 px-2 text-[11px] text-slate-400">
                    <span>Câu trả lời hữu ích?</span>
                    <button type="button" onClick={() => void sendFeedback(turn.key, turn.eventId, 1)} className={`rounded-md px-2 py-1 ${turn.feedback === 1 ? "bg-emerald-100 text-emerald-700" : "bg-white hover:bg-emerald-50"}`}>Có</button>
                    <button type="button" onClick={() => void sendFeedback(turn.key, turn.eventId, -1)} className={`rounded-md px-2 py-1 ${turn.feedback === -1 ? "bg-rose-100 text-rose-700" : "bg-white hover:bg-rose-50"}`}>Không</button>
                  </div>
                )}
                {turn.listings && turn.listings.length > 0 && (
                  <div className={`mt-3 grid gap-3 ${expanded ? "md:grid-cols-2 xl:grid-cols-3" : "grid-cols-1"}`}>
                    {turn.listings.map((listing) => {
                      const suppliedCatalog = Boolean(listing.corpus_schema && listing.corpus_schema !== "public");
                      const sourceLink = catalogSource(listing.source_url);
                      const amenities = Object.entries(listing.amenities)
                        .filter(([key, value]) => value === true && amenityLabels[key])
                        .slice(0, 3);
                      return (
                        <div key={listing.id} className="group overflow-hidden rounded-2xl border border-blue-100 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                          <div className="h-1 bg-gradient-to-r from-primary to-cyan-400" />
                          <div className="p-3.5">
                            <div className="flex items-start justify-between gap-2">
                              <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-primary">Gợi ý #{listing.rank}</span>
                              <span className="text-[11px] font-semibold text-slate-400">Điểm gợi ý {Math.round(listing.similarity_score * 100)}/100</span>
                            </div>
                            <h3 className="mt-2 line-clamp-2 text-sm font-bold leading-5 text-slate-900">{listing.title}</h3>
                            <p className="mt-2 text-base font-black text-primary">{money(listing.price)}</p>
                            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                              {listing.area ? `${listing.area} m² · ` : ""}{listing.address || listing.district || "Chưa rõ địa chỉ"}
                            </p>
                            {distance(listing.distance_to_ctu) && <p className="mt-1 text-xs font-medium text-primary">⌖ {distance(listing.distance_to_ctu)}{suppliedCatalog ? " · đường chim bay ước tính" : ""}</p>}
                            {suppliedCatalog && <p className="mt-1 text-xs text-slate-500">Thông tin theo tin đăng; cần xác nhận giá và phòng còn trống.</p>}
                            {listing.match_reasons.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {listing.match_reasons.map((reason) => <span key={reason} className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">✓ {reason}</span>)}
                              </div>
                            )}
                            {amenities.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {amenities.map(([key]) => <span key={key} className="rounded-md bg-slate-100 px-2 py-1 text-[10px] text-slate-600">{amenityLabels[key]}</span>)}
                              </div>
                            )}
                            {suppliedCatalog ? (sourceLink ? <a href={sourceLink} target="_blank" rel="noopener noreferrer" className="mt-3 flex items-center justify-center rounded-xl bg-blue-50 px-3 py-2 text-xs font-bold text-primary">Đối chiếu tin nguồn</a> : <p className="mt-3 text-xs text-slate-500">Chưa có liên kết nguồn để đối chiếu.</p>) : <Link href={`/listings/${listing.id}`} className="mt-3 flex items-center justify-center rounded-xl bg-blue-50 px-3 py-2 text-xs font-bold text-primary transition group-hover:bg-primary group-hover:text-white">
                              Xem chi tiết phòng
                            </Link>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </article>
            ))}

            {turns.length === 1 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {QUICK_PROMPTS.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => void send(prompt)} className="rounded-full border border-blue-200 bg-white px-3 py-2 text-left text-xs font-medium text-primary shadow-sm transition hover:border-primary hover:bg-blue-50">
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {loading && (
              <div className="flex w-fit items-center gap-1 rounded-2xl rounded-bl-md border border-blue-50 bg-white px-4 py-3 shadow-sm" role="status" aria-label="Đang xử lý câu hỏi">
                {[0, 1, 2].map((index) => <span key={index} className="h-2 w-2 animate-bounce rounded-full bg-primary" style={{ animationDelay: `${index * 120}ms` }} />)}
                <span className="ml-2 text-xs text-slate-500">Đang đọc nguồn và trả lời…</span>
              </div>
            )}
          </div>
        </div>}

        {!showHistory && <form onSubmit={submit} className="shrink-0 border-t border-blue-100 bg-white p-3">
          <div className={`mx-auto ${expanded ? "max-w-5xl" : "max-w-full"}`}>
            {error && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
              {needLogin && <> <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="font-semibold underline">Đăng nhập</Link></>}
            </p>}
            <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-1.5 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100">
              <textarea
                ref={inputRef}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                maxLength={2000}
                placeholder="Tìm trọ hoặc hỏi quy định pháp luật..."
                className="max-h-24 min-h-[40px] min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
              />
              <button disabled={loading || message.trim().length < 2} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary text-white transition hover:bg-navy disabled:cursor-not-allowed disabled:opacity-40" aria-label="Gửi câu hỏi">
                <Icon name="send" />
              </button>
            </div>
            <p className="mt-1.5 text-center text-[10px] text-slate-400">Lịch sử được lưu theo tài khoản của bạn. Kiểm tra thông tin trước khi đặt cọc.</p>
          </div>
        </form>}
      </div>
    </section>
  );
}
