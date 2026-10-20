"use client";

import { useCallback, useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { Answer } from "@/components/Answer";
import type { Source } from "@/lib/api";

type Status = "open" | "in_progress" | "resolved";
type TicketRow = {
  id: number;
  conversation_id: string;
  market: string;
  reason: string;
  status: Status;
  assigned_to: string | null;
  created_at: string;
  last_customer_message: string | null;
};
type TicketDetail = TicketRow & {
  messages: { id: number; role: "user" | "assistant"; content: string; outcome: string | null; sources: Source[]; rating: number | null }[];
};
type FeedbackRow = {
  message_id: number;
  conversation_id: string;
  market: string;
  rating: number;
  comment: string | null;
  question: string | null;
  answer: string;
  created_at: string;
};

const REASONS: Record<string, string> = {
  customer_request: "Asked for a person",
  refusal: "Assistant couldn't answer",
  negative_feedback: "Rated an answer unhelpful",
  unavailable: "Assistant was unavailable",
};
const STATUSES: { value: Status; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
];

async function agentApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/agent/${path}`, init);
  if (!response.ok) throw new Error(`${response.status}`);
  return (await response.json()) as T;
}

function since(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(`${iso}Z`).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`;
}

/** Feedback as golden-set candidates: the question is real, the expected facts are for a person to add. */
function downloadGolden(rows: FeedbackRow[]) {
  const lines = rows
    .filter((r) => r.question)
    .map((r) =>
      JSON.stringify({
        id: `fb-${r.message_id}`,
        category: "natural",
        market: r.market,
        language: r.market === "de" ? "de" : "en",
        question: r.question,
        route: "kb",
        relevant: [],
        facts: [],
        note: `from feedback ${r.created_at}: ${r.comment ?? "no comment"}. Check the language; add relevant and facts.`,
      }),
    );
  const url = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "application/jsonl" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: "golden-candidates.jsonl" });
  link.click();
  URL.revokeObjectURL(url);
}

