"use client";

import Image from "next/image";
import { motion } from "motion/react";
import { Button } from "@/components/ui/Button";
import { Lockup } from "@/components/brand/Logo";
import { PRODUCT_SHOT } from "@/lib/constants";

export function Hero() {
  return (
    <section className="relative overflow-hidden px-4 pt-32 pb-20 md:pt-40">
      {/* Drafting grid + soft brand-blue light */}
      <div className="pointer-events-none absolute inset-0">
        <div className="blueprint-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_25%,transparent_70%)]" />
        <div
          className="absolute left-1/2 top-24 h-[520px] w-[900px] -translate-x-1/2"
          style={{
            background:
              "radial-gradient(ellipse, rgba(160,206,255,0.08) 0%, rgba(91,157,255,0.03) 45%, transparent 70%)",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Lockup className="text-3xl sm:text-4xl" />
        </motion.div>

        <motion.p
          className="mt-5"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <span className="inline-block rounded-full border border-accent/25 bg-accent/5 px-4 py-1.5 text-sm text-accent">
            True Building Experience
          </span>
        </motion.p>

        <motion.h1
          className="mt-8 text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl md:text-7xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
        >
          See it before you <span className="gradient-text">build it.</span>
        </motion.h1>

        <motion.p
          className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary md:text-xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          The building design platform where daylight is measured through
          every opening, surfaces design themselves, and one change updates
          the whole project — instantly.
        </motion.p>

        <motion.div
          className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.45 }}
        >
          <Button href="/#contact" size="lg">
            Request a Demo
          </Button>
          <Button href="/signup/" variant="secondary" size="lg">
            Create free account
          </Button>
        </motion.div>
      </div>

      {/* Product showcase */}
      <motion.figure
        className="relative z-10 mx-auto mt-16 max-w-6xl"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.55 }}
      >
        <div className="absolute -inset-x-10 -inset-y-6 rounded-[32px] bg-accent/10 blur-3xl" aria-hidden />
        <div className="relative overflow-hidden rounded-[var(--radius-card)] border border-white/10 shadow-[0_30px_80px_#00000080]">
          <Image
            src={PRODUCT_SHOT.wide}
            alt={PRODUCT_SHOT.alt}
            width={1600}
            height={900}
            priority
            sizes="(min-width: 1200px) 1152px, 100vw"
            className="h-auto w-full"
          />
        </div>
        <figcaption className="mt-4 text-center text-sm text-text-muted">
          {PRODUCT_SHOT.caption}
        </figcaption>
      </motion.figure>
    </section>
  );
}
