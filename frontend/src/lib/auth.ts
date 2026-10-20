import "server-only";
import { timingSafeEqual } from "node:crypto";
import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GithubProvider from "next-auth/providers/github";

/** Agents allowed into the desk. Empty means nobody: access is never open by default. */
function allowedAgents(): Set<string> {
  return new Set(
    (process.env.AGENT_EMAILS ?? "")
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function isAgent(email: string | null | undefined): boolean {
  return Boolean(email) && allowedAgents().has(email!.toLowerCase());
}

function samePassword(given: string, expected: string): boolean {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

const providers: NextAuthOptions["providers"] = [];
if (process.env.GITHUB_ID && process.env.GITHUB_SECRET) {
  providers.push(GithubProvider({ clientId: process.env.GITHUB_ID, clientSecret: process.env.GITHUB_SECRET }));
}
// A shared password for local development and demos, off unless AGENT_DEV_PASSWORD is set.
const devPassword = process.env.AGENT_DEV_PASSWORD;
if (devPassword) {
  providers.push(
    CredentialsProvider({
      id: "password",
      name: "Email and team password",
      credentials: { email: { label: "Work email", type: "email" }, password: { label: "Team password", type: "password" } },
      authorize(credentials) {
        const email = credentials?.email?.trim().toLowerCase();
        if (!email || !credentials?.password || !isAgent(email) || !samePassword(credentials.password, devPassword)) {
          return null;
        }
        return { id: email, email };
      },
    }),
  );
}

export const authOptions: NextAuthOptions = {
  providers,
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  pages: { signIn: "/agent/signin" },
  callbacks: {
    signIn: ({ user }) => isAgent(user.email),
  },
};
