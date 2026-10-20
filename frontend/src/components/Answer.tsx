"use client";

import { useId, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Source } from "@/lib/api";

/** Turn "[1]" and "[1, 3]" into links the renderer below shows as citation tabs. */
function linkCitations(text: string): string {
  return text.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, group: string) =>
    group
      .split(",")
      .map((n) => `[${n.trim()}](#source-${n.trim()})`)
      .join(""),
  );
}

function licenceLabel(source: Source): string {
  if (source.source_type === "public") return source.licence === "OGL-3.0" ? "GOV.UK, Open Government Licence" : source.licence;
  return "Northwind documentation";
}

export function Answer({ text, sources }: { text: string; sources: Source[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const baseId = useId();
  const byNumber = new Map(sources.map((s) => [s.n, s]));

  return (
    <div>
      <div className="answer max-w-[68ch]">
        <ReactMarkdown
          components={{
            a: ({ href, children }) => {
              const n = href?.startsWith("#source-") ? Number(href.slice(8)) : null;
              if (n === null || !byNumber.has(n)) {
                return (
                  <a href={href} className="text-fjord underline underline-offset-2" target="_blank" rel="noreferrer">
                    {children}
                  </a>
                );
              }
              const source = byNumber.get(n)!;
              return (
                <button
                  type="button"
                  onClick={() => setOpen(open === n ? null : n)}
                  aria-expanded={open === n}
                  aria-controls={`${baseId}-${n}`}
                  title={`${source.title}: ${source.section}`}
                  className="mx-0.5 inline-flex h-[1.35em] min-w-[1.35em] -translate-y-px items-center justify-center rounded-[3px] bg-amber px-1 align-middle font-display text-[0.75em] font-semibold text-amber-ink"
                >
                  <span className="sr-only">Source </span>
                  {n}
                </button>
              );
            },
          }}
        >
          {linkCitations(text)}
        </ReactMarkdown>
      </div>

      {sources.length > 0 && (
        <ul className="mt-3 space-y-1.5" aria-label="Sources">
          {sources.map((s) => (
            <li key={s.n}>
              <button
                type="button"
                onClick={() => setOpen(open === s.n ? null : s.n)}
                aria-expanded={open === s.n}
                aria-controls={`${baseId}-${s.n}`}
                className="group flex w-full items-baseline gap-2 text-left text-[0.9rem] text-slate hover:text-ink"
              >
                <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-[3px] bg-amber px-1 font-display text-xs font-semibold text-amber-ink">
                  {s.n}
                </span>
                <span>
                  <span className="text-ink">{s.title}</span>
                  {s.section && s.section !== s.title ? `, ${s.section}` : ""}
                </span>
              </button>
              {open === s.n && (
                <blockquote
                  id={`${baseId}-${s.n}`}
                  className="answer mt-2 mb-3 ml-7 border-l-[3px] border-amber bg-surface px-4 py-3 text-[0.95rem]"
                >
                  <ReactMarkdown>{s.excerpt}</ReactMarkdown>
                  <footer className="mt-2 text-xs text-slate">
                    {licenceLabel(s)}
                    {s.url && (
                      <>
                        {". "}
                        <a href={s.url} target="_blank" rel="noreferrer" className="text-fjord underline underline-offset-2">
                          Open the original page
                        </a>
                      </>
                    )}
                  </footer>
                </blockquote>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
