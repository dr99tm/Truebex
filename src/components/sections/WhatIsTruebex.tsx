"use client";

import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { Layers, Eye, ShoppingCart } from "lucide-react";

const highlights = [
  { icon: Layers, label: "5-in-1 Platform" },
  { icon: Eye, label: "Real-Time VR" },
  { icon: ShoppingCart, label: "Market Integration" },
];

export function WhatIsTruebex() {
  return (
    <Section id="about">
      <FadeInWhenVisible>
        <SectionHeading
          title="What is Truebex?"
          subtitle="A platform built around truth — from concept to construction."
        />
      </FadeInWhenVisible>

      <div className="grid gap-12 md:grid-cols-2 md:items-center">
        <FadeInWhenVisible direction="left">
          <div className="space-y-6">
            <p className="text-lg leading-relaxed text-text-secondary">
              Truebex is a next-generation building design platform that unifies
              concept design, real-world material selection, accurate
              measurements, construction calculations, and instant VR
              experience — all in a single workflow.
            </p>
            <p className="text-lg leading-relaxed text-text-secondary">
              This is not a rendering tool. It is a platform where what you
              design is what gets built. Geometry is real. Materials are real.
              The experience of the space — visual, spatial, and measurable — is
              real.
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
                  <item.icon className="h-6 w-6 text-accent" />
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
