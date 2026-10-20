# Frontend

Next.js 16 (App Router, TypeScript, Tailwind CSS 4). Two parts:

- **`/`**: the customer chat. Streams answers from `POST /backend/v1/chat` (this app forwards it to the API, so the browser only ever talks to one origin), shows citations as amber tabs that open the cited passage with its source and licence, collects feedback, and offers a person when the assistant cannot help.
- **`/agent`**: the support desk for signed-in agents (next-auth): handoff queue with transcripts and sources, take/resolve, and unhelpful answers exportable as evaluation questions. Agent calls go through `src/app/api/agent/[...path]`, which checks the session and calls the backend with a 5-minute token; the shared secret never reaches the browser.

```bash
cp .env.example .env.local   # fill NEXTAUTH_SECRET, AGENT_JWT_SECRET (= backend CS_AGENT_JWT_SECRET), AGENT_EMAILS
npm install
npm run dev                  # http://127.0.0.1:3000 (the API must run on API_URL, default :8000)
npm run lint && npm run typecheck
npm run test:e2e             # Playwright smoke tests against a mocked API (uses installed Edge locally)
```

Agent sign-in: GitHub OAuth when `GITHUB_ID`/`GITHUB_SECRET` are set (a free OAuth app), and/or a team password (`AGENT_DEV_PASSWORD`) for local use and demos. Only emails in `AGENT_EMAILS` get in; an empty list lets nobody in.
