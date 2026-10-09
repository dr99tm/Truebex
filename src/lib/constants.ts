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
  Building2,
  Palette,
  HardHat,
  Wrench,
  Users,
} from "lucide-react";

// Content follows .claude/skills/truebex-brand-voice:
// - Truebex is its own platform. Never name or compare to other software or
//   engines.
// - Lead with what is distinctive; skip table-stakes features every design
//   tool has.
// - Claims must be true of the shipping app; planned work goes in
//   src/content/roadmap.json (shown as "On the roadmap", never as shipped).

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
  { label: "Pricing", href: "/pricing/" },
  { label: "Developers", href: "/developers/" },
  { label: "FAQ", href: "/#faq" },
  { label: "Contact", href: "/#contact" },
] as const;

export const NAV_UI = {
  login: "Log in",
  demo: "Request Demo",
  demoHref: "/#contact",
  dashboard: "Dashboard",
  home: "Truebex home",
  toggle: "Toggle menu",
} as const;

export const FEATURES = [
  {
    id: "daylight",
    href: "/features/daylight/",
    icon: Sun,
    title: "Daylight, measured — not painted",
    description:
      "Every window and door reads the sky and sun on its far side and lets exactly that light into the room. Open a door between a bright room and a dark one, and the light follows.",
  },
  {
    id: "fills",
    href: "/features/surfaces/",
    icon: LayoutPanelTop,
    title: "Surfaces that design themselves",
    description:
      "Split any wall into panels and fill them with rule-based patterns — start, end, centre, alternating. They re-flow on their own when the wall grows, shrinks or gains an opening.",
  },
  {
    id: "assets",
    href: "/features/assets/",
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
    href: "/features/sheets/",
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
    a: "Paid plans will be billed monthly or annually by card. Payments are rolling out; the pricing page shows every plan and what it includes.",
  },
] as const;

// ---------------------------------------------------------------------------
// Pricing (/pricing/ and the home teaser). Numbers come from the plan
// catalogue (server/app/catalogue.json, read at build time by
// src/lib/catalogue.ts); this block holds only words. A tier without a price
// shows `priceAtLaunch`; the founding block stays hidden until the catalogue
// has its numbers. Tokens: {api} requests per month, {devices} computers per
// person, {n} seats, {total} founding seats, {pct} discount, {remaining}.
// ---------------------------------------------------------------------------

export type PricingHighlight = string | { text: string; roadmap: true };

export interface TierCopy {
  description: string;
  highlights: readonly PricingHighlight[];
  cta: string;
  /** Overrides the checkout link (Enterprise talks to us first). */
  href?: string;
  highlighted?: boolean;
}

