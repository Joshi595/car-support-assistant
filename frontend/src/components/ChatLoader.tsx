"use client";

import dynamic from "next/dynamic";

// The chat lives in the browser: it reads the saved conversation and the browser language on first render.
export const ChatLoader = dynamic(() => import("@/components/Chat").then((m) => m.Chat), {
  ssr: false,
  loading: () => (
    <div className="mx-auto max-w-3xl px-4 pt-6 sm:px-6">
      <p className="font-display text-2xl font-bold tracking-tight">Northwind Motors</p>
      <p className="mt-1 font-display text-lg text-slate">Customer help</p>
    </div>
  ),
});
