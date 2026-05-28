"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { login, register } from "@/lib/auth";

type Mode = "login" | "signup";

const inputClass =
  "w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isSignup = mode === "signup";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (isSignup) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      router.push("/account");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <h1 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
        {isSignup ? (
          <>
            Create your <span className="gradient-text">Truebex</span> account
          </>
        ) : (
          <>
            Welcome <span className="gradient-text">back</span>
          </>
        )}
      </h1>
      <p className="mt-3 text-center text-text-secondary">
        {isSignup
          ? "Sign up with your email and a password."
          : "Log in to continue."}
      </p>

      <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email Address"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete={isSignup ? "new-password" : "current-password"}
          required
          minLength={isSignup ? 8 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />
        {isSignup && (
          <p className="text-xs text-text-muted">
            Must be at least 8 characters.
          </p>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={loading}>
          {loading
            ? "Please wait..."
            : isSignup
              ? "Create account"
              : "Log in"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-text-secondary">
        {isSignup ? (
          <>
            Already have an account?{" "}
            <a href="/login" className="text-accent hover:underline">
              Log in
            </a>
          </>
        ) : (
          <>
            Don&apos;t have an account?{" "}
            <a href="/signup" className="text-accent hover:underline">
              Sign up
            </a>
          </>
        )}
      </p>
    </div>
  );
}