export const PRICING = {
  title: "Pricing",
  description:
    "Truebex pricing: start free with the full modeller and measured daylight, then move to Pro, Studio, Team or Enterprise, billed monthly or annually.",
  eyebrow: "Pricing",
  heading: "Truebex pricing",
  intro:
    "Start free with the full modeller and measured daylight. Upgrade when Truebex becomes part of your daily work.",
  teaserTitle: "Pricing",
  teaserSubtitle:
    "Start free with the full modeller. Upgrade when Truebex becomes part of your daily work.",
  seeAll: "See all plans",
  // Tiers on the home page teaser, in order.
  teaser: ["free", "pro", "team"],
  labels: {
    interval: "Billing interval",
    month: "Monthly",
    year: "Annual",
    saveUpTo: "save up to {pct} %",
    currency: "Currency",
    perMonth: "per month",
    perMonthAnnual: "per month, billed annually",
    perYear: "{amount} a year",
    perYearMonthly: "{amount} a year, paid monthly",
    perSeat: "per seat",
    fromSeats: "from {n} seats",
    priceAtLaunch: "Price at launch",
    startFree: "Start free",
    free: "Free",
    freeNote: "no time limit",
    custom: "Custom",
    customNote: "for your organisation",
    mostPopular: "Most popular",
    onTheRoadmap: "On the roadmap",
    included: "Included",
    notIncluded: "Not included",
    unlimited: "Unlimited",
  },
  tiers: {
    free: {
      description: "The full modeller with measured daylight and every surface tool.",
      highlights: [
        "Measured daylight, ray tracing and path tracing",
        "Self-arranging surface fills and finishes",
        "One storey per project",
        "Vector PDF and DXF export, with a watermark",
        "Developer API: {api} requests / month",
        "Try Pro free for 14 days",
      ],
      cta: "Start free",
      href: "/signup/",
    },
    pro: {
      description: "For designers who draw, light and present every day.",
      highlights: [
        "Everything in Free, on every storey",
        "Exports without a watermark",
        "The asset library: change once, update everywhere",
        "Developer API: {api} requests / month",
        "Priority support",
      ],
      cta: "Choose Pro",
      highlighted: true,
    },
    studio: {
      description: "For studios that present and share their work every week.",
      highlights: [
        "Everything in Pro",
        { text: "Share links with panoramas and drawings", roadmap: true },
        { text: "Panoramas rendered in the cloud", roadmap: true },
      ],
      cta: "Choose Studio",
    },
    team: {
      description: "For practices that buy a seat for each person.",
      highlights: [
        "Everything in Studio",
        "A seat for each person, on one invoice",
        { text: "Several people in one model", roadmap: true },
      ],
      cta: "Choose Team",
    },
    enterprise: {
      description: "For organisations designing at scale.",
      highlights: [
        "Everything in Team",
        "Team onboarding",
        "Custom asset libraries",
        "Developer API: {api} requests / month",
        "A dedicated contact",
      ],
      cta: "Talk to us",
      href: "/#contact",
    },
  } satisfies Record<string, TierCopy>,
  founding: {
    title: "Founding seats",
    body: "The first {total} paid seats keep {pct} % off for as long as they stay subscribed.",
    left: "{remaining} of {total} founding seats left",
    ends: "Offer ends {date}.",
  },
  comparisonTitle: "Compare plans",
  comparisonSubtitle:
    "Everything each plan includes. Rows marked “On the roadmap” describe work that has not shipped yet.",
  // One row per key of the entitlement matrix (catalogue features and
  // limits), plus the developer API. `roadmap: true` = not shipped yet.
  comparison: [
    {
      title: "Design and light",
      rows: [
        { key: "lighting.full", kind: "feature", label: "Measured daylight, ray tracing and path tracing" },
        { key: "storeys", kind: "limit", label: "Storeys per project" },
        { key: "assets.library", kind: "feature", label: "Asset library: change once, update everywhere" },
        { key: "render.panorama", kind: "feature", label: "Panorama renders", roadmap: true },
        { key: "vr.pc", kind: "feature", label: "Walk the model in a PC headset", roadmap: true },
        { key: "mep", kind: "feature", label: "Building services: ducts, pipes and circuits", roadmap: true },
        { key: "analysis.reports", kind: "feature", label: "Daylight, energy, sound and wind reports", roadmap: true },
      ],
    },
    {
      title: "Drawings and exchange",
      rows: [
        { key: "export.pdf", kind: "feature", label: "Vector PDF sheets with selectable text" },
        { key: "export.dxf", kind: "feature", label: "DXF export" },
        { key: "export.clean", kind: "feature", label: "Exports without a watermark" },
        { key: "export.dwg", kind: "feature", label: "DWG export", roadmap: true },
        { key: "export.ifc", kind: "feature", label: "IFC export", roadmap: true },
      ],
    },
    {
      title: "Cloud and sharing",
      rows: [
        { key: "cloud.sync", kind: "feature", label: "Cloud save and versions", roadmap: true },
        { key: "collab.live", kind: "feature", label: "Several people in one model", roadmap: true },
        { key: "share.links", kind: "feature", label: "Share links with panoramas and drawings", roadmap: true },
        { key: "share_links", kind: "limit", label: "Share links open at once", roadmap: true },
        { key: "cloud.panoramas", kind: "feature", label: "Panoramas on phones and headsets", roadmap: true },
        { key: "cloud_cu_month", kind: "limit", label: "Cloud render units per month", roadmap: true },
      ],
    },
    {
      title: "Prices and the assistant",
      rows: [
        { key: "market.cost", kind: "feature", label: "The model prices itself", roadmap: true },
        { key: "ai.byok", kind: "feature", label: "Assistant with your own AI key", roadmap: true },
        { key: "ai.metered", kind: "feature", label: "Truebex AI credits", roadmap: true },
        { key: "ai_credits_month", kind: "limit", label: "AI credits per month", roadmap: true },
      ],
    },
    {
      title: "Account",
      rows: [
        { key: "devices", kind: "limit", label: "Computers per person" },
        { key: "api.monthly_requests", kind: "api", label: "Developer API requests per month" },
      ],
    },
  ],
  faqTitle: "Pricing questions",
  faqSubtitle: "Plans, trials, billing and seats.",
  // `when`: shown only when the catalogue says so ("unpriced" = no paid
  // price yet; "founding" = the founding offer has its numbers).
  faq: [
    {
      q: "Is Truebex free to use?",
      a: "Yes. Free is the full modeller with measured daylight, surface fills and the asset library, with no time limit. Projects have one storey, and PDF and DXF exports carry a watermark.",
    },
    {
      q: "How does the Pro trial work?",
      a: "Every account can try Pro free for 14 days, once. When the trial ends, your projects stay yours and keep opening on Free.",
    },
    {
      q: "What is the difference between monthly and annual billing?",
      a: "It is the same plan, paid every month or once a year. Annual billing costs less per month.",
    },
    {
      q: "Which currencies can I pay in?",
      a: "Prices are shown in pounds sterling, US dollars and euros. Choose yours above the plans.",
    },
    {
      q: "What does per seat mean?",
      a: "Team is priced per person. Each seat runs Truebex on up to {devices} computers.",
    },
    {
      q: "What are founding seats?",
      a: "The first {total} paid seats keep a {pct} % discount for as long as their subscription stays active.",
      when: "founding",
    },
    {
      q: "When can I buy a paid plan?",
      a: "Payments are rolling out. Create a free account today; paid plans open from your dashboard when prices are published here.",
      when: "unpriced",
    },
    {
      q: "Can I cancel at any time?",
      a: "Yes. A paid plan runs to the end of the period you paid for, and your projects stay yours on Free.",
    },
  ],
} as const;

// ---------------------------------------------------------------------------
// Feature pages (/features/<slug>/), one per search cluster (truebex-seo
// keyword map). `h1` carries the cluster's phrase. The marketplace page is
// roadmap: future tense only. A page shows its own capture once
// scripts/make_web_assets.py has written public/images/features/<slug>.jpg
// from a clean frame; until then it shows the shared capture (PRODUCT_SHOT).
// ---------------------------------------------------------------------------

