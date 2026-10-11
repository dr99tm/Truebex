import { GroupDocPage, groupMetadata } from "@/components/developers/GroupDocPage";

export const metadata = groupMetadata("projects");

export default function Page() {
  return <GroupDocPage pageKey="projects" />;
}
