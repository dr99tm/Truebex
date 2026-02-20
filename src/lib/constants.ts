import {
  PenTool,
  ShoppingBag,
  Calculator,
  Glasses,
  RefreshCw,
  Building2,
  Palette,
  HardHat,
  Wrench,
  Users,
} from "lucide-react";

export const NAV_LINKS = [
  { label: "About", href: "#about" },
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Who It's For", href: "#who-its-for" },
  { label: "Why Truebex", href: "#why-truebex" },
  { label: "Pricing", href: "#pricing" },
  { label: "Contact", href: "#contact" },
] as const;

export const FEATURES = [
  {
    id: "design",
    icon: PenTool,
    title: "Design",
    description:
      "Create and shape buildings and spaces with intuitive tools built for architects and designers. Every model is dimensionally accurate from the first stroke.",
  },
  {
    id: "market",
    icon: ShoppingBag,
    title: "Surf the Market",
    description:
      "Browse and place real-world objects, materials, and products directly within your design. What you select is what can be sourced, priced, and built.",
  },
  {
    id: "calculate",
    icon: Calculator,
    title: "Calculate",
    description:
      "Automatically compute areas, volumes, material quantities, and construction estimates as you design. Numbers are native, not secondary.",
  },
  {
    id: "vr",
    icon: Glasses,
    title: "Experience in VR",
    description:
      "Step into your design instantly. Walk through spaces in virtual reality during the design process — not weeks later as a rendered video.",
  },
  {
    id: "sync",
    icon: RefreshCw,
    title: "Instant Changes",
    description:
      "Every modification syncs across design, calculations, market selections, and VR in real time. No exports. No delays. No broken handoffs.",
  },
] as const;

export const STEPS = [
  {
    number: "01",
    title: "Design Your Space",
    description:
      "Start with your building design using powerful yet intuitive tools. Every dimension is real from the start.",
  },
  {
    number: "02",
    title: "Select Real Materials",
    description:
      "Browse the integrated marketplace for actual products, materials, and finishes. Place them directly into your model.",
  },
  {
    number: "03",
    title: "Calculate Everything",
    description:
      "Get instant, accurate calculations — areas, volumes, quantities, and estimates — updated live as you design.",
  },
  {
    number: "04",
    title: "Experience It Live",
    description:
      "Walk through your design in VR with all selections applied. See the space as it will truly exist — in real time.",
  },
] as const;

export const AUDIENCES = [
  {
    icon: Building2,
    title: "Architects",
    description:
      "Design with precision and experience your creations in VR before a single brick is laid.",
  },
  {
    icon: Palette,
    title: "Interior Designers",
    description:
      "Select real materials and furnishings, then walk through your spaces to ensure every detail is right.",
  },
  {
    icon: HardHat,
    title: "Developers & Contractors",
    description:
      "Get accurate quantity calculations and cost projections directly from the design model.",
  },
  {
    icon: Wrench,
    title: "Engineers",
    description:
      "Work with precise measurements and real-time calculation updates as designs evolve.",
  },
  {
    icon: Users,
    title: "Clients & Stakeholders",
    description:
      "Experience your future space in VR and make confident decisions before construction begins.",
  },
] as const;

export const PRICING_PLANS = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "Get started with core design tools and explore the platform.",
    features: [
      "Basic 3D design tools",
      "Limited material library",
      "Area & volume calculations",
      "Community support",
      "1 active project",
    ],
    cta: "Get Started",
    highlighted: false,
  },
  {
    name: "Professional",
    price: "$49",
    period: "/month",
    description: "Full platform access for professionals who demand accuracy.",
    features: [
      "Advanced design tools",
      "Full market object library",
      "Complete calculations suite",
      "Instant VR experience",
      "Real-time sync across all views",
      "Unlimited projects",
      "Priority support",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "Tailored solutions for teams and organizations at scale.",
    features: [
      "Everything in Professional",
      "Team collaboration",
      "Custom object libraries",
      "API access & integrations",
      "Dedicated account manager",
      "On-premise deployment option",
      "SLA guarantee",
    ],
    cta: "Contact Sales",
    highlighted: false,
  },
] as const;

export const DIFFERENTIATORS = [
  {
    traditional: "Switch between disconnected tools",
    truebex: "Design, market, calculate, and VR in one platform",
  },
  {
    traditional: "Use placeholder objects and generic materials",
    truebex: "Every object comes from the real marketplace",
  },
  {
    traditional: "Wait weeks for rendered visualizations",
    truebex: "Step into VR instantly during design",
  },
  {
    traditional: "Re-enter data when designs change",
    truebex: "Everything stays in sync — automatically",
  },
  {
    traditional: "Different tools for different team members",
    truebex: "One environment for the entire team",
  },
] as const;
