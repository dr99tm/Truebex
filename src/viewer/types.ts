// The share page's data (contract share-bundle v1.1, 5.10): the manifest of
// §6.1 with every file's signed URL and the panorama derivatives PF5 makes.

export interface Hotspot {
  target: string;
  bearing_deg: number;
  pitch_deg: number;
  label?: string | null;
}

export interface Derivative {
  url: string;
  width: number;
  height: number;
  bytes: number;
}

export interface Panorama {
  id: string;
  title: string;
  file: string;
  width: number;
  height: number;
  storey?: string | null;
  center_bearing_deg: number;
  start_bearing_deg?: number;
  start_pitch_deg?: number;
  start_hfov_deg?: number;
  hotspots?: Hotspot[];
  derivatives?: Partial<Record<"pano-4096" | "pano-1024", Derivative>>;
  /** PF6 (a MINOR proposal): a followed render set this view shows live. */
  live_job_id?: string | null;
}

export interface Render {
  id: string;
  title: string;
  file: string;
  width: number;
  height: number;
}

export interface BundleFile {
  sha256: string;
  bytes: number;
  content_type: string;
  /** A relative path inside the bundle; it may hold folders (1.1). */
  name: string;
  url?: string | null;
}

export interface Manifest {
  schema: string;
  bundle_id: string;
  watermark: boolean;
  project: {
    title: string;
    units?: string;
    region?: string | null;
    /** 1.1: the project card. */
    storeys?: number;
    rooms?: number;
    floor_area_m2?: number;
  };
  start?: string | null;
  /** 1.1: the SHA-256 of the link-preview JPEG (the API serves it as the card). */
  cover?: string | null;
  branding?: { designed_in?: boolean };
  panoramas: Panorama[];
  renders: Render[];
  sheets?: { file: string; pages?: number; titles?: string[] } | null;
  files: BundleFile[];
}

export interface PageData {
  title: string;
  created_at: string;
  published_at?: string | null;
  expires_at: string | null;
  watermark: boolean;
  designed_in: string;
  url?: string;
  /** 1.1: 1, + 1 per Update the designer published. */
  version?: number;
  manifest: Manifest;
}

/** The manifest MAJOR this viewer reads. */
export const SCHEMA_MAJOR = 1;

export function schemaMajor(schema: unknown): number | null {
  const m = typeof schema === "string" ? /^truebex-share\/(\d+)$/.exec(schema) : null;
  return m ? Number(m[1]) : null;
}
