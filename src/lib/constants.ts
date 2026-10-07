import {
  PenTool,
  Sun,
  Footprints,
  Ruler,
  LayoutPanelTop,
  Zap,
  ShoppingBag,
  Calculator,
  Glasses,
  Code2,
  Building2,
  Palette,
  HardHat,
  Wrench,
  Users,
} from "lucide-react";

// Content follows the brand voice in .claude/skills/truebex-brand-voice.
// Claims here must be true of the shipping desktop app; anything planned
// goes in ROADMAP, never in FEATURES.

export const SITE = {
  name: "Truebex",
  url: "https://truebex.com",
  tagline: "True Building Experience",
  title: "Truebex — Real-Time Architectural Design on Unreal Engine 5.7",
  description:
    "Truebex is a real-time 2D + 3D building design tool. Draw walls and rooms, light them with Lumen, see live room areas, and walk through your design in first person — while you design.",
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
    id: "model",
    icon: PenTool,
    title: "One model, plan and 3D",
    description:
      "Draw walls, rooms, doors, windows, slabs and stairs in plan — the 3D building forms as you draw. Arcs, groups, reference planes and locked dimensions keep your design intent intact.",
  },
  {
    id: "light",
    icon: Sun,
    title: "Real light, in real time",
    description:
      "Lumen global illumination, sun and sky, and daylight measured through every window and door. Hardware ray tracing and path tracing when you need the final word.",
  },
  {
    id: "walk",
    icon: Footprints,
    title: "Walk through it",
    description:
      "Switch to first person at any moment and walk the rooms at eye height, with collision. Feel the proportions of a space before anyone pours a foundation.",
  },
  {
    id: "measure",
    icon: Ruler,
    title: "Live areas and dimensions",
    description:
      "Rooms know their size. Areas update the instant a wall moves, and dimensions you lock hold their numbers while everything else adapts.",
  },
  {
    id: "faces",
    icon: LayoutPanelTop,
    title: "Wall faces as design surfaces",
    description:
      "Panel any wall face, nest regions, and fill them with dynamic patterns. Save a face as an asset — edit it once and every placed copy updates.",
  },
  {
    id: "speed",
    icon: Zap,
    title: "Changes in milliseconds",
    description:
      "Edits cost only what they change. Dragging a wall in a full scene went from 240 ms to 4.3 ms in our benchmark, so the model keeps up with your thinking.",
  },
] as const;

// Where the platform is going. Shown as "on the roadmap", never as shipped.
export const ROADMAP = [
  {
    icon: ShoppingBag,
    title: "Real-product marketplace",
    description: "Place sourceable materials and products straight into the model.",
  },
  {
    icon: Calculator,
    title: "Quantities and cost",
    description: "Take-offs and estimates generated from the same live model.",
  },
  {
    icon: Glasses,
    title: "VR headsets",
    description: "The first-person walk mode, in a headset.",
  },
  {
    icon: Code2,
    title: "Project API",
    description: "Read and drive projects and assets through the developer API.",
  },
] as const;

export const PRODUCT_SHOTS = [
  {
    src: "/images/product/rooms-area-labels.jpg",
    alt: "Truebex 3D view of a living room and bedroom with live room-area labels (Living Room 20.36 m², Bedroom 20.06 m²)",
    caption: "Rooms label their own areas — and update as walls move.",
    width: 1200,
    height: 863,
  },
  {
    src: "/images/product/first-person-walkthrough.jpg",
    alt: "First-person walkthrough inside a daylit Truebex interior rendered with Lumen",
    caption: "First person at eye height, lit by Lumen.",
    width: 1200,
    height: 897,
  },
  {
    src: "/images/product/wall-face-panels.jpg",
    alt: "A wall face in Truebex split into panel regions around a window opening, with region area and fill",
    caption: "Panels, regions and fills on any wall face.",
    width: 1200,
    height: 778,
  },
] as const;