export interface FeaturePageCopy {
  slug: string;
  nav: string;
  title: string;
  description: string;
  eyebrow: string;
  h1: string;
  intro: string;
  roadmap?: boolean;
  stepsTitle: string;
  steps: readonly { title: string; description: string }[];
  sections: readonly { title: string; body: string }[];
  capture?: { alt: string; caption: string };
  faq: readonly { q: string; a: string }[];
  supplierCta?: { label: string; href: string };
}

export const FEATURE_PAGES: readonly FeaturePageCopy[] = [
  {
    slug: "daylight",
    nav: "Daylight",
    title: "Daylight design software",
    description:
      "Daylight design software that measures the light through every window and door as you draw, so you see how bright each room is before you build it.",
    eyebrow: "Measured daylight",
    h1: "Daylight design, measured through every opening",
    intro:
      "Every window and door in Truebex reads the sky and the sun on its far side and lets exactly that light into the room. Move an opening, widen a door or add a wall, and the light in every room follows while you draw.",
    stepsTitle: "How it works",
    steps: [
      { title: "Place the openings", description: "Draw walls and drop in windows and doors. Each opening knows the sky and the sun outside it." },
      { title: "Light is measured, not painted", description: "Each opening measures what it sees and passes exactly that light into the room behind it." },
      { title: "Light travels room to room", description: "Open an interior door and a dark room borrows light from a bright one, as it would on site." },
      { title: "Judge it at full quality", description: "Switch on ray tracing or path tracing for the final look on a modern graphics card." },
    ],
    sections: [
      {
        title: "Rooms lit through other rooms",
        body: "A hallway with no window of its own still gets the light that reaches it through doors. Truebex passes the measured light on from opening to opening, so inner rooms look as bright, or as dim, as they will be.",
      },
      {
        title: "A project that remembers its light",
        body: "Lighting setups and the exact view (camera, section and storey) are saved inside the project, and every lighting change can be undone like any other edit.",
      },
      {
        title: "Fast enough to design with",
        body: "An edit costs only what it changes. Moving a wall in a full building takes milliseconds (240 ms became 4.3 ms in our benchmark), so the light keeps up with the idea.",
      },
    ],
    capture: {
      alt: "Daylight measured through a doorway: soft light falling into a quiet white room, designed and lit in Truebex",
      caption: "Daylight measured through a doorway, captured in Truebex.",
    },
    faq: [
      {
        q: "How does Truebex measure daylight?",
        a: "Each window and door samples the sky and the sun on its outside face and lets that measured amount of light into the room. The result changes as soon as an opening, a wall or the sun position changes.",
      },
      {
        q: "Do rooms without windows get light?",
        a: "Yes, when they connect to a lit room. Open an interior door and the light measured at that doorway passes on into the next room.",
      },
      {
        q: "What hardware do I need for the best lighting?",
        a: "A Windows PC with a modern graphics card. An NVIDIA RTX card unlocks the highest lighting quality, including ray tracing and path tracing.",
      },
      {
        q: "Can Truebex produce a daylight report?",
        a: "Not yet. Daylight reports with lux, daylight factor and sun hours are on the roadmap.",
      },
    ],
  },
  {
    slug: "surfaces",
    nav: "Surfaces",
    title: "Parametric wall panel design",
    description:
      "Parametric wall panel design in Truebex: split any wall, floor or ceiling into panels, set fill rules, and watch the pattern re-flow when the wall changes.",
    eyebrow: "Surfaces that design themselves",
    h1: "Parametric wall panels that design themselves",
    intro:
      "Split any wall, floor or ceiling into panels and fill them with rule-based patterns. Set what goes at the start, the end, the centre or in between, and Truebex lays it out, then re-flows it when the wall grows, shrinks or gains an opening.",
    stepsTitle: "How it works",
    steps: [
      { title: "Split the face", description: "Divide a wall face into panels and nested regions. Floors, ceilings, slabs and the faces of models work the same way." },
      { title: "Set the fill rules", description: "Say what goes at the start, the end and the centre, what alternates, and how the rest repeats." },
      { title: "Change the wall", description: "Lengthen the wall or add a door and the pattern re-flows by itself, with every panel still in step." },
      { title: "Finish it", description: "Paint, wallpaper and three-dimensional patterns go on any face, driven by the same panels." },
    ],
    sections: [
      {
        title: "Rules, not drawings",
        body: "A fill is a set of rules about the surface it sits on, not a picture of a pattern. That is why it keeps its intent when the room changes: the rules run again and the layout follows.",
      },
      {
        title: "Mouldings that know the room",
        body: "Skirtings and mouldings stop flush at door jambs and follow curved walls, so a finished room stays finished after you move a door.",
      },
      {
        title: "Make it once",
        body: "Save a finished wall face as an asset, place it anywhere, and change every copy in one step.",
      },
    ],
    capture: {
      alt: "A room designed in Truebex, with daylight falling through a doorway onto clean wall surfaces",
      caption: "A room designed and lit in Truebex.",
    },
    faq: [
      {
        q: "What are dynamic surface fills?",
        a: "Patterns that understand the surface they sit on. You set the rules (what goes at the start, the end, the centre or in between) and Truebex lays them out, re-flowing them whenever the wall or its openings change.",
      },
      {
        q: "Which surfaces can be panelled?",
        a: "Walls, floors, ceilings, slabs and the faces of models.",
      },
      {
        q: "What happens when I add a door to a panelled wall?",
        a: "The panels and fills re-flow around the new opening, and mouldings stop at the door jambs.",
      },
      {
        q: "Can I reuse a finished wall?",
        a: "Yes. Save the wall face as an asset and place it anywhere; edit it once and every copy updates.",
      },
    ],
  },
  {
    slug: "assets",
    nav: "Assets",
    title: "Reusable design assets",
    description:
      "Reusable design assets in Truebex: save a wall face, an object or a detail once, place it across the project, and update every copy in one step when it changes.",
    eyebrow: "Make it once, update everywhere",
    h1: "Reusable design assets that update everywhere",
    intro:
      "Save a finished wall face, an object or a detail as an asset and place it across the project. Open the asset, change it, and every copy updates in one step.",
    stepsTitle: "How it works",
    steps: [
      { title: "Design it once", description: "Finish a wall face, an object or a section the way you want it." },
      { title: "Save it as an asset", description: "Keep it inside the project or link it from a shared file." },
      { title: "Place it everywhere", description: "Drop it into every unit, room or storey that needs it." },
      { title: "Change it once", description: "Open the asset, edit it, save, and every copy follows." },
    ],
    sections: [
      {
        title: "One library for everything",
        body: "Textures, meshes, objects, sections, faces and sheet templates live in one library, with categories, tags, search and favourites.",
      },
      {
        title: "Embedded or linked",
        body: "Keep assets inside the project, link them from a shared file, or mix both. A missing link shows a stand-in that heals as soon as the file returns.",
      },
      {
        title: "Bring your own",
        body: "Import textures, and meshes in glTF, GLB, OBJ and FBX, then compose your own objects from them.",
      },
    ],
    capture: {
      alt: "A daylit room designed in Truebex, where walls and details are reusable assets",
      caption: "A room designed and lit in Truebex.",
    },
    faq: [
      {
        q: "What happens when I edit an asset?",
        a: "Open any saved asset, change it, and save. Every copy placed across the project updates in a single step, so a detail is only ever designed once.",
      },
      {
        q: "Can assets live outside the project?",
        a: "Yes. Save them embedded in the project, linked from a shared file, or a mix of both.",
      },
      {
        q: "Which files can I import?",
        a: "Textures, and meshes in glTF, GLB, OBJ and FBX.",
      },
      {
        q: "Is there a marketplace for assets?",
        a: "Not yet. A marketplace of real products with regional prices is on the roadmap.",
      },
    ],
  },
  {
    slug: "sheets",
    nav: "Drawing sheets",
    title: "Automatic drawing sheets",
    description:
      "Automatic drawing sheets: one command lays out plans, sections, stair sheets and schedules, with dimensions that keep up. Export vector PDF or DXF from Truebex.",
    eyebrow: "Drawings that draw themselves",
    h1: "Drawing sheets that lay themselves out",
    intro:
      "One command lays out the sheet set (cover, plans, sections, stair sheets, schedules and renders) with forms you fill once. Export a vector PDF with selectable text and fillable fields, or DXF.",
    stepsTitle: "How it works",
    steps: [
      { title: "Run one command", description: "Truebex creates the sheet set from the model: cover, plans, sections, stairs, schedules and renders." },
      { title: "Fill the forms once", description: "Project details go into forms once and appear on every sheet." },
      { title: "Dimensions keep up", description: "Auto dimensions stay current as walls and openings move." },
      { title: "Export", description: "Vector PDF with selectable text and fillable fields, or DXF." },
    ],
    sections: [
      {
        title: "Dimensions that stay current",
        body: "Dimension styles for plan, 3D and sheets, auto dimensions that follow the model, relevance per view, and pins that keep the dimensions you choose always visible.",
      },
      {
        title: "Our own PDF and DXF writers",
        body: "Truebex writes its own vector PDF: crisp at any zoom, with text you can select and form fields you can fill.",
      },
    ],
    capture: {
      alt: "A daylit room designed in Truebex, the model its drawing sheets are made from",
      caption: "The model behind the sheets, designed and lit in Truebex.",
    },
    faq: [
      {
        q: "Which sheets does Truebex create?",
        a: "A cover, plans, sections, the stair sheets, face sketches, renders and schedules, laid out by one command.",
      },
      {
        q: "Can I export to PDF and DXF?",
        a: "Yes: vector PDF with selectable text and fillable form fields, and DXF.",
      },
      {
        q: "Do dimensions update when the design changes?",
        a: "Yes. Auto dimensions stay up to date as walls and openings move, and pins keep chosen dimensions visible.",
      },
      {
        q: "Can I export DWG or IFC?",
        a: "Not yet. DWG and IFC exchange are on the roadmap.",
      },
    ],
  },
  {
    slug: "marketplace",
    nav: "Marketplace",
    title: "Building products marketplace",
    description:
      "On the Truebex roadmap: a building products marketplace inside your model, with real products, regional prices and stock, and a cost that updates as you draw.",
    eyebrow: "On the roadmap",
    h1: "A building products marketplace inside your model",
    intro:
      "On the roadmap: real products from real suppliers, placed straight into your design, with prices and stock for your region. The model will price itself as you draw, and orders and quotes will go through the platform.",
    roadmap: true,
    stepsTitle: "How it will work",
    steps: [
      { title: "Suppliers will list real products", description: "Products will arrive with their variants, geometry, prices, tax, delivery and stock." },
      { title: "You will place them in the model", description: "The catalogue will sit in the asset browser, next to your own assets." },
      { title: "Prices will follow your region", description: "Switch the project to another region and every product will re-price." },
      { title: "Orders and quotes will go through Truebex", description: "Checkout will happen on the platform, never inside the app." },
    ],
    sections: [
      {
        title: "A cost that will update as you draw",
        body: "Quantities from the model will meet live regional prices, so the bill of quantities will move with every wall, floor and finish you change.",
      },
      {
        title: "For suppliers",
        body: "Suppliers will manage their catalogue, stock, regional prices, leads and orders in a web app, with spreadsheet and feed import. The first suppliers will be onboarded by hand.",
      },
    ],
    faq: [
      {
        q: "When will the marketplace open?",
        a: "It is on the roadmap. The roadmap page shows its status as it moves from planned to in progress.",
      },
      {
        q: "How will prices work?",
        a: "Each product will carry prices, tax, delivery and availability per region, and the project's cost will update as you place and change products.",
      },
      {
        q: "Can my company list products?",
        a: "Yes, once it opens. Suppliers can register their interest today, and the first suppliers will be onboarded by hand.",
      },
    ],
    supplierCta: {
      label: "Register supplier interest",
      href: `mailto:${SITE.email}?subject=Supplier%20interest`,
    },
  },
] as const;

