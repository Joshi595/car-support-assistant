import type { Metadata } from "next";
import { AgentProviders } from "@/components/AgentProviders";

export const metadata: Metadata = { title: "Northwind support desk" };

export default function AgentLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AgentProviders>{children}</AgentProviders>;
}
