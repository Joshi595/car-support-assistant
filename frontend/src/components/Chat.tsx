"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Answer } from "@/components/Answer";
import { API_URL, type Done, type Market, postJson, type Source } from "@/lib/api";
import { readEvents } from "@/lib/sse";

type Turn = {
  key: string;
  role: "user" | "assistant";
  text: string;
  streaming?: boolean;
  messageId?: number;
  sources?: Source[];
  offerHandoff?: boolean;
  rating?: 1 | -1;
  error?: boolean;
};

type HandoffState = "idle" | "sending" | "done";

const MARKETS: { value: Market; label: string }[] = [
  { value: "uk", label: "United Kingdom" },
  { value: "us", label: "United States" },
  { value: "de", label: "Deutschland" },
];

const SUGGESTIONS: Record<Market, string[]> = {
  uk: ["How long is the battery warranty?", "How much does a home charger cost?", "When is my first MOT due?"],
  us: ["How long is the bumper-to-bumper warranty?", "Can I return my car if I don't like it?", "Which charging port does the Ion 4 have?"],
  de: ["Wie lange gilt die Garantie für einen Neuwagen?", "Was kostet die Wallbox?", "Brauche ich Winterreifen?"],
};

const STORAGE_KEY = "northwind-conversation";

function guessMarket(): Market {
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("de")) return "de";
  return lang === "en-us" ? "us" : "uk";
}

function savedConversation(): { id: string; market: Market } | null {
  const saved = sessionStorage.getItem(STORAGE_KEY);
  return saved ? (JSON.parse(saved) as { id: string; market: Market }) : null;
}

