"use client";

import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { ABOUT } from "@/lib/constants";

export function WhatIsTruebex() {
  return (
    <Section id="about">
      <FadeInWhenVisible>
        <SectionHeading
          title={ABOUT.title}
          subtitle={ABOUT.subtitle}
        />
      </FadeInWhenVisible>

      <div className="grid gap-12 md:grid-cols-2 md:items-center">
        <FadeInWhenVisible direction="left">
          <div className="space-y-6">
            {ABOUT.paragraphs.map((p) => (
              <p key={p} className="text-lg leading-relaxed text-text-secondary">
                {p}
              </p>
            ))}
          </div>
        </FadeInWhenVisible>

        <FadeInWhenVisible direction="right">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {ABOUT.highlights.map((item) => (
              <div
                key={item.label}
                className="glass flex flex-col items-center gap-3 rounded-[var(--radius-card)] p-6 text-center"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/10">
                  <item.icon className="h-6 w-6 text-accent" aria-hidden />
                </div>
                <span className="text-sm font-medium">{item.label}</span>
              </div>
            ))}
          </div>
        </FadeInWhenVisible>
      </div>
    </Section>
  );
}
