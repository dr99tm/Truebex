"use client";

import { motion } from "motion/react";
import { Button } from "@/components/ui/Button";

export function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 pt-20">
      {/* Animated background */}
      <div className="pointer-events-none absolute inset-0">
        {/* Floating orb 1 - large, slow drift */}
        <motion.div
          className="absolute top-1/4 left-1/4 h-[600px] w-[600px]"
          style={{
            background:
              "radial-gradient(circle, rgba(0,191,255,0.08) 0%, rgba(0,191,255,0.03) 40%, transparent 70%)",
            willChange: "transform",
          }}
          animate={{
            x: [0, 80, -40, 0],
            y: [0, -60, 40, 0],
            scale: [1, 1.2, 0.9, 1],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Floating orb 2 - medium, opposite drift */}
        <motion.div
          className="absolute right-1/4 bottom-1/3 h-[500px] w-[500px]"
          style={{
            background:
              "radial-gradient(circle, rgba(0,102,255,0.08) 0%, rgba(0,102,255,0.03) 40%, transparent 70%)",
            willChange: "transform",
          }}
          animate={{
            x: [0, -70, 50, 0],
            y: [0, 50, -70, 0],
            scale: [1, 0.85, 1.15, 1],
          }}
          transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Floating orb 3 - small accent */}
        <motion.div
          className="absolute top-1/2 left-1/2 h-[350px] w-[350px] -translate-x-1/2 -translate-y-1/2"
          style={{
            background:
              "radial-gradient(circle, rgba(0,191,255,0.06) 0%, rgba(0,191,255,0.02) 45%, transparent 70%)",
            willChange: "transform",
          }}
          animate={{
            x: [0, 40, -60, 20, 0],
            y: [0, -40, 20, -30, 0],
            opacity: [0.6, 1, 0.5, 0.8, 0.6],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Subtle grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        {/* Animated particles */}
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-1 w-1 rounded-full bg-accent/40"
            style={{
              top: `${15 + i * 14}%`,
              left: `${10 + i * 15}%`,
            }}
            animate={{
              y: [0, -30, 0],
              opacity: [0, 1, 0],
            }}
            transition={{
              duration: 3 + i * 0.5,
              repeat: Infinity,
              delay: i * 0.8,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>

      <div className="relative z-10 mx-auto max-w-4xl text-center">
        {/* Logo text */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <span className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl gradient-text">
            Truebex
          </span>
        </motion.div>

        {/* Badge */}
        <motion.div
          className="mt-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <span className="inline-block rounded-full border border-accent/30 bg-accent/5 px-4 py-1.5 text-sm text-accent">
            True Building Experience
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          className="mt-8 text-3xl font-bold leading-tight tracking-tight sm:text-5xl md:text-7xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
        >
          See It Before You{" "}
          <span className="gradient-text">Build It</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary md:text-xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          One platform to design spaces, browse real materials, calculate
          construction needs, and experience it all in VR — with every change
          synced instantly.
        </motion.p>

        {/* CTAs */}
        <motion.div
          className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.45 }}
        >
          <Button href="#contact" size="lg">
            Request a Demo
          </Button>
          <Button href="#how-it-works" variant="secondary" size="lg">
            See How It Works
          </Button>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.6 }}
      >
        <div className="flex flex-col items-center gap-2">
          <span className="text-xs text-text-muted">Scroll</span>
          <div className="h-8 w-[1px] bg-gradient-to-b from-text-muted to-transparent" />
        </div>
      </motion.div>
    </section>
  );
}