export const FEATURE_PAGE_UI = {
  home: "Home",
  learnMore: "How it works",
  faqTitle: "Questions",
  related: "More from Truebex",
  download: "Download for Windows",
  // Until the download page exists, the download button asks for a demo.
  downloadFallback: "Request a demo",
  signup: "Create free account",
  ctaTitle: "See it in your own project",
  ctaBody: "Create a free account and design with measured daylight today.",
  roadmapCtaTitle: "Follow it as it is built",
  roadmapCtaBody: "Create a free account to design with Truebex today, and watch the roadmap for this work.",
  roadmapLink: "See the roadmap",
} as const;

// ---------------------------------------------------------------------------
// Roadmap page and the home roadmap block. Items and statuses live in
// src/content/roadmap.json (statuses written by scripts/sync-roadmap.mjs).
// ---------------------------------------------------------------------------

export const ROADMAP_PAGE = {
  title: "Roadmap",
  description:
    "The Truebex roadmap in plain words: what is planned, in progress and shipped, from IFC and DWG exchange to cloud panoramas, a products marketplace and more.",
  eyebrow: "Roadmap",
  heading: "The Truebex roadmap",
  intro:
    "What we are building next, in our own words. An item joins the feature list only when it ships.",
  status: { planned: "Planned", in_progress: "In progress", shipped: "Shipped" },
  homeTitle: "On the roadmap",
  homeLink: "See the full roadmap",
} as const;

