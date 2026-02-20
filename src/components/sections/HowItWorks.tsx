"use client";

import { motion } from "motion/react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { STEPS } from "@/lib/constants";

export function HowItWorks() {
  return (
    <Section id="how-it-works">
      <FadeInWhenVisible>
        <SectionHeading
          title="How It Works"
          subtitle="From first sketch to VR walkthrough — in four seamless steps."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="relative grid gap-8 md:grid-cols-4">
        {/* Connecting line (desktop) */}
        <div className="absolute top-10 left-0 right-0 hidden h-[1px] bg-gradient-to-r from-transparent via-accent/30 to-transparent md:block" />

        {STEPS.map((step, i) => (
          <motion.div key={step.number} variants={staggerItem}>
            <div className="relative flex flex-col items-center text-center md:items-center">
              {/* Step number */}
              <div className="relative z-10 flex h-20 w-20 items-center justify-center rounded-full border border-accent/30 bg-background text-2xl font-bold text-accent">
                {step.number}
              </div>
              <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-text-secondary leading-relaxed">
                {step.description}
              </p>
            </div>
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
