import { AuthForm } from "@/components/auth/AuthForm";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <AuthForm mode="signup" />
    </main>
  );
}
