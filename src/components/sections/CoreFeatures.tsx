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
import { FEATURES } from "@/lib/constants";

export function CoreFeatures() {
  return (
    <Section id="features">
      <FadeInWhenVisible>
        <SectionHeading
          title="Core Features"
          subtitle="Five pillars that make Truebex the complete building design platform."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <motion.div key={feature.id} variants={staggerItem}>
            <GlassCard className="h-full">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 mb-4 transition-all duration-300 group-hover:bg-accent/20 group-hover:shadow-[0_0_20px_var(--color-accent-muted)]">
                <feature.icon className="h-6 w-6 text-accent transition-transform duration-300 group-hover:scale-110" />
              </div>
              <h3 className="text-xl font-semibold mb-2 transition-colors duration-300 group-hover:text-accent">{feature.title}</h3>
              <p className="text-text-secondary leading-relaxed transition-colors duration-300 group-hover:text-text-primary/80">
                {feature.description}
              </p>
            </GlassCard>
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
