import type { Page } from "@playwright/test";

/** Mock the customer API (same-origin /backend/v1/...) inside the browser, before it reaches the server. */
export async function mockApi(page: Page, done: Record<string, unknown>, draft = "The battery warranty is ") {
  const calls: { path: string; body: unknown }[] = [];
  await page.route("**/backend/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/backend", "");
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    calls.push({ path, body: request.postDataJSON() });
    if (path === "/v1/chat") {
      const events = [
        sse("meta", { conversation_id: "c0ffee00-0000-4000-8000-000000000001" }),
        ...draft.split(" ").map((word) => sse("token", { text: `${word} ` })),
        sse("done", done),
      ];
      return route.fulfill({ status: 200, headers: { ...cors, "Content-Type": "text/event-stream" }, body: events.join("") });
    }
    if (path === "/v1/feedback") return route.fulfill({ status: 204, headers: cors });
    if (path === "/v1/handoff") return route.fulfill({ status: 201, headers: cors, json: { status: "handed_off" } });
    return route.fulfill({ status: 404, headers: cors, json: { detail: "not mocked" } });
  });
  return calls;
}

const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*" };

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export const ANSWER = {
  message_id: 7,
  answer: "The high-voltage battery warranty lasts **8 years or 100,000 miles** [1].",
  outcome: "answer",
  offer_handoff: false,
  sources: [
    {
      n: 1,
      doc_id: "brand/uk/en/warranty",
      title: "Warranty Coverage (United Kingdom)",
      section: "High-Voltage Battery Warranty",
      source_type: "brand",
      url: null,
      licence: "Fictional sample data",
      attribution: null,
      excerpt: "- Duration: 8 years or 100,000 miles, whichever comes first.",
    },
  ],
};
