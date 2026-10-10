import { Noto_Sans_Arabic } from "next/font/google";

// An OFL-licensed Arabic sans, loaded on /ar/ only so the other pages stay
// light (Open Sans has no Arabic glyphs). Segoe UI, the app's font, follows
// it in the stack.
const arabic = Noto_Sans_Arabic({
  subsets: ["arabic"],
  display: "swap",
  variable: "--font-arabic",
});

/**
 * The Arabic landing page's wrapper: lang and dir for the content, and the
 * Arabic font for the whole page (the navbar sits outside this wrapper, in
 * the root layout). The served HTML's <html lang="ar" dir="rtl"> is written
 * after the build by scripts/postbuild-lang.mjs, because the root layout
 * renders one <html> for every route.
 */
export default function ArabicLayout({ children }: { children: React.ReactNode }) {
  const family = `${arabic.style.fontFamily}, var(--font-sans)`;
  return (
    <div lang="ar" dir="rtl" className={arabic.variable} style={{ fontFamily: family }}>
      <style>{`html[lang="ar"] body{font-family:${family}}`}</style>
      {children}
    </div>
  );
}