// ---------------------------------------------------------------------------
// Changelog (/changelog/ and /changelog/feed.xml): release entries from
// src/content/releases.json (the release feed) and the product's history
// from src/content/history.json.
// ---------------------------------------------------------------------------

export const CHANGELOG = {
  title: "Changelog",
  description:
    "The Truebex changelog: every release and milestone, from measured daylight and self-arranging surfaces to drawing sheets, finishes and the asset library.",
  eyebrow: "Changelog",
  heading: "Truebex changelog",
  intro:
    "Every release and milestone, newest first. Follow along with the feed in any feed reader.",
  feedTitle: "Truebex changelog",
  feedSubtitle: "Releases and milestones of the Truebex building design platform.",
  feedLink: "Subscribe to the feed",
  releasesTitle: "Releases",
  historyTitle: "Milestones",
  version: "Version",
} as const;

// ---------------------------------------------------------------------------
// Footer, language switch, social accounts.
// ---------------------------------------------------------------------------

export const LANGUAGE_SWITCH = {
  en: { label: "English", href: "/", lang: "en" },
  ar: { label: "العربية", href: "/ar/", lang: "ar" },
} as const;

export const FOOTER = {
  blurb:
    "The building design platform where daylight is measured, surfaces design themselves and every change is instant.",
  product: "Product",
  features: "Features",
  resources: "Resources",
  contact: "Get in touch",
  follow: "Follow",
  demo: "Request a demo",
  rights: "All rights reserved.",
  links: [
    { label: "Developer docs", href: "/developers/" },
    { label: "Changelog", href: "/changelog/" },
    { label: "Roadmap", href: "/roadmap/" },
    { label: "Dashboard", href: "/dashboard/" },
    { label: "Create account", href: "/signup/" },
    { label: "Brand assets", href: "/brand/truebex-mark-grey.svg" },
    { label: "Privacy", href: "/privacy/" },
    { label: "Terms", href: "/terms/" },
  ],
} as const;

// Social accounts: the footer's Follow column and the Organization `sameAs`
// show only the ones with a URL. The owner sets them from the launch plan.
export const SOCIAL: readonly { id: string; label: string; url: string }[] = [
  { id: "linkedin", label: "LinkedIn", url: "" },
  { id: "instagram", label: "Instagram", url: "" },
  { id: "youtube", label: "YouTube", url: "" },
  { id: "tiktok", label: "TikTok", url: "" },
  { id: "x", label: "X", url: "" },
];

// ---------------------------------------------------------------------------
// Analytics and search engines. All values are public by design (they are
// served in every page); none is a secret. Empty = off.
// ---------------------------------------------------------------------------

// Cloudflare Web Analytics: cookieless page views on public pages only. The
// token is the site's beacon token from the Cloudflare dashboard.
export const ANALYTICS = {
  cloudflareToken: "",
};

// Search Console (Google) and Bing Webmaster Tools HTML-tag verification.
export const VERIFICATION = {
  google: "",
  bing: "",
};

