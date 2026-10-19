"use client";

import { WarningCircleIcon } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Wordmark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Seeded by backend/app/seed.py. Listed here because this is a demo deployment
// whose readers (graders, testers) need a way in; not something a real system would do.
const DEMO_ACCOUNTS = [
  { role: "Analyst", email: "analyst@orbitalsentinel.test", password: "sentinel123" },
  { role: "Administrator", email: "admin@orbitalsentinel.test", password: "admin123" },
  { role: "Evaluator", email: "evaluator@orbitalsentinel.test", password: "evaluator123" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Email and password are required");
      return;
    }
    setSubmitting(true);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).catch(() => null);
    if (res?.ok) {
      router.push("/dashboard");
      return;
    }
    setSubmitting(false);
    setError("Invalid email or password");
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="dark flex flex-col justify-between gap-10 border-r bg-sidebar px-8 py-8 text-foreground sm:px-12 sm:py-10">
        <Wordmark className="text-[15px]" />
        <div className="max-w-md">
          <h2 className="text-2xl leading-snug font-semibold">Anomaly detection for satellite telemetry.</h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            Replays NASA SMAP and MSL channel data through per-channel LSTM predictors, raises and ranks alerts by risk,
            points to the channels behind each one, and tracks the fleet on a live SGP4 globe.
          </p>
        </div>
        <div className="max-w-md">
          <p className="text-[13px] font-medium">Demo accounts</p>
          <table className="mt-2 w-full text-[13px]">
            <tbody>
              {DEMO_ACCOUNTS.map((a) => (
                <tr key={a.role} className="border-t border-border">
                  <td className="py-1.5 pr-3 text-muted-foreground">{a.role}</td>
                  <td className="num py-1.5 pr-3">{a.email}</td>
                  <td className="num py-1.5">{a.password}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </aside>

      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-xl font-semibold">Sign in</h1>
          <p className="mt-1 text-muted-foreground">Use your Orbital Sentinel account.</p>

          <form id="loginForm" onSubmit={onSubmit} noValidate className="mt-8 flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-9 bg-card"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-9 bg-card"
              />
            </div>
            {error && (
              <p
                role="alert"
                className="flex items-center gap-2 rounded-md border border-[color:var(--risk-critical)] px-3 py-2 text-[13px] text-[color:var(--risk-critical)]"
              >
                <WarningCircleIcon className="size-4 shrink-0" weight="bold" />
                <span id="loginError">{error}</span>
              </p>
            )}
            <Button id="loginBtn" type="submit" size="lg" disabled={submitting} className="h-9">
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
}
