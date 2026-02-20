"use client";

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

export function Pricing() {
  return (
    <Section id="pricing">
      <FadeInWhenVisible>
        <SectionHeading
          title="Pricing"
          subtitle="Start free. Scale when you're ready."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="grid gap-6 md:grid-cols-3 max-w-5xl mx-auto">
        {PRICING_PLANS.map((plan) => (
          <motion.div key={plan.name} variants={staggerItem}>
            <div
              className={cn(
                "group relative rounded-[var(--radius-card)] p-6 h-full flex flex-col",
                plan.highlighted
                  ? "glass-card border-accent/30"
                  : "glass-card"
              )}
            >
              {plan.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-accent px-4 py-1 text-xs font-semibold text-background">
                    Most Popular
                  </span>
                </div>
              )}

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
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
