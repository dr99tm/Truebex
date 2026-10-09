"use client";

import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GlassCard } from "@/components/ui/GlassCard";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import {
  StaggerChildren,
  staggerItem,
} from "@/components/animations/StaggerChildren";
import { FEATURES, FEATURE_PAGE_UI, ROADMAP_PAGE } from "@/lib/constants";
import { homeRoadmap, roadmapIcon, STATUS_CLASS } from "@/lib/roadmap";
import { cn } from "@/lib/utils";

export function CoreFeatures() {
  const roadmap = homeRoadmap();
  return (
    <Section id="features">
      <FadeInWhenVisible>
        <SectionHeading
          title="What only Truebex does"
          subtitle="Nine capabilities at the heart of the platform, all shipping today."
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
              {"href" in feature && (
                <a
                  href={feature.href}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
                >
                  {FEATURE_PAGE_UI.learnMore}
                  <ArrowRight size={14} aria-hidden />
                </a>
              )}
            </GlassCard>
          </motion.div>
        ))}
      </StaggerChildren>

      <FadeInWhenVisible>
        <div className="mt-16 rounded-[var(--radius-card)] border border-dashed border-border p-6 md:p-8">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-warn">
            {ROADMAP_PAGE.homeTitle}
          </h3>
          <ul className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {roadmap.map((item) => {
              const Icon = roadmapIcon(item.icon);
              return (
                <li key={item.id} className="flex gap-3" data-roadmap-item={item.id} data-status={item.status}>
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-text-muted" aria-hidden />
                  <div>
                    <p className="font-medium text-text-primary">{item.title}</p>
                    <p className="mt-1 text-sm text-text-secondary">{item.description}</p>
                    <span
                      className={cn(
                        "mt-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium",
                        STATUS_CLASS[item.status]
                      )}
                    >
                      {ROADMAP_PAGE.status[item.status]}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          <a
            href="/roadmap/"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
          >
            {ROADMAP_PAGE.homeLink}
            <ArrowRight size={14} aria-hidden />
          </a>
        </div>
      </FadeInWhenVisible>
    </Section>
  );
}