export function AgentDesk() {
  const { data: session, status: sessionStatus } = useSession({ required: true });
  const [view, setView] = useState<"tickets" | "feedback">("tickets");
  const [filter, setFilter] = useState<Status>("open");
  const [tickets, setTickets] = useState<TicketRow[] | null>(null);
  const [selected, setSelected] = useState<TicketDetail | null>(null);
  const [feedback, setFeedback] = useState<FeedbackRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadTickets = useCallback(() => {
    agentApi<TicketRow[]>(`tickets?status_filter=${filter}`)
      .then((rows) => {
        setTickets(rows);
        setError(null);
      })
      .catch(() => setError("The support API can't be reached. Check that the backend is running."));
  }, [filter]);

  useEffect(() => {
    if (sessionStatus !== "authenticated") return;
    loadTickets();
    const timer = setInterval(loadTickets, 20000); // new handoffs show up without a reload
    return () => clearInterval(timer);
  }, [sessionStatus, loadTickets]);

  useEffect(() => {
    if (sessionStatus === "authenticated" && view === "feedback") {
      agentApi<FeedbackRow[]>("feedback?rating=-1").then(setFeedback).catch(() => setFeedback([]));
    }
  }, [sessionStatus, view]);

  async function open(id: number) {
    setSelected(await agentApi<TicketDetail>(`tickets/${id}`));
  }

  async function setStatus(status: Status) {
    if (!selected) return;
    await agentApi(`tickets/${selected.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    await open(selected.id);
    loadTickets();
  }

  if (sessionStatus !== "authenticated") return <p className="p-8 text-slate">Checking your sign-in…</p>;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
        <div className="flex items-baseline gap-6">
          <p className="font-display text-xl font-bold tracking-tight">Northwind support desk</p>
          <nav className="flex gap-1" aria-label="Views">
            {(["tickets", "feedback"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                aria-current={view === v ? "page" : undefined}
                className={`rounded-md px-3 py-1 font-display text-base ${view === v ? "bg-fjord-soft text-ink" : "text-slate hover:text-ink"}`}
              >
                {v === "tickets" ? "Handoffs" : "Unhelpful answers"}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate">
          <span>{session?.user?.email}</span>
          <button type="button" onClick={() => void signOut({ callbackUrl: "/agent/signin" })} className="underline underline-offset-2">
            Sign out
          </button>
        </div>
      </header>
      {error && <p className="border-b border-line bg-surface px-6 py-2 text-danger">{error}</p>}

      {view === "tickets" ? (
        <div className="grid flex-1 md:grid-cols-[22rem_1fr]">
          <aside className="border-line md:border-r">
            <div className="flex gap-1 p-3" role="group" aria-label="Ticket status">
              {STATUSES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => {
                    setFilter(s.value);
                    setSelected(null);
                  }}
                  aria-pressed={filter === s.value}
                  className={`rounded-md border px-3 py-1 text-sm ${filter === s.value ? "border-fjord bg-fjord-soft" : "border-line"}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            {tickets?.length === 0 && <p className="px-4 py-6 text-slate">No {STATUSES.find((s) => s.value === filter)?.label.toLowerCase()} handoffs.</p>}
            <ul>
              {tickets?.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => void open(t.id)}
                    className={`w-full border-t border-line px-4 py-3 text-left ${selected?.id === t.id ? "bg-surface" : "hover:bg-surface"}`}
                  >
                    <span className="flex justify-between gap-2 text-sm text-slate">
                      <span>{REASONS[t.reason] ?? t.reason}</span>
                      <span>
                        {t.market.toUpperCase()}, {since(t.created_at)}
                      </span>
                    </span>
                    <span className="mt-1 line-clamp-2 block">{t.last_customer_message ?? "No message"}</span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="px-6 py-6">
            {!selected ? (
              <p className="text-slate">Choose a handoff to see the conversation and the sources the assistant used.</p>
            ) : (
              <div className="max-w-3xl">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h1 className="font-display text-2xl font-semibold">{REASONS[selected.reason] ?? selected.reason}</h1>
                  <div className="flex gap-2">
                    {selected.status !== "in_progress" && selected.status !== "resolved" && (
                      <button type="button" onClick={() => void setStatus("in_progress")} className="rounded-md bg-fjord px-4 py-2 font-display font-semibold text-white dark:text-[#0e1b27]">
                        Take this handoff
                      </button>
                    )}
                    {selected.status !== "resolved" && (
                      <button type="button" onClick={() => void setStatus("resolved")} className="rounded-md border border-line px-4 py-2 font-display font-semibold">
                        Mark resolved
                      </button>
                    )}
                  </div>
                </div>
                <p className="mt-1 text-sm text-slate">
                  {selected.assigned_to ? `Assigned to ${selected.assigned_to}` : "Not assigned yet"}. Customer details are
                  redacted in the transcript.
                </p>
                <ol className="mt-6 space-y-6">
                  {selected.messages.map((m) =>
                    m.role === "user" ? (
                      <li key={m.id} className="rounded-xl bg-fjord-soft px-4 py-3">
                        <span className="block text-xs text-slate">Customer</span>
                        {m.content}
                      </li>
                    ) : (
                      <li key={m.id}>
                        <span className="mb-1 block text-xs text-slate">
                          Assistant{m.rating === -1 ? ", rated unhelpful" : m.rating === 1 ? ", rated helpful" : ""}
                        </span>
                        <Answer text={m.content} sources={m.sources} />
                      </li>
                    ),
                  )}
                </ol>
              </div>
            )}
          </section>
        </div>
      ) : (
        <section className="mx-auto w-full max-w-4xl px-6 py-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-2xl font-semibold">Answers customers rated unhelpful</h1>
            <button
              type="button"
              disabled={!feedback?.length}
              onClick={() => downloadGolden(feedback ?? [])}
              className="rounded-md border border-line px-4 py-2 font-display font-semibold disabled:opacity-50"
            >
              Download as test questions
            </button>
          </div>
          <p className="mt-1 max-w-[70ch] text-sm text-slate">
            Each one becomes a candidate for the evaluation set: add the expected facts and sources, then the next
            evaluation run checks the fix.
          </p>
          {feedback?.length === 0 && <p className="mt-6 text-slate">No answers have been rated unhelpful.</p>}
          <ul className="mt-6 space-y-5">
            {feedback?.map((f) => (
              <li key={f.message_id} className="border-l-[3px] border-line pl-4">
                <p className="font-semibold">{f.question}</p>
                <p className="mt-1 line-clamp-3 text-slate">{f.answer}</p>
                {f.comment && <p className="mt-1 text-sm">&ldquo;{f.comment}&rdquo;</p>}
                <p className="mt-1 text-xs text-slate">{since(f.created_at)}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
