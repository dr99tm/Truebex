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
import { AUDIENCES } from "@/lib/constants";

export function WhoItsFor() {
  return (
    <Section id="who-its-for">
      <FadeInWhenVisible>
        <SectionHeading
          title="Who It's For"
          subtitle="Built for every stakeholder in the building lifecycle."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {AUDIENCES.map((audience) => (
          <motion.div key={audience.title} variants={staggerItem}>
            <GlassCard className="h-full flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10 transition-all duration-300 group-hover:bg-accent/20 group-hover:shadow-[0_0_20px_var(--color-accent-muted)]">
                <audience.icon className="h-6 w-6 text-accent transition-transform duration-300 group-hover:scale-110" />
              </div>
              <div>
                <h3 className="text-lg font-semibold transition-colors duration-300 group-hover:text-accent">{audience.title}</h3>
                <p className="mt-1 text-sm text-text-secondary leading-relaxed transition-colors duration-300 group-hover:text-text-primary/80">
                  {audience.description}
                </p>
              </div>
            </GlassCard>
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
