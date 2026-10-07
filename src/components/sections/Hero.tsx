"use client";

import { motion } from "motion/react";
import { Button } from "@/components/ui/Button";
import { Lockup } from "@/components/brand/Logo";

export function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 pt-24 pb-16">
      {/* Drafting grid + soft brand-blue light, like the app's viewport */}
      <div className="pointer-events-none absolute inset-0">
        <div className="blueprint-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
        <motion.div
          className="absolute top-1/4 left-1/4 h-[600px] w-[600px]"
          style={{
            background:
              "radial-gradient(circle, rgba(160,206,255,0.07) 0%, rgba(160,206,255,0.02) 40%, transparent 70%)",
            willChange: "transform",
          }}
          animate={{ x: [0, 80, -40, 0], y: [0, -60, 40, 0] }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute right-1/4 bottom-1/4 h-[500px] w-[500px]"
          style={{
            background:
              "radial-gradient(circle, rgba(91,157,255,0.07) 0%, rgba(91,157,255,0.02) 40%, transparent 70%)",
            willChange: "transform",
          }}
          animate={{ x: [0, -70, 50, 0], y: [0, 50, -70, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
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
            True Building Experience · Built on Unreal Engine 5.7
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
          Real-time architectural design in 2D and 3D. Draw walls and rooms,
          light them with Lumen, watch the areas update, and walk through the
          space in first person — while you design.
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

      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.6 }}
        aria-hidden
      >
        <div className="flex flex-col items-center gap-2">
          <span className="text-xs text-text-muted">Scroll</span>
          <div className="h-8 w-[1px] bg-gradient-to-b from-text-muted to-transparent" />
        </div>
      </motion.div>
    </section>
  );
}
