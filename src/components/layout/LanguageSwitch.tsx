import { Languages } from "lucide-react";
import { LANGUAGE_SWITCH } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * English · العربية. A plain link (full page load), because the Arabic
 * page's <html lang="ar" dir="rtl"> is in its HTML, not set by the client.
 */
export function LanguageSwitch({
  current,
  className,
  onClick,
}: {
  current: "en" | "ar";
  className?: string;
  onClick?: () => void;
}) {
  const target = current === "ar" ? LANGUAGE_SWITCH.en : LANGUAGE_SWITCH.ar;
  return (
    <a
      href={target.href}
      hrefLang={target.lang}
      lang={target.lang}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary",
        className
      )}
    >
      <Languages size={15} aria-hidden />
      {target.label}
    </a>
  );
}
