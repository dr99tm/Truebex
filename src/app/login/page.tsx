import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/AuthForm";

export const metadata: Metadata = {
  title: "Log in",
  description: "Sign in to your Truebex dashboard with Google or email.",
  alternates: { canonical: "/login/" },
  robots: { index: false, follow: true },
};

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <AuthForm mode="login" />
    </main>
  );
}
