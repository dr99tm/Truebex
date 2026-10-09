import {
  Sun,
  LayoutPanelTop,
  Layers,
  Link2,
  Zap,
  Bookmark,
  FileText,
  Armchair,
  Paintbrush,
  ShoppingBag,
  Building2,
  Palette,
  HardHat,
  Wrench,
  Users,
  FileInput,
  Calculator,
  Smartphone,
  Bot,
  Wind,
  Cable,
  Languages,
} from "lucide-react";

// Content follows .claude/skills/truebex-brand-voice:
// - Truebex is its own platform. Never name or compare to other software or
//   engines.
// - Lead with what is distinctive; skip table-stakes features every design
//   tool has.
// - Claims must be true of the shipping app; planned work goes in ROADMAP.

export const SITE = {
  name: "Truebex",
  url: "https://truebex.com",
  tagline: "True Building Experience",
  title: "Truebex — See It Before You Build It",
  description:
    "Truebex is a building design platform where daylight is measured through every opening, surfaces design themselves, and one change updates the whole project — instantly.",
  email: "dr99tm@gmail.com",
} as const;

// Absolute hrefs (/#section, not #section) so the links work from any route,
// not just the homepage. From /dashboard/ a bare #features would resolve to
// /dashboard/#features (no such section); /#features navigates home first.
export const NAV_LINKS = [
  { label: "Product", href: "/#features" },
  { label: "How It Works", href: "/#how-it-works" },
  { label: "Who It's For", href: "/#who-its-for" },
  { label: "Pricing", href: "/#pricing" },
  { label: "Developers", href: "/developers/" },
  { label: "FAQ", href: "/#faq" },
  { label: "Contact", href: "/#contact" },
] as const;

export const FEATURES = [
  {
    id: "daylight",
    icon: Sun,
    title: "Daylight, measured — not painted",
    description:
      "Every window and door reads the sky and sun on its far side and lets exactly that light into the room. Open a door between a bright room and a dark one, and the light follows.",
  },
  {
    id: "fills",
    icon: LayoutPanelTop,
    title: "Surfaces that design themselves",
    description:
      "Split any wall into panels and fill them with rule-based patterns — start, end, centre, alternating. They re-flow on their own when the wall grows, shrinks or gains an opening.",
  },
  {
    id: "assets",
    icon: Layers,
    title: "Make it once, update everywhere",
    description:
      "Save a finished wall face as an asset and place it anywhere. Open the asset, change it, and every copy across the project updates in one step.",
  },
  {
    id: "intent",
    icon: Link2,
    title: "Design intent that holds",
    description:
      "Offsets, links, locked dimensions and reference planes keep shapes in relationship while the walls they belong to move and resize.",
  },
  {
    id: "instant",
    icon: Zap,
    title: "Instant at any size",
    description:
      "An edit costs only what it changes. Moving a wall in a full building takes milliseconds — 240 ms became 4.3 ms in our benchmark — so the model never lags behind your idea.",
  },
  {
    id: "memory",
    icon: Bookmark,
    title: "A project that remembers its light",
    description:
      "Lighting setups and the exact view — camera, section, storey — are saved inside the project, and every lighting change can be undone like any other edit.",
  },
  {
    id: "sheets",
    icon: FileText,
    title: "Drawings that draw themselves",
    description:
      "One command lays out plans, sections, stair sheets and schedules, with forms you fill once. Export a vector PDF with selectable text and fillable fields, or DXF.",
  },
  {
    id: "objects",
    icon: Armchair,
    title: "Doors, cabinets and stairs from numbers",
    description:
      "Describe a door, a window, a cabinet or a stair by its parameters and it builds itself, regenerates with its host, and keeps its handles and hardware in place.",
  },
  {
    id: "finishes",
    icon: Paintbrush,
    title: "Finishes on any face",
    description:
      "Paint, wallpaper and three-dimensional patterns on walls, floors, ceilings and models, driven by the same panel system — with mouldings that stop at door jambs and follow curved walls.",
  },
] as const;

// Where the platform is going. Shown as "on the roadmap", never as shipped.
export const ROADMAP = [
  {
    icon: FileInput,
    title: "Works with IFC and DWG",
    description: "Exchange models and drawings with every other tool on the project.",
  },
  {
    icon: Users,
    title: "Your team on one model",
    description: "Several people in one project, with every change in a history you can rewind.",
  },
  {
    icon: Calculator,
    title: "The model prices itself",
    description: "Real products with live prices and stock, by region, so the bill of quantities updates as you draw.",
  },
  {
    icon: Smartphone,
    title: "On your phone and in a headset",
    description: "Panoramas rendered in the cloud, refreshed the moment anything changes, and edits from wherever you are.",
  },
  {
    icon: Wind,
    title: "Daylight, energy, sound and wind reports",
    description: "Measured results from the one true model, on demand or as you work.",
  },
  {
    icon: Cable,
    title: "Building services",
    description: "Ducts, pipes and circuits that route and size themselves.",
  },
  {
    icon: Bot,
    title: "An assistant that edits the model",
    description: "Ask for a window on the north wall and it appears, with the light measured and the change undoable.",
  },
  {
    icon: Languages,
    title: "Arabic, right to left",
    description: "The whole app in Arabic, with metric and imperial units.",
  },
] as const;

