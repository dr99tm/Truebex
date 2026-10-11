import { GroupDocPage, groupMetadata } from "@/components/developers/GroupDocPage";

export const metadata = groupMetadata("jobs");

export default function Page() {
  return <GroupDocPage pageKey="jobs" />;
}
