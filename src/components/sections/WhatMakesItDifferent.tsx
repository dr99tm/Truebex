"use client";

import { motion } from "motion/react";
import { X, Check } from "lucide-react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { DIFFERENTIATORS } from "@/lib/constants";

export function WhatMakesItDifferent() {
  return (
    <Section id="why-truebex">
      <FadeInWhenVisible>
        <SectionHeading
          title="What Makes Truebex Different"
          subtitle="We didn't optimize for pretty lies. We built for truth preservation."
        />
      </FadeInWhenVisible>

      {/* Comparison header */}
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 grid grid-cols-2 gap-4">
          <div className="text-center text-sm font-medium text-text-muted uppercase tracking-wider">
            Traditional Workflow
          </div>
          <div className="text-center text-sm font-medium text-accent uppercase tracking-wider">
            With Truebex
          </div>
        </div>

        <StaggerChildren className="space-y-4">
          {DIFFERENTIATORS.map((item, i) => (
            <motion.div
              key={i}
              variants={staggerItem}
              className="glass grid grid-cols-2 gap-4 rounded-[var(--radius-card)] p-4"
            >
              <div className="flex items-center gap-3 text-text-muted">
                <X className="h-4 w-4 shrink-0 text-red-400/60" />
                <span className="text-sm line-through decoration-text-muted/30">
                  {item.traditional}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <Check className="h-4 w-4 shrink-0 text-accent" />
                <span className="text-sm text-text-primary">
                  {item.truebex}
                </span>
              </div>
            </motion.div>
          ))}
        </StaggerChildren>
      </div>
    </Section>
  );
}
