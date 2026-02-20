"use client";

import { cn } from "@/lib/utils";

interface GlassCardProps {
  className?: string;
  children: React.ReactNode;
}

export function GlassCard({ className, children }: GlassCardProps) {
  return (
    <div
      className={cn(
        "group glass-card rounded-[var(--radius-card)] p-6",
        className
      )}
    >
      {children}
    </div>
  );
}
