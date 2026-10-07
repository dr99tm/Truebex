"use client";

import { motion } from "motion/react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GlassCard } from "@/components/ui/GlassCard";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { FEATURES, ROADMAP } from "@/lib/constants";

export function CoreFeatures() {
  return (
    <Section id="features">
      <FadeInWhenVisible>
        <SectionHeading
          title="What only Truebex does"
          subtitle="Six capabilities at the heart of the platform."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <motion.div key={feature.id} variants={staggerItem}>
            <GlassCard className="h-full">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 transition-all duration-300 group-hover:bg-accent/20 group-hover:shadow-[0_0_20px_var(--color-accent-muted)]">
                <feature.icon className="h-6 w-6 text-accent transition-transform duration-300 group-hover:scale-110" aria-hidden />
              </div>
              <h3 className="mb-2 text-xl font-semibold transition-colors duration-300 group-hover:text-accent">
                {feature.title}
              </h3>
              <p className="leading-relaxed text-text-secondary transition-colors duration-300 group-hover:text-text-primary/80">
                {feature.description}
              </p>
            </GlassCard>
          </motion.div>
        ))}
      </StaggerChildren>

      <FadeInWhenVisible>
        <div className="mt-16 rounded-[var(--radius-card)] border border-dashed border-border p-6 md:p-8">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-warn">
            On the roadmap
          </h3>
          <ul className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {ROADMAP.map((item) => (
              <li key={item.title} className="flex gap-3">
                <item.icon className="mt-0.5 h-5 w-5 shrink-0 text-text-muted" aria-hidden />
                <div>
                  <p className="font-medium text-text-primary">{item.title}</p>
                  <p className="mt-1 text-sm text-text-secondary">{item.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </FadeInWhenVisible>
    </Section>
  );
}
