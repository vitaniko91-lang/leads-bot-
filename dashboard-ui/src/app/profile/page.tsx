import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ProfileForm } from "./ProfileForm";
import type { ProfilePayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  let profile: ProfilePayload | null = null;
  try {
    profile = await api<ProfilePayload>("/api/profile");
  } catch {
    /* file not found — show empty form */
  }

  return (
    <>
      <PageHeader
        title="Profile"
        subtitle="Used by the drafter to personalize replies"
      />
      <ProfileForm initial={profile} />
    </>
  );
}
