// The public roadmap: src/content/roadmap.json (words by hand, statuses from
// scripts/sync-roadmap.mjs). Safe for client components.
import {
  BadgeCheck,
  Bot,
  Building2,
  Cable,
  Calculator,
  ClipboardCheck,
  Code,
  Crosshair,
  FileInput,
  FileStack,
  FolderInput,
  Glasses,
  Languages,
  Layers,
  LifeBuoy,
  Palette,
  Share2,
  Smartphone,
  Table,
  Terminal,
  Users,
  Wand2,
  Wind,
  type LucideIcon,
} from "lucide-react";
import roadmap from "@/content/roadmap.json";

export type RoadmapStatus = "planned" | "in_progress" | "shipped";

export interface RoadmapItem {
  id: string;
  title: string;
  description: string;
  icon: string;
  theme: string;
  plan_ids: string[];
  status: RoadmapStatus;
  home?: boolean;
}

export interface RoadmapTheme {
  id: string;
  title: string;
}

export const ROADMAP_ITEMS = roadmap.items as RoadmapItem[];
export const ROADMAP_THEMES = roadmap.themes as RoadmapTheme[];

const ICONS: Record<string, LucideIcon> = {
  BadgeCheck,
  Bot,
  Building2,
  Cable,
  Calculator,
  ClipboardCheck,
  Code,
  Crosshair,
  FileInput,
  FileStack,
  FolderInput,
  Glasses,
  Languages,
  Layers,
  LifeBuoy,
  Palette,
  Share2,
  Smartphone,
  Table,
  Terminal,
  Users,
  Wand2,
  Wind,
};

export function roadmapIcon(name: string): LucideIcon {
  return ICONS[name] ?? FileInput;
}

/** Items in each theme, in file order; themes without items are left out. */
export function roadmapByTheme(): { theme: RoadmapTheme; items: RoadmapItem[] }[] {
  return ROADMAP_THEMES.map((theme) => ({
    theme,
    items: ROADMAP_ITEMS.filter((i) => i.theme === theme.id),
  })).filter((g) => g.items.length > 0);
}

/** The home page block: the items flagged `home`, work in progress first. */
export function homeRoadmap(): RoadmapItem[] {
  const order: Record<RoadmapStatus, number> = { in_progress: 0, planned: 1, shipped: 2 };
  return ROADMAP_ITEMS.filter((i) => i.home).sort((a, b) => order[a.status] - order[b.status]);
}

/** Status chip colours: amber for planned (the roadmap colour), accent for
 *  in progress, muted for shipped. */
export const STATUS_CLASS: Record<RoadmapStatus, string> = {
  planned: "border-warn/40 text-warn",
  in_progress: "border-accent/40 text-accent",
  shipped: "border-border text-text-secondary",
};
