import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/AuthForm";

export const metadata: Metadata = {
  title: "Create your free account",
  description:
    "Create a free Truebex account with Google or email. Get your dashboard and developer API keys in seconds.",
  alternates: { canonical: "/signup/" },
};

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <AuthForm mode="signup" />
    </main>
  );
}
