// Following a live share (PF6, a MINOR proposal for share-bundle §5): when a
// share manifest's panorama names `live_job_id`, the share viewer long-polls
// `GET /s/{slug}/live?rev=` and hands each newer manifest to the cube-tile
// viewer (cube.ts), which swaps only the tiles that changed. No credential:
// the link is the permission, and revoking the share ends it.

import type { CubeView } from "./cube";

export interface LiveState {
  rev: number;
  job_id: string | null;
  at_seq: number;
  following: boolean;
  manifest: { tiles_base: string; views: (CubeView & { view: string })[] } | null;
}

const CONTRACT = { "X-Truebex-Contract": "share-bundle/1.1" };

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });
}

/** Long-poll the share's set until it stops following, the share ends or
 *  `signal` aborts; retries with backoff 1, 2, 4 … 60 s on errors. */
export async function followShareLive(
  api: string,
  slug: string,
  onUpdate: (state: LiveState) => void,
  signal: AbortSignal,
  panorama?: string
): Promise<void> {
  let rev = -1;
  let backoff = 1000;
  while (!signal.aborted) {
    const query = `rev=${rev}&wait_s=25${panorama ? `&panorama=${encodeURIComponent(panorama)}` : ""}`;
    try {
      const res = await fetch(`${api}/s/${encodeURIComponent(slug)}/live?${query}`, { headers: CONTRACT, signal });
      if (res.status === 404 || res.status === 410) return;
      if (!res.ok) throw new Error(`live ${res.status}`);
      const state = (await res.json()) as LiveState;
      backoff = 1000;
      if (state.rev > rev) {
        rev = state.rev;
        if (state.manifest) onUpdate(state);
      }
      if (!state.following) return;
    } catch {
      if (signal.aborted) return;
      await sleep(backoff * (0.8 + Math.random() * 0.4), signal);
      backoff = Math.min(backoff * 2, 60_000);
    }
  }
}
