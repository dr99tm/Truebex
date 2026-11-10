import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";
import { PASSWORD_RESET } from "@/lib/constants";

// A private page: noindex and no canonical (PF13b), never in the sitemap.
export const metadata: Metadata = {
  title: PASSWORD_RESET.forgot.metaTitle,
  description: PASSWORD_RESET.forgot.metaDescription,
  robots: { index: false, follow: true },
};

export default function ForgotPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <ForgotPasswordForm />
    </main>
  );
}
