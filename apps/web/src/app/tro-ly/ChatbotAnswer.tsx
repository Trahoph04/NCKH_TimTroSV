"use client";

import { Fragment, useRef, useState, type ReactNode } from "react";

type Reference = {
  rank: number;
  title: string;
  heading: string | null;
  page_from: number | null;
  page_to: number | null;
  excerpt?: string | null;
  source_url?: string | null;
  page_kind?: 'physical_pdf' | 'logical_document' | 'web_excerpt' | 'editorial_guidance' | null;
};

function publicSource(value?: string | null): string | null {
  try {
    const url = new URL(value || '');
    const signedWaterDecision = url.hostname === 'capnuoccantho2.com.vn' && url.pathname === '/View.aspx' && url.searchParams.get('wc') === '63' && url.searchParams.get('wp') === '332';
    const providerInstructions = (url.hostname === 'ctn-cantho.com.vn' && url.pathname === '/tin-khoa-hoc-cong-nghe/huong-dan-truy-cap-website-de-tra-cuu-va-tai-hoa-don-tien-nuoc-331.html')
      || (url.hostname === 'hddt.ctn-cantho.com.vn' && url.pathname === '/')
      || (url.hostname === 'capnuoccantho2.com.vn' && url.pathname === '/View.aspx' && url.searchParams.get('wp') === '253');
    return url.protocol === 'https:' && !url.username && !url.password && !url.port && (url.hostname.endsWith('.gov.vn') || url.hostname.endsWith('.chinhphu.vn') || url.hostname.endsWith('.ctu.edu.vn') || signedWaterDecision || providerInstructions) ? url.href : null;
  } catch { return null; }
}

function answerDisplay(content: string) {
  const answer: string[] = [];
  for (const line of content.split("\n")) {
    const text = line.trim();
    const normalized = text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/đ/g, "d");
    // Hide only Word provenance notices; keep answer gaps, legal conditions
    // and follow-up questions in their original position.
    if (/^nguon\b/.test(normalized) && /\bword\b/.test(normalized)
      && /chua.{0,40}(?:doi chieu|xac minh)/.test(normalized)) {
      continue;
    } else {
      answer.push(line);
    }
  }
  const cleaned = answer.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return cleaned;
}

export default function ChatAnswer({ content, sources = [] }: { content: string; sources?: Reference[] }) {
  const [expanded, setExpanded] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const sourcePanel = useRef<HTMLDetailsElement>(null);
  const answer = answerDisplay(content);
  const long = answer.length > 600;
  const cut = Math.max(answer.lastIndexOf("\n", 420), answer.lastIndexOf(" ", 420));
  const visible = long && !expanded ? `${answer.slice(0, cut > 0 ? cut : 420)}…` : answer;

  function inline(text: string): ReactNode[] {
    return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\])/g).map((part, index): ReactNode => {
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{inline(part.slice(2, -2))}</strong>;
      if (part.startsWith("*") && part.endsWith("*")) return <em key={index}>{inline(part.slice(1, -1))}</em>;
      const citation = /^\[(\d+)\]$/.exec(part);
      const rank = citation ? Number(citation[1]) : null;
      if (rank !== null && sources.some((source) => source.rank === rank)) {
        return <button key={index} type="button" aria-label={`Xem nguồn ${rank}`}
          className="mx-0.5 inline-flex rounded bg-blue-50 px-1.5 text-xs font-semibold text-primary hover:bg-blue-100"
          onClick={() => {
            setShowSources(true);
            setSelected(rank);
            // Focus without scrolling the outer page or hiding the widget header.
            sourcePanel.current?.querySelector("summary")?.focus({ preventScroll: true });
          }}>{part}</button>;
      }
      // React escapes model output: never interpret HTML or arbitrary Markdown URLs.
      return <Fragment key={index}>{part}</Fragment>;
    });
  }

  const lines = visible.split(/\n+/).filter((line) => line.trim());
  const blocks = [];
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(?:[-*•]|\d+[.)])\s+/.test(lines[i])) {
      const items = [];
      const start = i;
      while (i < lines.length && /^\s*(?:[-*•]|\d+[.)])\s+/.test(lines[i])) {
        items.push(<li key={i}>{inline(lines[i].replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""))}</li>);
        i++;
      }
      i--;
      blocks.push(<ul key={start} className="list-disc space-y-2 pl-5 marker:text-blue-500">{items}</ul>);
    } else {
      blocks.push(<p key={i}>{inline(lines[i].replace(/^#{1,6}\s+/, ""))}</p>);
    }
  }

  return <div className="min-w-0 space-y-3 break-words [overflow-wrap:anywhere]">
    <div className="space-y-3" data-testid="chat-answer">{blocks}</div>
    {long && <button type="button" aria-expanded={expanded} className="text-xs font-semibold text-primary"
      onClick={() => setExpanded(!expanded)}>{expanded ? "Thu gọn câu trả lời" : "Xem toàn bộ câu trả lời"}</button>}
    {sources.length > 0 && <details ref={sourcePanel} open={showSources}
      onToggle={(event) => setShowSources(event.currentTarget.open)}
      className="rounded-xl border border-blue-100 bg-slate-50 text-xs">
      <summary className="cursor-pointer px-3 py-2 font-semibold text-primary">Nguồn tham khảo ({sources.length})</summary>
      <div className="space-y-2 px-3 pb-3">
        {sources.map((source) => <div key={source.rank} className={`rounded-lg border p-2.5 ${selected === source.rank ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white"}`}>
          <p className="font-semibold text-slate-700">[{source.rank}] {source.title}</p>
          {source.heading && <p className="mt-1 text-slate-500">{source.heading}</p>}
          {source.page_kind === 'editorial_guidance' ? <p className="text-slate-500">Hướng dẫn biên soạn, cần đối chiếu căn cứ</p> : source.page_kind === 'web_excerpt' ? <p className="text-slate-500">Trích từ trang thông tin</p> : source.page_from && <p className="text-slate-500">{source.page_kind === 'logical_document' ? 'Trang trong bản trích' : 'Trang'} {source.page_from}{source.page_to && source.page_to !== source.page_from ? `–${source.page_to}` : ""}</p>}
          {publicSource(source.source_url) && <a href={publicSource(source.source_url)!} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block font-medium text-primary underline">Đối chiếu nguồn công bố</a>}
          {source.excerpt && <details className="mt-2">
            <summary className="cursor-pointer text-primary">Đọc trích đoạn</summary>
            <p className="mt-2 whitespace-pre-line border-l-2 border-blue-200 pl-2 leading-5 text-slate-600">{source.excerpt}</p>
            <p className="mt-1 text-[10px] text-slate-400">Trích đoạn, không phải toàn bộ văn bản.</p>
          </details>}
        </div>)}
      </div>
    </details>}
  </div>;
}