// The one capture the site shows (clean frames only — no HUD or labels).
export const PRODUCT_SHOT = {
  src: "/images/product/daylight-doorway.jpg",
  wide: "/images/product/daylight-doorway-wide.jpg",
  alt: "Soft daylight falling through a doorway into a quiet white room, designed and lit in Truebex",
  caption: "Daylight measured through a doorway — captured in Truebex.",
  width: 1600,
  height: 1196,
} as const;

export const STEPS = [
  {
    number: "01",
    title: "Draw the plan",
    description:
      "Lay out walls, rooms and openings. The building forms in 3D with every line.",
  },
  {
    number: "02",
    title: "Shape the surfaces",
    description:
      "Panel the walls and set fill rules. Patterns arrange themselves and keep up with every change.",
  },
  {
    number: "03",
    title: "Let the light in",
    description:
      "Daylight is measured through every opening, room by room, as you design.",
  },
  {
    number: "04",
    title: "Make it reusable",
    description:
      "Save what works as an asset. Change it once and the whole project follows.",
  },
] as const;

export const AUDIENCES = [
  {
    icon: Building2,
    title: "Architects",
    description:
      "Judge daylight and proportion while you draw — not weeks later.",
  },
  {
    icon: Palette,
    title: "Interior Designers",
    description:
      "Panels, fills and finishes that adapt when the room changes.",
  },
  {
    icon: HardHat,
    title: "Developers & Contractors",
    description:
      "One asset, placed across every unit, updated in one step.",
  },
  {
    icon: Wrench,
    title: "Engineers",
    description:
      "References and constraints that keep relationships intact as the design evolves.",
  },
  {
    icon: Users,
    title: "Clients & Stakeholders",
    description:
      "See the real light in the real room before anything is built.",
  },
] as const;

export const PRICING_PLANS = [
  {
    id: "free",
    name: "Starter",
    price: "Free",
    period: "",
    description: "Explore Truebex and build against the developer API.",
    features: [
      "Plan and 3D design in one model",
      "Measured daylight",
      "Dynamic surface fills",
      "Developer API: 1,000 requests / month",
      "2 API keys",
    ],
    cta: "Create free account",
    href: "/signup/",
    highlighted: false,
  },
  {
    id: "pro",
    name: "Professional",
    price: "$99",
    period: "/month",
    description: "For professionals who design and present every day.",
    features: [
      "Everything in Starter",
      "Full lighting suite: ray tracing and path tracing",
      "Asset library that updates everywhere",
      "Developer API: 100,000 requests / month",
      "20 API keys",
      "Priority support",
    ],
    cta: "Upgrade to Pro",
    href: "/dashboard/billing/?plan=pro",
    highlighted: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For teams and organisations designing at scale.",
    features: [
      "Everything in Professional",
      "Team onboarding",
      "Custom asset libraries",
      "High-volume API limits",
      "Dedicated contact",
    ],
    cta: "Contact us",
    href: "/#contact",
    highlighted: false,
  },
] as const;

// The ideas Truebex is built on (shown in the "Why Truebex" section).
export const PRINCIPLES = [
  {
    title: "Truth, not decoration",
    description:
      "What you see is computed from the sun, the sky and the openings you placed — not dressed up afterwards.",
  },
  {
    title: "Intent survives change",
    description:
      "Relationships, dimensions and patterns hold while the design moves around them.",
  },
  {
    title: "Make it once",
    description:
      "Every good detail becomes an asset you can place, refine and update everywhere at once.",
  },
] as const;

export const FAQS = [
  {
    q: "What is Truebex?",
    a: "Truebex is a building design platform for Windows. You draw in plan and design in 3D at the same time, with daylight measured through every opening, surfaces that arrange themselves, and assets that update everywhere when you change them.",
  },
  {
    q: "How is the lighting in Truebex different?",
    a: "Each window and door measures the sky and sun outside it and lets that exact amount of light into the room. Move a window, widen a door or add a wall, and the light in every room responds — including rooms that only receive light through another room.",
  },
  {
    q: "What are dynamic surface fills?",
    a: "Patterns that understand the surface they sit on. You set the rules — what goes at the start, the end, the centre or in between — and Truebex lays them out, re-flowing them whenever the wall or its openings change.",
  },
  {
    q: "What happens when I edit an asset?",
    a: "Open any saved asset, change it, and save. Every copy placed across the project updates in a single step, so a detail is only ever designed once.",
  },
  {
    q: "What do I need to run Truebex?",
    a: "A Windows PC with a modern graphics card. An NVIDIA RTX card unlocks the highest lighting quality, including ray tracing and path tracing.",
  },
  {
    q: "Is there an API for developers?",
    a: "Yes. Create API keys in your dashboard and call the Truebex API with a bearer token. Every plan includes a monthly request allowance; see the developer docs.",
  },
  {
    q: "Does Truebex work with IFC and DWG files?",
    a: "Today Truebex exports vector PDF and DXF. IFC and DWG import and export are on the roadmap, together with sharing a project with your team.",
  },
  {
    q: "How can I pay?",
    a: "Professional plans are billed monthly by card. Payments are rolling out; the pricing section shows the plans.",
  },
] as const;
