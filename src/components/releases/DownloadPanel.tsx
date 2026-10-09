"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import { DOWNLOAD } from "@/lib/constants";
import { getDownloadLink, getReleaseFeed } from "@/lib/licence";
import { formatBytes, formatReleaseDate, type ReleaseManifest } from "@/lib/releases";
import { cn } from "@/lib/utils";

type Shown = Pick<ReleaseManifest, "version" | "channel" | "published_at" | "installer">;

/**
 * The latest release of a channel and a Download button. The server renders
 * the build-time release (src/content/releases*.json); after load the live
 * feed replaces it if it is newer, and the button asks the API for a fresh
 * 15-minute link at click time. Downloads need no account. Give it
 * `key={channel}` when the channel can change.
 */
export function DownloadPanel({
  initial,
  channel = "stable",
  compact = false,
  className,
}: {
  initial: Shown | null;
  channel?: "stable" | "beta";
  compact?: boolean;
  className?: string;
}) {
  const [release, setRelease] = useState<Shown | null>(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    getReleaseFeed(channel)
      .then((feed) => {
        const live = feed.releases.find((r) => r.manifest.version === feed.latest)?.manifest;
        if (!cancelled && live) setRelease(fromManifest(live));
      })
      .catch(() => {
        /* offline or no API: keep the build-time release */
      });
    return () => {
      cancelled = true;
    };
  }, [channel]);

  async function download() {
    setBusy(true);
    setMessage("");
    try {
      let version = release?.version;
      if (!version) {
        const feed = await getReleaseFeed(channel);
        version = feed.latest ?? undefined;
      }
      if (!version) {
        setMessage(DOWNLOAD.noRelease);
        return;
      }
      const link = await getDownloadLink(version);
      window.location.assign(link.url);
    } catch (err) {
      setMessage(
        err instanceof ApiError && err.status === 0
          ? DOWNLOAD.offline
          : err instanceof ApiError && err.status === 404
            ? DOWNLOAD.noRelease
            : err instanceof Error
              ? err.message
              : DOWNLOAD.offline
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={className} data-release={initial?.version ?? "none"}>
      {release ? (
        <dl className={cn("grid gap-x-6 gap-y-2 text-sm", compact ? "grid-cols-2" : "sm:grid-cols-3")}>
          <div>
            <dt className="text-text-muted">{DOWNLOAD.version}</dt>
            <dd className="mt-0.5 font-semibold text-text-primary">
              {release.version}
              {release.channel === "beta" && (
                <span className="ml-2 rounded-full border border-warn/40 px-2 py-0.5 text-xs font-medium text-warn">
                  {DOWNLOAD.beta}
                </span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-text-muted">{DOWNLOAD.size}</dt>
            <dd className="mt-0.5 text-text-primary">{formatBytes(release.installer.bytes)}</dd>
          </div>
          <div className={compact ? "col-span-2" : undefined}>
            <dt className="text-text-muted">{DOWNLOAD.released}</dt>
            <dd className="mt-0.5 text-text-primary">{formatReleaseDate(release.published_at)}</dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-text-secondary">{DOWNLOAD.noRelease}</p>
      )}

      <div className={cn("flex flex-wrap items-center gap-3", release ? "mt-5" : "mt-4")}>
        <Button onClick={download} disabled={busy} size={compact ? "sm" : "lg"}>
          <Download size={16} aria-hidden />
          <span className="ml-2">
            {busy ? DOWNLOAD.preparing : channel === "beta" ? DOWNLOAD.ctaBeta : DOWNLOAD.cta}
          </span>
        </Button>
      </div>
      {message && (
        <p role="status" className="mt-3 text-sm text-text-secondary">
          {message}
        </p>
      )}
      {release && !compact && (
        <p className="mt-4 break-all font-mono text-xs text-text-muted">
          {DOWNLOAD.checksum} {release.installer.sha256}
        </p>
      )}
    </div>
  );
}

function fromManifest(m: ReleaseManifest): Shown {
  return { version: m.version, channel: m.channel, published_at: m.published_at, installer: m.installer };
}
