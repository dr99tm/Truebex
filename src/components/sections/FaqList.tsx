// Native <details> so answers are in the HTML (crawlable) and work without
// JS. Every page that shows a FaqList emits the same list as FAQPage
// structured data; `data-faq-question` lets the build checks compare them.
export function FaqList({ items }: { items: readonly { q: string; a: string }[] }) {
  return (
    <div className="mx-auto max-w-3xl divide-y divide-border rounded-[var(--radius-card)] border border-border bg-surface/60">
      {items.map((item) => (
        <details key={item.q} className="group px-5 py-4 [&_summary::-webkit-details-marker]:hidden">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-start font-medium text-text-primary">
            <h3 className="text-base" data-faq-question="">
              {item.q}
            </h3>
            <span
              aria-hidden
              className="text-xl leading-none text-text-muted transition-transform group-open:rotate-45"
            >
              +
            </span>
          </summary>
          <p className="mt-3 leading-relaxed text-text-secondary">{item.a}</p>
        </details>
      ))}
    </div>
  );
}
