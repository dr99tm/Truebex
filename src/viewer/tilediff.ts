// Which tiles changed between two manifests of one view (render-jobs §6.2):
// a `tiles` job re-renders a few faces and carries the rest, so a viewer
// fetches only the new hashes. The mobile client uses it for the "faces
// updated" line, for keeping the offline copy current, and for the headset
// mode, which re-composes only the faces that changed. Framework-free.

export type FaceName = "n" | "e" | "s" | "w" | "u" | "d";
export const FACE_ORDER: readonly FaceName[] = ["n", "e", "s", "w", "u", "d"];

export interface TileViewLike {
  view?: string;
  tile_px: number;
  levels: number[];
  faces: Partial<Record<FaceName, { tiles: string[][] }>>;
}

export interface TileDiff {
  /** Faces with at least one changed tile, in compass order. */
  faces: FaceName[];
  /** `face:level:index` of every changed tile. */
  changed: string[];
  /** The new hashes, each once, in face order. */
  fetch: string[];
}

/** Tiles of `next` that `prev` did not show at the same face, level and place. */
export function diffTiles(prev: TileViewLike | null | undefined, next: TileViewLike): TileDiff {
  const faces: FaceName[] = [];
  const changed: string[] = [];
  const fetch: string[] = [];
  const seen = new Set<string>();
  for (const face of FACE_ORDER) {
    const after = next.faces[face]?.tiles ?? [];
    const before = prev?.faces[face]?.tiles ?? [];
    let any = false;
    after.forEach((level, l) => {
      level.forEach((sha, i) => {
        if (before[l]?.[i] === sha) return;
        any = true;
        changed.push(`${face}:${l}:${i}`);
        if (!seen.has(sha)) {
          seen.add(sha);
          fetch.push(sha);
        }
      });
    });
    if (any) faces.push(face);
  }
  return { faces, changed, fetch };
}

/** The level a face of `px` pixels on screen needs: the smallest that covers it. */
export function levelFor(view: TileViewLike, px: number): number {
  const i = view.levels.findIndex((size) => size >= px);
  return i === -1 ? view.levels.length - 1 : i;
}

/** The largest level no bigger than `maxPx` (a headset's textures). */
export function levelAtMost(view: TileViewLike, maxPx: number): number {
  let best = 0;
  view.levels.forEach((size, i) => {
    if (size <= maxPx) best = i;
  });
  return best;
}

/** `<tiles_base>/<sha256>.jpg` for every tile of `level` (all six faces). */
export function tileUrls(view: TileViewLike, tilesBase: string, level: number): string[] {
  const base = tilesBase.replace(/\/$/, "");
  const out: string[] = [];
  for (const face of FACE_ORDER) for (const sha of view.faces[face]?.tiles?.[level] ?? []) out.push(`${base}/${sha}.jpg`);
  return [...new Set(out)];
}
