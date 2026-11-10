import type { Metadata } from "next";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { PASSWORD_RESET } from "@/lib/constants";

// A private page reached from a reset e-mail: noindex, no canonical (PF13b),
// never in the sitemap, and no Footer, so no analytics beacon loads beside
// the token in the fragment.
export const metadata: Metadata = {
  title: PASSWORD_RESET.reset.metaTitle,
  description: PASSWORD_RESET.reset.metaDescription,
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <ResetPasswordForm />
    </main>
  );
}
