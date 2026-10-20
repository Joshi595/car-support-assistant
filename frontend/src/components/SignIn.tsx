"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { type ClientSafeProvider, getProviders, signIn } from "next-auth/react";

export function SignIn() {
  const [providers, setProviders] = useState<ClientSafeProvider[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    getProviders().then((p) => setProviders(Object.values(p ?? {})));
  }, []);

  async function withPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const result = await signIn("password", {
      email: form.get("email"),
      password: form.get("password"),
      redirect: false,
    });
    if (result?.ok) router.push("/agent");
    else setError("That email is not on the agent list, or the team password is wrong.");
  }

  const github = providers?.find((p) => p.id === "github");
  const password = providers?.find((p) => p.id === "password");

  return (
    <main className="mx-auto max-w-md px-4 pt-20">
      <p className="font-display text-2xl font-bold tracking-tight">Northwind support desk</p>
      <h1 className="mt-1 font-display text-lg text-slate">Sign in to see handoffs and feedback</h1>

      {providers?.length === 0 && (
        <p className="mt-8 border-l-[3px] border-danger pl-4">
          No sign-in method is configured. Set GITHUB_ID and GITHUB_SECRET, or AGENT_DEV_PASSWORD for local
          use, and list agents in AGENT_EMAILS.
        </p>
      )}
      {github && (
        <button
          type="button"
          onClick={() => void signIn("github", { callbackUrl: "/agent" })}
          className="mt-8 w-full rounded-xl bg-ink px-4 py-3 font-display text-lg font-semibold text-glacier"
        >
          Sign in with GitHub
        </button>
      )}
      {password && (
        <form onSubmit={withPassword} className="mt-8 space-y-4">
          <label className="block">
            <span className="text-sm text-slate">Work email</span>
            <input
              name="email"
              type="email"
              required
              autoComplete="username"
              className="mt-1 w-full rounded-xl border border-line bg-surface px-4 py-3"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate">Team password</span>
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className="mt-1 w-full rounded-xl border border-line bg-surface px-4 py-3"
            />
          </label>
          {error && <p className="text-danger">{error}</p>}
          <button type="submit" className="w-full rounded-xl bg-fjord px-4 py-3 font-display text-lg font-semibold text-white dark:text-[#0e1b27]">
            Sign in
          </button>
        </form>
      )}
    </main>
  );
}
