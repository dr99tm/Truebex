"use client";

import { useEffect, useRef, useState } from "react";
import { fill } from "@/lib/catalogue";
import { CLOUD } from "@/lib/constants";
import { getJob, getOutput, type TileManifest } from "@/lib/jobs";
import { CubeTileViewer } from "@/viewer/cube";

/**
 * A finished panorama job as the cube-tile viewer shows it. For a job that
 * follows edits it long-polls the job's `rev` (5.2, 25 s) and swaps in the
 * faces each update re-rendered, as the share page does with a live share.
 */
export function TilePreview({ jobId, following }: { jobId: string; following: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<CubeTileViewer | null>(null);
  const [manifest, setManifest] = useState<TileManifest | null>(null);
  const [viewIndex, setViewIndex] = useState(0);
  const [status, setStatus] = useState<string>(CLOUD.preview.loading);

  // Load the output, then (when the job follows edits) keep it current.
  useEffect(() => {
    const abort = new AbortController();
    let rev = -1;
    const load = async () => {
      try {
        const job = await getJob(jobId);
        rev = job.rev;
        if (!job.output_ready) {
          setStatus(CLOUD.preview.none);
          return;
        }
        const out = await getOutput(jobId);
        if (abort.signal.aborted) return;
        setManifest(out);
        setStatus(fill(CLOUD.preview.updated, { seq: out.at_seq }));
        while (following && !abort.signal.aborted) {
          const next = await getJob(jobId, rev, 25, abort.signal);
          if (abort.signal.aborted) return;
          if (next.rev > rev) {
            rev = next.rev;
            if (!next.follow) return;
            const fresh = await getOutput(jobId);
            if (abort.signal.aborted) return;
            setManifest(fresh);
            setStatus(fill(CLOUD.preview.updated, { seq: fresh.at_seq }));
          }
        }
      } catch (err) {
        if (!abort.signal.aborted) setStatus(err instanceof Error ? err.message : CLOUD.errors.generic);
      }
    };
    void load();
    return () => abort.abort();
  }, [jobId, following]);

  // Mount the viewer once, swap tiles on every manifest.
  useEffect(() => {
    const view = manifest?.views[Math.min(viewIndex, (manifest?.views.length ?? 1) - 1)];
    if (!host.current || !manifest || !view) return;
    if (!viewer.current) {
      viewer.current = new CubeTileViewer(host.current, { tilesBase: manifest.tiles_base, label: CLOUD.preview.title });
    }
    viewer.current.update(view, manifest.tiles_base);
  }, [manifest, viewIndex]);

  useEffect(
    () => () => {
      viewer.current?.destroy();
      viewer.current = null;
    },
    []
  );

  return (
    <div>
      <div
        ref={host}
        className="aspect-[16/9] w-full overflow-hidden rounded-[var(--radius-card)] border border-border bg-background"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-text-muted">
        <p role="status">{status}</p>
        {manifest && manifest.views.length > 1 && (
          <label className="flex items-center gap-2">
            {CLOUD.preview.view}
            <select
              value={viewIndex}
              onChange={(e) => setViewIndex(Number(e.target.value))}
              className="rounded-[var(--radius-button)] border border-border bg-background px-2 py-1 text-text-primary"
            >
              {manifest.views.map((v, i) => (
                <option key={v.view} value={i}>
                  {v.title || `${CLOUD.preview.view} ${i + 1}`}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <p className="mt-1 text-xs text-text-muted">{CLOUD.preview.hint}</p>
    </div>
  );
}
