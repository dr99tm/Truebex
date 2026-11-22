import { Mail, MessageCircle } from "lucide-react";
import { SITE, whatsappHref } from "@/lib/constants";

const base =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] px-8 text-base font-medium transition-all duration-300";
const primary = `${base} bg-accent text-background hover:bg-accent-hover`;
const secondary = `${base} border border-accent text-accent hover:bg-accent hover:text-background`;

export interface ContactCopy {
  email: string;
  whatsapp: string;
  subject: string;
  whatsappText: string;
  note: string;
  privacy: string;
}

/**
 * The pre-launch call to action: write to us by email or WhatsApp to join the
 * early-adopter or tester list. Both land in Truebex Desk. The WhatsApp
 * button shows only once the site has a number (SITE.whatsapp).
 */
export function ContactButtons({ copy, privacyHref = "/privacy/" }: { copy: ContactCopy; privacyHref?: string }) {
  const wa = whatsappHref(copy.whatsappText);
  return (
    <div data-contact="early-adopters">
      <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
        <a href={`mailto:${SITE.email}?subject=${encodeURIComponent(copy.subject)}`} data-contact-channel="email" className={primary}>
          <Mail size={18} className="me-2" aria-hidden />
          {copy.email}
        </a>
        {wa && (
          <a href={wa} data-contact-channel="whatsapp" rel="noopener noreferrer" className={secondary}>
            <MessageCircle size={18} className="me-2" aria-hidden />
            {copy.whatsapp}
          </a>
        )}
      </div>
      <p className="mt-4 text-sm text-text-secondary" dir="ltr">
        {SITE.email}
      </p>
      <p className="mx-auto mt-6 max-w-md text-xs leading-relaxed text-text-muted">
        {copy.note}{" "}
        <a href={privacyHref} className="underline hover:text-text-secondary">
          {copy.privacy}
        </a>
      </p>
    </div>
  );
}
