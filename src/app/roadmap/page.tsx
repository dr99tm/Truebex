import type { Metadata } from "next";
import { Footer } from "@/components/layout/Footer";
import { ROADMAP_PAGE } from "@/lib/constants";
import { roadmapByTheme, roadmapIcon, STATUS_CLASS } from "@/lib/roadmap";
import { breadcrumbLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";
import { cn } from "@/lib/utils";

export const metadata: Metadata = pageMetadata({
  title: ROADMAP_PAGE.title,
  description: ROADMAP_PAGE.description,
  path: "/roadmap/",
});

export default function RoadmapPage() {
  const groups = roadmapByTheme();
  const ld = ldJson([
    webPageLd({ name: ROADMAP_PAGE.heading, description: ROADMAP_PAGE.description, path: "/roadmap/" }),
    breadcrumbLd([
      { name: "Truebex", path: "/" },
      { name: ROADMAP_PAGE.title, path: "/roadmap/" },
    ]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-28 md:px-8">
        <header className="max-w-3xl">
          <p className="text-sm font-medium uppercase tracking-wider text-warn">{ROADMAP_PAGE.eyebrow}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{ROADMAP_PAGE.heading}</h1>
          <p className="mt-5 text-lg text-text-secondary">{ROADMAP_PAGE.intro}</p>
          <ul className="mt-6 flex flex-wrap gap-2" aria-label="Status key">
            {(["planned", "in_progress", "shipped"] as const).map((s) => (
              <li key={s} className={cn("rounded-full border px-3 py-1 text-xs font-medium", STATUS_CLASS[s])}>
                {ROADMAP_PAGE.status[s]}
              </li>
            ))}
          </ul>
        </header>

        {groups.map(({ theme, items }) => (
          <section key={theme.id} className="mt-14">
            <h2 className="text-2xl font-bold tracking-tight">{theme.title}</h2>
            <ul className="mt-6 grid gap-4 sm:grid-cols-2">
              {items.map((item) => {
                const Icon = roadmapIcon(item.icon);
                return (
                  <li
                    key={item.id}
                    id={item.id}
                    data-roadmap-item={item.id}
                    data-status={item.status}
                    className="flex gap-4 rounded-[var(--radius-card)] border border-dashed border-border bg-surface/40 p-5"
                  >
                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-text-muted" aria-hidden />
                    <div>
                      <h3 className="font-semibold text-text-primary">{item.title}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-text-secondary">{item.description}</p>
                      <span
                        className={cn(
                          "mt-3 inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium",
                          STATUS_CLASS[item.status]
                        )}
                      >
                        {ROADMAP_PAGE.status[item.status]}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </main>
      <Footer />
    </>
  );
}
