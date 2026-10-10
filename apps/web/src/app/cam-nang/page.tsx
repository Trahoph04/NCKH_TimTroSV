import Link from "next/link";
import SiteHeader from "../SiteHeader";
import { REFERENCES, SECTIONS, UPDATED_AT, type Basis } from "./content";

export const metadata = {
  title: "Cẩm nang | Trọ CTU",
  description: "Lưu ý khi tìm phòng, khi ở ghép và thông tin pháp lý, hợp đồng thuê trọ cho sinh viên ĐH Cần Thơ",
};

function BasisLinks({ basis }: { basis: Basis[] }) {
  return (
    <div className="mt-4 border-t border-line-soft pt-3 text-[12.5px] leading-5 text-ink-muted">
      <span className="font-semibold text-ink-soft">Căn cứ: </span>
      {basis.map((b, i) => (
        <span key={b.label}>
          {i > 0 && " · "}
          {b.href ? (
            <a href={b.href} target="_blank" rel="noopener noreferrer" className="underline decoration-line hover:text-primary">
              {b.label}
            </a>
          ) : (
            b.label
          )}
        </span>
      ))}
    </div>
  );
}

// Cẩm nang thay cho "AI cảnh báo rủi ro" (dữ liệu tin không có nhãn lừa đảo để học) — nội dung ở content.ts
export default function HandbookPage() {
  return (
    <>
      <SiteHeader />
      <main className="bg-paper pb-16">
        <section className="bg-gradient-to-br from-primary-soft via-white to-paper px-5 pb-10 pt-12 sm:px-10">
          <div className="mx-auto max-w-5xl">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-primary">Cẩm nang</p>
            <h1 className="mt-3 text-3xl font-extrabold leading-tight text-ink sm:text-5xl">Thuê trọ an toàn cho sinh viên</h1>
            <p className="mt-5 max-w-2xl text-[17px] leading-8 text-ink-soft">
              Những điều nên kiểm tra khi tìm phòng, khi ở ghép và khi ký giấy tờ — gom từ kinh nghiệm của sinh viên đi
              trước, cảnh báo của cơ quan công an và văn bản pháp luật hiện hành.
            </p>
            <p className="mt-3 text-sm text-ink-muted">Bản tạm, cập nhật {UPDATED_AT} · nội dung sẽ được bổ sung thêm.</p>
          </div>
        </section>

        <nav aria-label="Mục lục cẩm nang" className="sticky top-0 z-20 border-y border-line bg-white/95 px-5 backdrop-blur sm:px-10">
          <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto py-2 text-[15px] font-semibold">
            {SECTIONS.map((section, index) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="shrink-0 rounded-full px-4 py-2 text-ink-soft transition hover:bg-tint hover:text-primary"
              >
                {index + 1}. {section.short}
              </a>
            ))}
          </div>
        </nav>

        <div className="mx-auto max-w-5xl px-5 sm:px-0">
          {SECTIONS.map((section, index) => (
            <section key={section.id} id={section.id} className="scroll-mt-20 pt-12">
              <h2 className="text-2xl font-extrabold text-ink sm:text-3xl">
                <span className="mr-2 text-primary">{index + 1}.</span>
                {section.title}
              </h2>
              <p className="mt-3 max-w-3xl leading-7 text-ink-soft">{section.intro}</p>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {section.tips.map((tip) => (
                  <article
                    key={tip.id}
                    id={`${section.id}-${tip.id}`}
                    className="scroll-mt-20 rounded-2xl border border-line bg-white p-5 shadow-sm"
                  >
                    <h3 className="text-lg font-bold text-ink">{tip.title}</h3>
                    {tip.lead && <p className="mt-2 text-[14.5px] leading-6 text-ink-muted">{tip.lead}</p>}
                    <ul className="mt-3 space-y-2.5">
                      {tip.items.map((item) => (
                        <li key={item} className="flex gap-2.5 text-[14.5px] leading-6 text-ink-soft">
                          <span aria-hidden="true" className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">
                            ✓
                          </span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                    {tip.basis && <BasisLinks basis={tip.basis} />}
                  </article>
                ))}
              </div>

              {section.id === "phap-ly" && (
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-primary px-5 py-4 text-white">
                  <p className="text-[15px]">Tình huống cụ thể của bạn? Trợ lý AI trả lời kèm trích dẫn điều luật.</p>
                  <Link href="/tro-ly" className="rounded-[10px] bg-white px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary-soft">
                    Hỏi Trợ lý AI
                  </Link>
                </div>
              )}
            </section>
          ))}

          <section className="mt-14 border-t border-line pt-6 text-[13px] leading-6 text-ink-muted">
            <h2 className="font-semibold text-ink-soft">Nguồn tham khảo</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {REFERENCES.map((r) => (
                <li key={r.label}>
                  {r.href ? (
                    <a href={r.href} target="_blank" rel="noopener noreferrer" className="underline decoration-line hover:text-primary">
                      {r.label}
                    </a>
                  ) : (
                    r.label
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-3">
              Nội dung mang tính tham khảo, không thay thế tư vấn pháp lý. Luôn đối chiếu với hợp đồng thực tế và văn bản
              gốc.
            </p>
          </section>
        </div>
      </main>
    </>
  );
}
