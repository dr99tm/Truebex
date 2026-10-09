import { parseNotes, type Inline } from "@/lib/releaseNotes";

function InlineNodes({ nodes }: { nodes: Inline[] }) {
  return (
    <>
      {nodes.map((n, i) => {
        if (n.type === "text") return <span key={i}>{n.text}</span>;
        if (n.type === "bold") {
          return (
            <strong key={i} className="font-semibold text-text-primary">
              <InlineNodes nodes={n.children} />
            </strong>
          );
        }
        const external = /^https?:\/\//.test(n.href) && !n.href.startsWith("https://truebex.com");
        return (
          <a
            key={i}
            href={n.href}
            className="text-accent hover:underline"
            {...(external ? { rel: "noopener noreferrer" } : {})}
          >
            <InlineNodes nodes={n.children} />
          </a>
        );
      })}
    </>
  );
}

/** Release notes (the contract's subset: headings, bullets, bold, links).
 *  Everything is rendered as React text, so a manifest cannot inject HTML. */
export function ReleaseNotes({ md, className }: { md: string; className?: string }) {
  const blocks = parseNotes(md);
  return (
    <div className={className}>
      {blocks.map((b, i) => {
        if (b.type === "heading") {
          const Tag = b.level <= 3 ? "h3" : "h4";
          return (
            <Tag key={i} className="mt-5 mb-2 font-semibold text-text-primary first:mt-0">
              <InlineNodes nodes={b.inline} />
            </Tag>
          );
        }
        if (b.type === "list") {
          return (
            <ul key={i} className="my-3 list-disc space-y-1.5 pl-6 text-text-secondary">
              {b.items.map((item, j) => (
                <li key={j} className="leading-relaxed">
                  <InlineNodes nodes={item} />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="my-3 leading-relaxed text-text-secondary">
            <InlineNodes nodes={b.inline} />
          </p>
        );
      })}
    </div>
  );
}
