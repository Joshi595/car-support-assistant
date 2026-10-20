"use client";

import { SessionProvider } from "next-auth/react";

export function AgentProviders({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
