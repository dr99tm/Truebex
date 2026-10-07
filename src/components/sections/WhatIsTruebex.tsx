"use client";

import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { Sun, LayoutPanelTop, Layers } from "lucide-react";

const highlights = [
  { icon: Sun, label: "Measured daylight" },
  { icon: LayoutPanelTop, label: "Self-arranging surfaces" },
  { icon: Layers, label: "Update everywhere" },
];

export function WhatIsTruebex() {
  return (
    <Section id="about">
      <FadeInWhenVisible>
        <SectionHeading
          title="What is Truebex?"
          subtitle="A building design platform where what you draw is what you see — in real light, at real scale."
        />
      </FadeInWhenVisible>

      <div className="grid gap-12 md:grid-cols-2 md:items-center">
        <FadeInWhenVisible direction="left">
          <div className="space-y-6">
            <p className="text-lg leading-relaxed text-text-secondary">
              Truebex treats a building as one living model. The plan you draw,
              the surfaces you shape and the light that fills each room are the
              same thing — so there is nothing to export, nothing to re-render
              and nothing to fall out of step.
            </p>
            <p className="text-lg leading-relaxed text-text-secondary">
              Light is measured from the sun, the sky and the openings you
              placed. Patterns know the walls they sit on. Details you design
              once update everywhere they are used.
            </p>
          </div>
        </FadeInWhenVisible>

        <FadeInWhenVisible direction="right">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {highlights.map((item) => (
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