/** Browser-only (rendered with ssr: false): reads sessionStorage and the browser language directly. */
export function Chat() {
  const [market, setMarket] = useState<Market>(() => savedConversation()?.market ?? guessMarket());
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [handoff, setHandoff] = useState<HandoffState>("idle");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Restore the conversation after a reload.
  useEffect(() => {
    const saved = savedConversation();
    if (!saved) return;
    const { id } = saved;
    fetch(`${API_URL}/v1/conversations/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((c: { status: string; messages: { id: number; role: Turn["role"]; content: string; sources: Source[] }[] }) => {
        setConversationId(id);
        setHandoff(c.status === "handed_off" ? "done" : "idle");
        setTurns(c.messages.map((m) => ({ key: `m${m.id}`, role: m.role, text: m.content, messageId: m.id, sources: m.sources })));
      })
      .catch(() => sessionStorage.removeItem(STORAGE_KEY));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  function updateLast(change: Partial<Turn>) {
    setTurns((all) => [...all.slice(0, -1), { ...all[all.length - 1], ...change }]);
  }

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setInput("");
    setTurns((all) => [
      ...all,
      { key: crypto.randomUUID(), role: "user", text },
      { key: crypto.randomUUID(), role: "assistant", text: "", streaming: true },
    ]);
    try {
      const response = await postJson("/v1/chat", { market, message: text, conversation_id: conversationId });
      if (response.status === 429) throw new Error("rate");
      if (!response.ok) throw new Error(String(response.status));
      let draft = "";
      for await (const { event, data } of readEvents(response)) {
        if (event === "meta") {
          const id = (data as { conversation_id: string }).conversation_id;
          setConversationId(id);
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ id, market }));
        } else if (event === "token") {
          draft += (data as { text: string }).text;
          updateLast({ text: draft });
        } else if (event === "done") {
          const done = data as Done;
          updateLast({
            text: done.answer,
            streaming: false,
            messageId: done.message_id,
            sources: done.sources,
            offerHandoff: done.offer_handoff,
          });
          if (done.outcome === "handoff") setHandoff("done");
        }
      }
    } catch (error) {
      const rate = error instanceof Error && error.message === "rate";
      updateLast({
        streaming: false,
        error: true,
        text: rate
          ? "You're sending messages faster than we can answer. Wait a minute, then send your question again."
          : "The assistant can't be reached right now. Check your connection and send your question again.",
      });
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  async function rate(turn: Turn, rating: 1 | -1) {
    if (!conversationId || !turn.messageId) return;
    setTurns((all) => all.map((t) => (t.key === turn.key ? { ...t, rating, offerHandoff: t.offerHandoff || rating === -1 } : t)));
    await postJson("/v1/feedback", { conversation_id: conversationId, message_id: turn.messageId, rating });
  }

  async function requestHandoff(reason: string) {
    if (!conversationId) return;
    setHandoff("sending");
    const response = await postJson("/v1/handoff", { conversation_id: conversationId, reason });
    setHandoff(response.ok ? "done" : "idle");
  }

  function changeMarket(next: Market) {
    setMarket(next);
    setConversationId(null);
    setTurns([]);
    setHandoff("idle");
    sessionStorage.removeItem(STORAGE_KEY);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(input);
    }
  }

  const lastAssistant = [...turns].reverse().find((t) => t.role === "assistant" && !t.streaming);
  const handoffReason = lastAssistant?.rating === -1 ? "negative_feedback" : lastAssistant?.error ? "unavailable" : "refusal";

  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pt-6 pb-4">
        <div>
          <p className="font-display text-2xl leading-none font-bold tracking-tight">Northwind Motors</p>
          <h1 className="mt-1 font-display text-lg font-medium text-slate">Customer help</h1>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate">
          Your market
          <select
            value={market}
            onChange={(e) => changeMarket(e.target.value as Market)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 font-display text-base text-ink"
          >
            {MARKETS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </header>
      <p className="py-2 text-xs text-slate">
        Northwind Motors is fictional. Answers come from sample documents and public GOV.UK guidance; recall
        checks use live NHTSA data.
      </p>

      <main className="flex-1 py-6" aria-live="polite" aria-busy={busy}>
        {turns.length === 0 ? (
          <section className="pt-10">
            <h2 className="font-display text-4xl leading-tight font-semibold text-balance sm:text-5xl">
              Ask anything about your Northwind.
            </h2>
            <p className="mt-3 max-w-[56ch] text-slate">
              Warranty, servicing, charging, ordering, finance, recalls or chargers near you. Every answer shows the
              document it comes from.
            </p>
            <ul className="mt-8 flex flex-col items-start gap-2">
              {SUGGESTIONS[market].map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => void ask(s)}
                    className="rounded-full border border-line bg-surface px-4 py-2 text-left text-[0.95rem] hover:border-fjord"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <ol className="space-y-8">
            {turns.map((turn) =>
              turn.role === "user" ? (
                <li key={turn.key} className="flex justify-end">
                  <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-fjord-soft px-4 py-2.5">{turn.text}</p>
                </li>
              ) : (
                <li key={turn.key}>
                  {turn.streaming ? (
                    <p className={`max-w-[68ch] whitespace-pre-wrap text-slate ${turn.text ? "caret" : ""}`}>
                      {turn.text || <span className="caret">Looking it up</span>}
                    </p>
                  ) : turn.error ? (
                    <p className="max-w-[68ch] text-danger">{turn.text}</p>
                  ) : (
                    <Answer text={turn.text} sources={turn.sources ?? []} />
                  )}
                  {!turn.streaming && !turn.error && turn.messageId && (
                    <div className="mt-3 flex items-center gap-1 text-sm text-slate">
                      <span className="mr-1">Was this helpful?</span>
                      {([1, -1] as const).map((value) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => void rate(turn, value)}
                          aria-pressed={turn.rating === value}
                          className={`rounded-md border px-2.5 py-1 ${
                            turn.rating === value ? "border-fjord bg-fjord-soft text-ink" : "border-line hover:border-fjord"
                          }`}
                        >
                          {value === 1 ? "Yes" : "No"}
                        </button>
                      ))}
                    </div>
                  )}
                </li>
              ),
            )}
          </ol>
        )}

        {handoff !== "done" && lastAssistant && (lastAssistant.offerHandoff || lastAssistant.error) && conversationId && (
          <div className="mt-8 flex flex-wrap items-center gap-3 border-l-[3px] border-fjord pl-4">
            <p className="text-[0.95rem]">A colleague from customer service can take it from here.</p>
            <button
              type="button"
              disabled={handoff === "sending"}
              onClick={() => void requestHandoff(handoffReason)}
              className="rounded-md bg-fjord px-4 py-2 font-display font-semibold text-white disabled:opacity-60 dark:text-[#0e1b27]"
            >
              Talk to a person
            </button>
          </div>
        )}
        {handoff === "done" && (
          <p className="mt-8 border-l-[3px] border-fjord pl-4 text-[0.95rem]">
            A colleague will pick this up. They can see this conversation, so you won&apos;t need to repeat yourself.
          </p>
        )}
        <div ref={endRef} />
      </main>

      <form onSubmit={onSubmit} className="sticky bottom-0 border-t border-line bg-glacier pt-3 pb-5">
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id="question"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            maxLength={2000}
            placeholder="Ask about warranty, charging, service…"
            className="max-h-40 min-h-12 flex-1 resize-none rounded-xl border border-line bg-surface px-4 py-3 [field-sizing:content] placeholder:text-slate"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="h-12 rounded-xl bg-fjord px-5 font-display text-lg font-semibold text-white disabled:opacity-50 dark:text-[#0e1b27]"
          >
            Send
          </button>
        </div>
        <p className="mt-2 text-xs text-slate">Don&apos;t share card numbers or passwords. Contact details you type are removed before storage.</p>
      </form>
    </div>
  );
}
