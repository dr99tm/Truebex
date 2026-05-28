import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <AuthForm mode="login" />
    </main>
  );
}