// The privacy policy's section on website analytics.
export const WEBSITE_ANALYTICS_NOTICE = {
  title: "Website analytics",
  paragraphs: [
    "On the public pages of truebex.com (not in your dashboard or account pages) we count page views with Cloudflare Web Analytics. It uses no cookies and no local storage, does not fingerprint your device, and does not follow you across other websites.",
    "It records the page, the referring site, the browser, the device type and the country, aggregated by Cloudflare. We use it only to see which pages are read.",
    "Sign-ups, downloads, trials and purchases are counted from our own account and billing records, as daily totals with no personal details.",
  ],
} as const;

// ---------------------------------------------------------------------------
// The Arabic landing page (/ar/): the home page in Arabic, right to left.
// The native-speaker review is the owner's (launch plan).
// ---------------------------------------------------------------------------

export const AR_HOME = {
  meta: {
    title: "Truebex — شاهده قبل أن تبنيه",
    description:
      "Truebex منصة لتصميم المباني: يُقاس فيها ضوء النهار عبر كل نافذة وباب، وتُرتّب الأسطح نفسها بنفسها، ويحدّث تعديل واحد المشروع كله فورًا.",
    ogLocale: "ar_AR",
  },
  nav: [
    { label: "المنتج", href: "/ar/#features" },
    { label: "كيف يعمل", href: "/ar/#how-it-works" },
    { label: "لمن صُمّم", href: "/ar/#who-its-for" },
    { label: "الأسعار", href: "/ar/#pricing" },
    { label: "الأسئلة الشائعة", href: "/ar/#faq" },
    { label: "تواصل معنا", href: "/ar/#contact" },
  ],
  login: "تسجيل الدخول",
  dashboard: "لوحة التحكم",
  demo: "اطلب عرضًا توضيحيًا",
  home: "الصفحة الرئيسية لـ Truebex",
  toggleMenu: "فتح القائمة وإغلاقها",
  hero: {
    badge: "تجربة بناء حقيقية",
    titleStart: "شاهده قبل أن",
    titleAccent: "تبنيه.",
    subtitle:
      "منصة لتصميم المباني يُقاس فيها ضوء النهار عبر كل فتحة، وتصمّم الأسطح نفسها بنفسها، ويحدّث تعديل واحد المشروع كله — فورًا.",
    primary: { label: "اطلب عرضًا توضيحيًا", href: "/ar/#contact" },
    secondary: { label: "أنشئ حسابًا مجانيًا", href: "/signup/" },
    alt: "ضوء نهار ناعم يدخل عبر مدخل باب إلى غرفة بيضاء هادئة، صُمّمت وأُضيئت في Truebex",
    caption: "ضوء النهار مقيسًا عبر مدخل باب — لقطة من Truebex.",
  },
  about: {
    title: "ما هو Truebex؟",
    subtitle: "منصة لتصميم المباني، ما ترسمه فيها هو ما تراه — في ضوء حقيقي وبمقياس حقيقي.",
    paragraphs: [
      "يتعامل Truebex مع المبنى كنموذج واحد حيّ. المسقط الذي ترسمه، والأسطح التي تشكّلها، والضوء الذي يملأ كل غرفة، كلها شيء واحد — فلا شيء يُصدَّر، ولا شيء يُعاد إخراجه، ولا شيء يخرج عن التزامن.",
      "يُقاس الضوء من الشمس والسماء والفتحات التي وضعتها. تعرف الأنماط الجدران التي تقع عليها. والتفاصيل التي تصمّمها مرة واحدة تتحدّث في كل مكان تُستخدم فيه.",
    ],
  },
  features: {
    title: "ما يقدّمه Truebex وحده",
    subtitle: "تسع قدرات في صميم المنصة، كلها متاحة في التطبيق اليوم.",
    items: {
      daylight: {
        title: "ضوء النهار مقيس — لا مرسوم",
        description:
          "تقرأ كل نافذة وكل باب السماء والشمس على جانبها الآخر، وتُدخل إلى الغرفة ذلك الضوء بالضبط. افتح بابًا بين غرفة مضيئة وأخرى مظلمة، فيتبعه الضوء.",
      },
      fills: {
        title: "أسطح تصمّم نفسها",
        description:
          "قسّم أي جدار إلى ألواح واملأها بأنماط تحكمها قواعد: البداية والنهاية والوسط والتناوب. تعيد ترتيب نفسها حين يطول الجدار أو يقصر أو تُضاف إليه فتحة.",
      },
      assets: {
        title: "اصنعه مرة، وحدّثه في كل مكان",
        description:
          "احفظ واجهة جدار مكتملة كأصل وضعها أينما شئت. افتح الأصل وعدّله، فتتحدّث كل نسخة منه في المشروع بخطوة واحدة.",
      },
      intent: {
        title: "نيّة التصميم ثابتة",
        description:
          "الإزاحات والروابط والأبعاد المقفلة والمستويات المرجعية تحفظ العلاقات بين الأشكال بينما تتحرك الجدران التي تنتمي إليها ويتغيّر حجمها.",
      },
      instant: {
        title: "فوري مهما كبر المشروع",
        description:
          "لا يكلّف التعديل إلا ما يغيّره. تحريك جدار في مبنى كامل يستغرق أجزاءً من الألف من الثانية — من 240 ملّي ثانية إلى 4.3 ملّي ثانية في اختبارنا — فلا يتأخر النموذج عن فكرتك.",
      },
      memory: {
        title: "مشروع يتذكّر ضوءه",
        description:
          "تُحفظ إعدادات الإضاءة والمشهد بدقة — الكاميرا والمقطع والطابق — داخل المشروع، ويمكن التراجع عن أي تغيير في الإضاءة كأي تعديل آخر.",
      },
      sheets: {
        title: "لوحات ترسم نفسها",
        description:
          "أمر واحد يرتّب المساقط والمقاطع ولوحات السلالم والجداول، مع نماذج تملؤها مرة واحدة. صدّر ملف PDF متجهيًا بنص قابل للتحديد وحقول قابلة للتعبئة، أو ملف DXF.",
      },
      objects: {
        title: "أبواب وخزائن وسلالم من الأرقام",
        description:
          "صِف بابًا أو نافذة أو خزانة أو سلّمًا بمعاملاته فيُبنى من تلقاء نفسه، ويُعاد توليده مع الجدار الحامل له، ويحافظ على مقابضه وتجهيزاته في مكانها.",
      },
      finishes: {
        title: "تشطيبات على أي سطح",
        description:
          "طلاء وورق جدران وأنماط ثلاثية الأبعاد على الجدران والأرضيات والأسقف والنماذج، يقودها نظام الألواح نفسه — مع كرانيش تتوقف عند حلوق الأبواب وتتبع الجدران المنحنية.",
      },
    },
  },
  steps: {
    title: "كيف يعمل",
    subtitle: "من المسقط إلى الضوء في أربع خطوات.",
    items: [
      { number: "01", title: "ارسم المسقط", description: "ضع الجدران والغرف والفتحات. يتشكّل المبنى بالأبعاد الثلاثية مع كل خط." },
      { number: "02", title: "شكّل الأسطح", description: "قسّم الجدران إلى ألواح وحدّد قواعد التعبئة. تترتب الأنماط من تلقاء نفسها وتواكب كل تغيير." },
      { number: "03", title: "أدخل الضوء", description: "يُقاس ضوء النهار عبر كل فتحة، غرفةً غرفة، أثناء التصميم." },
      { number: "04", title: "اجعله قابلًا لإعادة الاستخدام", description: "احفظ ما ينجح كأصل. غيّره مرة واحدة فيتبعه المشروع كله." },
    ],
  },
  audiences: {
    title: "لمن صُمّم Truebex",
    subtitle: "لكل من يحتاج أن يرى المبنى قبل أن يُبنى.",
    items: [
      { title: "المعماريون", description: "احكم على ضوء النهار والتناسب أثناء الرسم — لا بعد أسابيع." },
      { title: "مصممو الديكور الداخلي", description: "ألواح وتعبئات وتشطيبات تتكيّف حين تتغيّر الغرفة." },
      { title: "المطوّرون والمقاولون", description: "أصل واحد يوضع في كل وحدة ويُحدَّث بخطوة واحدة." },
      { title: "المهندسون", description: "مراجع وقيود تحفظ العلاقات بينما يتطوّر التصميم." },
      { title: "العملاء وأصحاب القرار", description: "شاهد الضوء الحقيقي في الغرفة الحقيقية قبل أن يُبنى أي شيء." },
    ],
  },
  pricing: {
    title: "الأسعار",
    subtitle: "ابدأ مجانًا بالمصمّم الكامل، ورقِّ اشتراكك حين يصبح Truebex جزءًا من عملك اليومي.",
    seeAll: "جميع الخطط والمقارنة الكاملة (بالإنجليزية)",
    labels: {
      interval: "دورة الفوترة",
      month: "شهري",
      year: "سنوي",
      saveUpTo: "وفّر حتى {pct}٪",
      currency: "العملة",
      perMonth: "شهريًا",
      perMonthAnnual: "شهريًا، يُدفع سنويًا",
      perYear: "{amount} في السنة",
      perYearMonthly: "{amount} في السنة عند الدفع الشهري",
      perSeat: "لكل مقعد",
      fromSeats: "من {n} مقاعد",
      priceAtLaunch: "السعر عند الإطلاق",
      startFree: "ابدأ مجانًا",
      free: "مجانًا",
      freeNote: "بلا حدّ زمني",
      custom: "حسب الطلب",
      customNote: "لمؤسستك",
      mostPopular: "الأكثر اختيارًا",
      onTheRoadmap: "على خارطة الطريق",
      included: "مشمول",
      notIncluded: "غير مشمول",
      unlimited: "بلا حدود",
    },
    tiers: {
      free: {
        name: "المجانية",
        description: "المصمّم الكامل مع ضوء نهار مقيس، مجانًا وبلا حدّ زمني.",
        highlights: [
          "ضوء نهار مقيس، وتتبّع الأشعة وتتبّع المسارات",
          "طابق واحد لكل مشروع",
          "تصدير PDF وDXF بعلامة مائية",
          "جرّب الخطة الاحترافية مجانًا 14 يومًا",
        ],
        cta: "ابدأ مجانًا",
        href: "/signup/",
      },
      pro: {
        name: "الاحترافية",
        description: "لمن يرسم ويُضيء ويعرض تصاميمه كل يوم.",
        highlights: [
          "كل ما في المجانية، على كل الطوابق",
          "تصدير بلا علامة مائية",
          "مكتبة الأصول: غيّر مرة واحدة فيتحدّث كل شيء",
          "دعم بأولوية",
        ],
        cta: "اختر الاحترافية",
        highlighted: true,
      },
      team: {
        name: "الفريق",
        description: "للمكاتب التي تشتري مقعدًا لكل شخص.",
        highlights: [
          "كل ما في خطة الاستوديو",
          "مقعد لكل شخص، بفاتورة واحدة",
          { text: "عدة أشخاص في نموذج واحد", roadmap: true },
        ],
        cta: "اختر الفريق",
      },
    } satisfies Record<string, TierCopy & { name: string }>,
  },
  roadmap: {
    title: "على خارطة الطريق",
    subtitle: "ما نبنيه بعد ذلك، وحالة كل عنصر.",
    status: { planned: "مخطط له", in_progress: "قيد التنفيذ", shipped: "متاح" },
    link: "خارطة الطريق كاملة (بالإنجليزية)",
    // Arabic words for roadmap items, keyed by the ids in roadmap.json.
    items: {
      exchange: { title: "التبادل مع IFC وDWG", description: "تبادل النماذج والرسومات مع كل أدوات المشروع الأخرى." },
      together: { title: "فريقك في نموذج واحد", description: "عدة أشخاص في مشروع واحد، مع سجل لكل تغيير يمكنك الرجوع إليه." },
      "prices-itself": { title: "نموذج يسعّر نفسه", description: "منتجات حقيقية بأسعار ومخزون حيّ لكل منطقة، فيتحدّث جدول الكميات أثناء الرسم." },
      everywhere: { title: "على هاتفك وفي نظارة العرض", description: "صور بانورامية تُعرض في السحابة وتتحدّث لحظة أي تغيير." },
      reports: { title: "تقارير ضوء النهار والطاقة والصوت والرياح", description: "نتائج مقيسة من النموذج الحقيقي الواحد." },
      arabic: { title: "العربية، من اليمين إلى اليسار", description: "التطبيق كله بالعربية، مع الوحدات المترية والإمبراطورية." },
    },
  },
  faq: {
    title: "أسئلة شائعة",
    subtitle: "إجابات قصيرة عن Truebex والأجهزة والأسعار.",
    items: [
      {
        q: "ما هو Truebex؟",
        a: "Truebex منصة لتصميم المباني تعمل على Windows. ترسم المسقط وتصمّم بالأبعاد الثلاثية في الوقت نفسه، مع ضوء نهار يُقاس عبر كل فتحة، وأسطح ترتّب نفسها، وأصول تتحدّث في كل مكان حين تغيّرها.",
      },
      {
        q: "كيف تختلف الإضاءة في Truebex؟",
        a: "تقيس كل نافذة وكل باب السماء والشمس خارجها وتُدخل ذلك القدر من الضوء بالضبط إلى الغرفة. حرّك نافذة أو وسّع بابًا أو أضف جدارًا، فيستجيب الضوء في كل غرفة — حتى الغرف التي لا يصلها الضوء إلا عبر غرفة أخرى.",
      },
      {
        q: "ماذا أحتاج لتشغيل Truebex؟",
        a: "حاسوب يعمل بنظام Windows مع بطاقة رسوميات حديثة. بطاقة NVIDIA RTX تتيح أعلى جودة للإضاءة، بما فيها تتبّع الأشعة وتتبّع المسارات.",
      },
      {
        q: "هل التطبيق متاح بالعربية؟",
        a: "هذه الصفحة بالعربية اليوم. أما واجهة التطبيق بالعربية من اليمين إلى اليسار، مع الوحدات المترية والإمبراطورية، فهي على خارطة الطريق.",
      },
      {
        q: "هل يعمل Truebex مع ملفات IFC وDWG؟",
        a: "يصدّر Truebex اليوم ملفات PDF متجهية وDXF. أما استيراد IFC وDWG وتصديرهما فعلى خارطة الطريق.",
      },
      {
        q: "كيف أدفع؟",
        a: "المدفوعات قيد الإطلاق، وصفحة الأسعار تعرض الخطط وما تشمله كل خطة.",
      },
    ],
  },
  contact: {
    titleStart: "هل أنت مستعد لتصميم",
    titleAccent: "ما سيُبنى فعلًا؟",
    body: "شاهد مبنى يُصمَّم ويُضاء ويُحسَّن في جلسة حيّة واحدة. اطلب عرضًا توضيحيًا وسنريك Truebex على مشروع يشبه مشروعك.",
    email: "راسلنا بالبريد الإلكتروني",
    form: "نموذج طلب العرض (بالإنجليزية)",
  },
  footer: {
    tagline: "تجربة بناء حقيقية",
    blurb: "منصة تصميم المباني حيث يُقاس ضوء النهار، وتصمّم الأسطح نفسها، وكل تعديل فوري.",
    product: "المنتج",
    features: "الميزات",
    resources: "مصادر",
    contact: "تواصل",
    follow: "تابعنا",
    demo: "اطلب عرضًا توضيحيًا",
    rights: "جميع الحقوق محفوظة.",
    featureNames: {
      daylight: "ضوء النهار",
      surfaces: "الأسطح",
      assets: "الأصول",
      sheets: "لوحات الرسم",
      marketplace: "سوق المنتجات",
    },
    links: [
      { label: "توثيق المطوّرين", href: "/developers/" },
      { label: "سجل التغييرات", href: "/changelog/" },
      { label: "خارطة الطريق", href: "/roadmap/" },
      { label: "لوحة التحكم", href: "/dashboard/" },
      { label: "إنشاء حساب", href: "/signup/" },
      { label: "الخصوصية", href: "/privacy/" },
      { label: "الشروط", href: "/terms/" },
    ],
  },
} as const;
