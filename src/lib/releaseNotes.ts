// Release notes: the contract's Markdown subset (licence-api.md §6.4: headings,
// bullets, bold and links) parsed into a small tree that React renders, so
// no HTML from a manifest ever reaches the page. Rejected: a full Markdown
// library (a dependency and a raw-HTML surface for four constructs).
//
// No imports and only erasable TypeScript, so `node` can run this file
// directly (server/tests/test_site_pf1.py checks it).

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; children: Inline[] }
  | { type: "link"; href: string; children: Inline[] };

export type Block =
  | { type: "heading"; level: number; inline: Inline[] }
  | { type: "list"; items: Inline[][] }
  | { type: "paragraph"; inline: Inline[] };

const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const BULLET = /^\s*[*-]\s+(.*)$/;
const LINK = /^\[([^\]\n]+)\]\(([^)\s]+)\)/;

/** Only web links and same-site paths become links; anything else stays text. */
export function safeHref(href: string): string | null {
  if (/^https?:\/\/[^\s]+$/i.test(href)) return href;
  if (/^\/(?!\/)[^\s]*$/.test(href) || /^#[^\s]*$/.test(href)) return href;
  return null;
}

function pushText(out: Inline[], text: string): void {
  if (!text) return;
  const last = out[out.length - 1];
  if (last && last.type === "text") last.text += text;
  else out.push({ type: "text", text });
}

function pushAll(out: Inline[], nodes: Inline[]): void {
  for (const n of nodes) {
    if (n.type === "text") pushText(out, n.text);
    else out.push(n);
  }
}

export function parseInline(src: string, inBold = false): Inline[] {
  const out: Inline[] = [];
  let i = 0;
  while (i < src.length) {
    if (!inBold && src.startsWith("**", i)) {
      const end = src.indexOf("**", i + 2);
      if (end > i + 2) {
        out.push({ type: "bold", children: parseInline(src.slice(i + 2, end), true) });
        i = end + 2;
        continue;
      }
    }
    if (src[i] === "[") {
      const m = LINK.exec(src.slice(i));
      if (m) {
        const href = safeHref(m[2]);
        const label = parseInline(m[1], inBold);
        if (href) out.push({ type: "link", href, children: label });
        else pushAll(out, label);
        i += m[0].length;
        continue;
      }
    }
    // Plain text up to the next character that could start markup.
    let j = i + 1;
    while (j < src.length && src[j] !== "[" && !(src[j] === "*" && src[j + 1] === "*")) j++;
    pushText(out, src.slice(i, j));
    i = j;
  }
  return out;
}

export function parseNotes(md: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: Inline[][] | null = null;

  const flush = () => {
    if (para.length) {
      blocks.push({ type: "paragraph", inline: parseInline(para.join(" ")) });
      para = [];
    }
    if (list) {
      blocks.push({ type: "list", items: list });
      list = null;
    }
  };

  for (const raw of (md ?? "").replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flush();
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      flush();
      blocks.push({ type: "heading", level: h[1].length, inline: parseInline(h[2]) });
      continue;
    }
    const b = BULLET.exec(line);
    if (b) {
      if (para.length) flush();
      list ??= [];
      list.push(parseInline(b[1].trim()));
      continue;
    }
    if (list) flush();
    para.push(line.trim());
  }
  flush();
  return blocks;
}

/** The notes as plain text (meta descriptions, previews). */
export function notesText(md: string): string {
  const text = (nodes: Inline[]): string =>
    nodes.map((n) => (n.type === "text" ? n.text : text(n.children))).join("");
  return parseNotes(md)
    .flatMap((b) => (b.type === "list" ? b.items.map(text) : [text(b.inline)]))
    .join(" ");
}
