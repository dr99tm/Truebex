"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { LayoutDashboard, LogOut } from "lucide-react";
import { logout, type User } from "@/lib/auth";

/** Circular avatar showing the first letter of the user's email. */
function Avatar({ email, size = 36 }: { email: string; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full bg-accent/15 font-semibold uppercase text-accent ring-1 ring-accent/30"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {email.charAt(0)}
    </span>
  );
}

/** Signed-in Navbar control: avatar button that opens a dropdown menu. */
export function ProfileMenu({ user }: { user: User }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function handleLogout() {
    logout();
    setOpen(false);
    router.push("/");
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full p-0.5 transition-transform hover:scale-105"
        aria-label="Open account menu"
        aria-expanded={open}
      >
        <Avatar email={user.email} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-60 overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface-elevated shadow-[0_8px_32px_#00000050]"
          >
            <div className="flex items-center gap-3 border-b border-border px-4 py-3">
              <Avatar email={user.email} size={40} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-text-primary">
                  {user.email}
                </p>
                <p className="text-xs text-text-muted">Signed in</p>
              </div>
            </div>
            <nav className="p-1.5">
              <a
                href="/account"
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-white/5 hover:text-text-primary"
              >
                <LayoutDashboard size={16} />
                Dashboard
              </a>
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-white/5 hover:text-red-400"
              >
                <LogOut size={16} />
                Log out
              </button>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
