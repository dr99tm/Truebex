// A /developers/<group>/ page (PF12): the words from DEVELOPER_DOCS.pages, the
// reference generated from openapi/v1.json for its route groups.
import type { Metadata } from "next";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import { operations } from "@/lib/developer-docs";
import { pageMetadata } from "@/lib/seo";
import { DevPage, Notes, OperationReference, devPath } from "./DevDocs";

export type GroupKey = "projects" | "jobs" | "shares" | "market";

export function groupMetadata(key: keyof typeof D.pages): Metadata {
  const page = D.pages[key];
  return pageMetadata({ title: page.title, description: page.description, path: devPath(key) });
}

export function GroupDocPage({ pageKey }: { pageKey: GroupKey }) {
  const page = D.pages[pageKey];
  return (
    <DevPage slug={pageKey} h1={page.h1} intro={page.intro} description={page.description} status={page.status}>
      <Notes title={page.notesTitle} notes={page.notes} />
      <OperationReference ops={operations(page.groups)} />
    </DevPage>
  );
}
