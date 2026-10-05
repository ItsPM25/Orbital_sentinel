"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Email and password are required");
      return;
    }
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) {
      router.push("/dashboard");
    } else {
      setError("Invalid email or password");
    }
  }

  return (
    <main>
      <h1>Orbital Sentinel - Login</h1>
      <form id="loginForm" onSubmit={onSubmit} noValidate>
        <p>
          <label htmlFor="email">Email</label>
          <br />
          <input id="email" name="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </p>
        <p>
          <label htmlFor="password">Password</label>
          <br />
          <input id="password" name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </p>
        <button id="loginBtn" type="submit">Login</button>
      </form>
      {error && (
        <p id="loginError" role="alert" style={{ color: "crimson" }}>
          {error}
        </p>
      )}
    </main>
  );
}
