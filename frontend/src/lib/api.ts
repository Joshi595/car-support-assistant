/** The customer API, reached through this app's own origin (src/app/backend forwards to the API). */
export const API_URL = "/backend";

export type Market = "uk" | "us" | "de";

export type Source = {
  n: number;
  doc_id: string;
  title: string;
  section: string;
  source_type: "brand" | "public";
  url: string | null;
  licence: string;
  attribution: string | null;
  excerpt: string;
};

export type Outcome =
  | "answer"
  | "refuse"
  | "off_topic"
  | "blocked"
  | "recall"
  | "chargers"
  | "handoff"
  | "clarify"
  | "unavailable";

export type Done = {
  message_id: number;
  answer: string;
  outcome: Outcome;
  sources: Source[];
  offer_handoff: boolean;
};

export async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
