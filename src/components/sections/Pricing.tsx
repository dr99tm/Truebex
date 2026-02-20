"use client";

import { useRef, useCallback } from "react";
import { motion } from "motion/react";
import { Check } from "lucide-react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Button } from "@/components/ui/Button";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { PRICING_PLANS } from "@/lib/constants";
import { cn } from "@/lib/utils";

function PricingCard({ plan }: { plan: (typeof PRICING_PLANS)[number] }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current || !glowRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      glowRef.current.style.opacity = "1";
      glowRef.current.style.background = `radial-gradient(300px circle at ${x}px ${y}px, rgba(0, 191, 255, 0.15), transparent 70%)`;
    },
    []
  );

  const handleMouseLeave = useCallback(() => {
    if (!glowRef.current) return;
    glowRef.current.style.opacity = "0";
  }, []);

  return (
    <div className="relative pt-4">
      {/* Badge sits outside the card */}
      {plan.highlighted && (
        <div className="absolute -top-0 left-1/2 -translate-x-1/2 z-20">
          <span className="rounded-full bg-accent px-4 py-1 text-xs font-semibold text-background whitespace-nowrap">
            Most Popular
          </span>
        </div>
      )}

      <div
        ref={cardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className={cn(
          "group relative rounded-[var(--radius-card)] p-6 h-full flex flex-col",
          "bg-[var(--color-glass)] backdrop-blur-[12px]",
          "border transition-all duration-400 ease-out",
          "hover:bg-[#ffffff0d] hover:border-[#ffffff22]",
          "hover:-translate-y-0.5",
          "hover:shadow-[0_8px_32px_#00000030]",
          plan.highlighted
            ? "border-accent/30"
            : "border-[var(--color-glass-border)]"
        )}
      >
        {/* Mouse-tracking glow */}
        <div
          ref={glowRef}
          className="pointer-events-none absolute inset-0 rounded-[var(--radius-card)] opacity-0 transition-opacity duration-400"
        />

        <div className="relative z-10 flex flex-col flex-1">
          <div className="mb-6">
            <h3 className="text-lg font-semibold transition-colors duration-300 group-hover:text-accent">
              {plan.name}
            </h3>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-4xl font-bold">{plan.price}</span>
              {plan.period && (
                <span className="text-text-muted">{plan.period}</span>
              )}
            </div>
            <p className="mt-2 text-sm text-text-secondary">
              {plan.description}
            </p>
          </div>

          <ul className="mb-8 flex-1 space-y-3">
            {plan.features.map((feature) => (
              <li
                key={feature}
                className="flex items-start gap-3 text-sm text-text-secondary"
              >
                <Check className="h-4 w-4 shrink-0 mt-0.5 text-accent" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>

          <Button
            href="#contact"
            variant={plan.highlighted ? "primary" : "secondary"}
            className="w-full"
          >
            {plan.cta}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function Pricing() {
  return (
    <Section id="pricing">
      <FadeInWhenVisible>
        <SectionHeading
          title="Pricing"
          subtitle="Start free. Scale when you're ready."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 max-w-5xl mx-auto">
        {PRICING_PLANS.map((plan) => (
          <motion.div key={plan.name} variants={staggerItem}>
            <PricingCard plan={plan} />
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
