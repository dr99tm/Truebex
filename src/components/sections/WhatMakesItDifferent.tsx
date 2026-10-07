"use client";

import { motion } from "motion/react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { PRINCIPLES } from "@/lib/constants";

export function WhatMakesItDifferent() {
  return (
    <Section id="why-truebex">
      <FadeInWhenVisible>
        <SectionHeading
          title="Built on three ideas"
          subtitle="Everything in Truebex follows from them."
        />
      </FadeInWhenVisible>

      <StaggerChildren className="mx-auto grid max-w-5xl gap-6 md:grid-cols-3">
        {PRINCIPLES.map((p, i) => (
          <motion.div
            key={p.title}
            variants={staggerItem}
            className="glass rounded-[var(--radius-card)] p-6"
          >
            <span className="font-mono text-sm text-accent">0{i + 1}</span>
            <h3 className="mt-3 text-xl font-semibold">{p.title}</h3>
            <p className="mt-2 leading-relaxed text-text-secondary">{p.description}</p>
          </motion.div>
        ))}
      </StaggerChildren>
    </Section>
  );
}
