import { Footer } from "@/components/layout/Footer";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">Legal</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{title}</h1>
        <p className="mt-4 text-sm text-text-muted">Last updated {updated}</p>
        <article className="prose-doc mt-8">{children}</article>
      </main>
      <Footer />
    </>
  );
}