export const STEPS = [
  {
    number: "01",
    title: "Draw the plan",
    description:
      "Lay out walls, rooms and openings in 2D. The 3D building forms with every line.",
  },
  {
    number: "02",
    title: "Shape the surfaces",
    description:
      "Panel wall faces, nest regions and apply fills. Save what works as a reusable asset.",
  },
  {
    number: "03",
    title: "Light it",
    description:
      "Sun, sky and Lumen global illumination show how daylight really reaches each room.",
  },
  {
    number: "04",
    title: "Walk it",
    description:
      "Drop into first person, walk the rooms, change a wall — and keep walking.",
  },
] as const;

export const AUDIENCES = [
  {
    icon: Building2,
    title: "Architects",
    description:
      "Design in plan and judge the space in real light, at real scale, in the same session.",
  },
  {
    icon: Palette,
    title: "Interior Designers",
    description:
      "Shape wall faces, panels and finishes, then walk the room to see how they read in daylight.",
  },
  {
    icon: HardHat,
    title: "Developers & Contractors",
    description:
      "Live room areas and locked dimensions keep the numbers honest as the design moves.",
  },
  {
    icon: Wrench,
    title: "Engineers",
    description:
      "Reference planes, constraints and dimension locks keep relationships intact while hosts resize.",
  },
  {
    icon: Users,
    title: "Clients & Stakeholders",
    description:
      "Walk the space before it exists and decide with confidence, not from a flat render.",
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
      "2D plan + 3D model",
      "First-person walk mode",
      "Live room areas",
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
    description: "For professionals who design, light and present every day.",
    features: [
      "Everything in Starter",
      "Full lighting suite: Lumen, ray tracing, path tracing",
      "Wall-face panels, fills and asset library",
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

export const DIFFERENTIATORS = [
  {
    traditional: "Model in one tool, render in another",
    truebex: "Model and light live in the same real-time engine",
  },
  {
    traditional: "Wait for overnight renders",
    truebex: "Lumen light updates while you draw",
  },
  {
    traditional: "Fly-through videos made after the design is done",
    truebex: "Walk through it in first person, any time",
  },
  {
    traditional: "Re-measure areas by hand after every change",
    truebex: "Room areas update as walls move",
  },
  {
    traditional: "Redraw the same wall detail on every project",
    truebex: "Save a wall face as an asset — edit once, update everywhere",
  },
] as const;

export const FAQS = [
  {
    q: "What is Truebex?",
    a: "Truebex is a desktop building design tool that works in 2D plan and 3D at once. It runs on Unreal Engine 5.7, so the model you draw is lit with real-time global illumination and can be walked through in first person while you design.",
  },
  {
    q: "Is Truebex a Revit alternative?",
    a: "Truebex works the way architects expect from BIM tools — walls, rooms, openings, dimensions and reference planes — but it is its own application, not a Revit plug-in. Its difference is that design, lighting and walkthrough happen in the same real-time model.",
  },
  {
    q: "Can I walk through my design?",
    a: "Yes. First-person mode puts you inside the model at eye height with collision, and you can switch to it at any point while designing.",
  },
  {
    q: "Does Truebex calculate areas?",
    a: "Rooms show their area live and update as walls move. Full quantity take-offs and cost estimates are on the roadmap.",
  },
  {
    q: "What hardware do I need?",
    a: "A Windows PC with a modern DirectX 12 graphics card. NVIDIA RTX cards also unlock DLSS 4.5 and hardware ray tracing.",
  },
  {
    q: "Is there an API for developers?",
    a: "Yes. Create API keys in your dashboard and call the Truebex API with a bearer token. Every plan includes a monthly request allowance; see the developer docs.",
  },
  {
    q: "How can I pay?",
    a: "Professional plans are billed monthly. We are rolling out card payments through Stripe and local payment in Iraq through Wayl (QiCard, FIB and ZainCash).",
  },
] as const;
