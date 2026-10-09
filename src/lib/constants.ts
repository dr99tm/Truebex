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
    name: "Free",
    price: "$0",
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
    name: "Pro",
    price: "$99",
    period: "/month",
    description: "For professionals who design and present every day.",
    features: [
      "Everything in Free",
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
      "Everything in Pro",
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
    a: "Pro plans are billed monthly by card. Payments are rolling out; the pricing section shows the plans.",
  },
] as const;

// The Download page (/download/) and the dashboard's Download panel. The
// version, size and date come from src/content/releases.json (saved by
// `npm run sync:releases` from the release feed), never typed here.
export const DOWNLOAD = {
  metaTitle: "Download Truebex for Windows",
  description:
    "Download Truebex for Windows: the building design platform with measured daylight. The installer needs no account; a free account holds your licence.",
  eyebrow: "Download",
  h1: "Download Truebex for Windows",
  intro:
    "One installer for Windows. Downloading needs no account, and every download is a signed release whose size and checksum are listed here.",
  cta: "Download for Windows",
  ctaBeta: "Download the beta",
  preparing: "Preparing your download…",
  noRelease: "The installer is published here with each release. Check back soon.",
  offline: "We can't reach the download server right now. Please try again in a moment.",
  version: "Version",
  released: "Released",
  size: "Size",
  checksum: "SHA-256",
  beta: "Beta",
  requirementsTitle: "What you need",
  requirements: [
    "A Windows 10 or Windows 11 PC (64-bit).",
    "A modern graphics card. A card with hardware ray tracing unlocks the highest lighting quality, including ray tracing and path tracing.",
    "About 450 MB of disk space for the installed app.",
  ],
  accountTitle: "Your licence lives in your account",
  accountText:
    "A free Truebex account holds your plan and the computers you use it on, so you can see and remove them from your dashboard.",
  accountCta: "Create a free account",
  changelogCta: "See what's new",
} as const;

// The Changelog page (/changelog/): one section per release from the feed,
// with the release's version as its anchor (#1.1.0, the manifest's notes_url).
export const CHANGELOG_PAGE = {
  metaTitle: "Changelog",
  description:
    "Every Truebex release and what changed in it, newest first: notes for each version of the building design platform for Windows, with a link to download.",
  eyebrow: "Changelog",
  h1: "What's new in Truebex",
  intro: "Every release of Truebex for Windows, newest first.",
  empty: "Release notes appear here with each release.",
  release: "Truebex",
  beta: "Beta",
  downloadCta: "Download the latest release",
} as const;

// Marketplace pages (PF7): the checkout page an order sent from the app opens,
// the buyer's orders and requests, and the admin tools. The marketplace itself
// stays in ROADMAP until roadmap 40 ships it; these pages only serve orders
// and requests for quote that were sent from Truebex.
export const MARKET = {
  states: {
    awaiting_payment: "Awaiting payment",
    paid: "Paid",
    pending: "Waiting for the supplier",
    accepted: "Accepted",
    rejected: "Declined by the supplier",
    shipped: "Shipped",
    delivered: "Delivered",
    cancelled: "Cancelled",
    submitted: "Sent to the supplier",
    quoted: "Quoted",
    declined: "Declined by the supplier",
    expired: "Expired",
  } as Record<string, string>,
  checkout: {
    metaTitle: "Checkout",
    h1: "Checkout",
    intro:
      "Review the order you sent from Truebex, then pay on the payment provider's secure page. Each supplier confirms and delivers its own part.",
    missing: "Open this page from the link Truebex gave you for your order.",
    signIn: "Sign in to see your order",
    loading: "Loading your order…",
    pay: "Pay",
    paying: "Opening the payment page…",
    placedTitle: "Order placed",
    placedText: "Payment received. Each supplier now confirms its part of the order.",
    confirming: "Confirming your payment…",
    stillConfirming: "Your payment is still being confirmed. This page shows it as soon as it is.",
    cancelledPayment: "Payment was cancelled. Nothing was charged.",
    notPayable: "This order has nothing left to pay.",
    quote: "This is a request for quote: each supplier replies with its price. Accept a quote from your orders.",
    secure: "Card details are entered on the payment provider's page. Truebex never sees them.",
    deliveryTo: "Delivery to",
    contact: "Contact",
    products: "Products",
    delivery: "Delivery",
    deliveryDays: "Delivery in {min}–{max} days",
    taxIncluded: "Includes tax",
    tax: "Tax",
    total: "Total",
    qty: "Qty",
    each: "each",
    quoted: "Quoted",
    ordersLink: "See all your orders",
  },
  orders: {
    title: "Orders",
    description: "Orders and requests for quote sent from Truebex, with each supplier's progress.",
    empty: "No orders yet. Orders and requests for quote you send from Truebex appear here.",
    order: "Order",
    quote: "Request for quote",
    project: "Project",
    pay: "Pay now",
    accept: "Accept quote",
    cancel: "Cancel",
    confirmCancel: "Cancel this order? Suppliers that have not accepted it yet will not deliver.",
    validUntil: "Quote valid until",
    expires: "Expires",
    paidOffline: "Each supplier invoices you directly for this order.",
    fromQuote: "From your accepted quote",
  },
  admin: {
    title: "Marketplace",
    description: "Suppliers, the product review queue, reviews, orders, commissions and feed runs.",
    tabs: {
      suppliers: "Suppliers",
      products: "Products",
      reviews: "Reviews",
      orders: "Orders",
      commissions: "Commissions",
      feeds: "Feeds",
    },
    paymentsOff: "Card payments for orders are off (MARKET_PAYMENTS_ENABLED): every supplier takes requests for quote only.",
    paymentsOn: "Card payments for orders are on.",
    paymentsNoStripe: "Card payments for orders are switched on, but Stripe is not configured on this server (STRIPE_SECRET_KEY): Pay answers 503.",
    verify: "Verify",
    suspend: "Suspend",
    reinstate: "Reinstate",
    commission: "Commission (basis points)",
    save: "Save",
    connect: "Payout onboarding link",
    approve: "Approve",
    reject: "Reject",
    withdraw: "Withdraw",
    reason: "Reason (shown to the supplier)",
    publish: "Publish",
    hide: "Hide",
    quoteFor: "Quote for the supplier",
    unitPrice: "Unit price (minor units)",
    deliveryFee: "Delivery fee (minor units)",
    makeStatements: "Make last month's statements",
    empty: "Nothing here.",
    statuses: {
      pending_review: "Waiting for review",
      approved: "Approved",
      rejected: "Rejected",
      withdrawn: "Withdrawn",
      hidden: "Hidden by a feed",
      all: "All",
      pending: "Pending",
      published: "Published",
    } as Record<string, string>,
  },
} as const;
