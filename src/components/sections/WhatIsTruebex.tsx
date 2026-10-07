"use client";

import Image from "next/image";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { Layers, Sun, Footprints } from "lucide-react";
import { PRODUCT_SHOTS } from "@/lib/constants";

const highlights = [
  { icon: Layers, label: "2D + 3D, one model" },
  { icon: Sun, label: "Lumen real-time light" },
  { icon: Footprints, label: "First-person walk" },
];

export function WhatIsTruebex() {
  const [hero, ...rest] = PRODUCT_SHOTS;
  return (
    <Section id="about">
      <FadeInWhenVisible>
        <SectionHeading
          title="What is Truebex?"
          subtitle="A building design tool where what you draw is what you see — in real light, at real scale."
        />
      </FadeInWhenVisible>

      <div className="grid gap-12 md:grid-cols-2 md:items-center">
        <FadeInWhenVisible direction="left">
          <div className="space-y-6">
            <p className="text-lg leading-relaxed text-text-secondary">
              Truebex is a Revit-style CAD tool — walls, rooms, openings,
              dimensions — built inside a real-time engine. The plan you draw
              and the building you see are one model, so there is nothing to
              export, nothing to re-render, and nothing to fall out of sync.
            </p>
            <p className="text-lg leading-relaxed text-text-secondary">
              It is not a rendering tool bolted onto a modeller. Geometry is
              exact, areas are live, and the light in the room is computed
              from the sun, the sky and the openings you placed.
            </p>
            <div className="grid grid-cols-3 gap-3">
              {highlights.map((item) => (
                <div
                  key={item.label}
                  className="glass flex flex-col items-center gap-2 rounded-[var(--radius-card)] p-4 text-center"
                >
                  <item.icon className="h-5 w-5 text-accent" aria-hidden />
                  <span className="text-xs font-medium sm:text-sm">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </FadeInWhenVisible>

        <FadeInWhenVisible direction="right">
          <figure className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface">
            <Image
              src={hero.src}
              alt={hero.alt}
              width={hero.width}
              height={hero.height}
              className="h-auto w-full"
              sizes="(min-width: 768px) 50vw, 100vw"
            />
            <figcaption className="px-4 py-3 text-sm text-text-muted">
              {hero.caption}
            </figcaption>
          </figure>
        </FadeInWhenVisible>
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {rest.map((shot) => (
          <FadeInWhenVisible key={shot.src}>
            <figure className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface">
              <Image
                src={shot.src}
                alt={shot.alt}
                width={shot.width}
                height={shot.height}
                className="aspect-[4/3] h-auto w-full object-cover"
                sizes="(min-width: 640px) 50vw, 100vw"
                loading="lazy"
              />
              <figcaption className="px-4 py-3 text-sm text-text-muted">
                {shot.caption}
              </figcaption>
            </figure>
          </FadeInWhenVisible>
        ))}
      </div>
      <p className="mt-4 text-center text-xs text-text-muted">
        Unretouched captures from the Truebex app.
      </p>
    </Section>
  );
}
