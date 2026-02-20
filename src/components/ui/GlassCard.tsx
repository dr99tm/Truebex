"use client";

import { useRef, useCallback } from "react";
import { cn } from "@/lib/utils";

interface GlassCardProps {
  className?: string;
  children: React.ReactNode;
}

export function GlassCard({ className, children }: GlassCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current || !glowRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    glowRef.current.style.opacity = "1";
    glowRef.current.style.background = `radial-gradient(300px circle at ${x}px ${y}px, rgba(0, 191, 255, 0.15), transparent 70%)`;
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (!glowRef.current) return;
    glowRef.current.style.opacity = "0";
  }, []);

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "group relative rounded-[var(--radius-card)] p-6",
        "bg-[var(--color-glass)] backdrop-blur-[12px]",
        "border border-[var(--color-glass-border)]",
        "transition-all duration-400 ease-out",
        "hover:bg-[#ffffff0d] hover:border-[#ffffff22]",
        "hover:-translate-y-0.5",
        "hover:shadow-[0_8px_32px_#00000030]",
        className
      )}
    >
      {/* Mouse-tracking glow overlay */}
      <div
        ref={glowRef}
        className="pointer-events-none absolute inset-0 rounded-[var(--radius-card)] opacity-0 transition-opacity duration-400"
      />
      {/* Content above glow */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
