import { GroupDocPage, groupMetadata } from "@/components/developers/GroupDocPage";

export const metadata = groupMetadata("market");

export default function Page() {
  return <GroupDocPage pageKey="market" />;
}
