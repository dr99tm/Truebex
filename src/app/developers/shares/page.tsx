import { GroupDocPage, groupMetadata } from "@/components/developers/GroupDocPage";

export const metadata = groupMetadata("shares");

export default function Page() {
  return <GroupDocPage pageKey="shares" />;
}
