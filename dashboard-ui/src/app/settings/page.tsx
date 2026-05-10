import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { SettingsForm } from "./SettingsForm";
import type { SettingsPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settings = await api<SettingsPayload>("/api/settings");
  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Operational thresholds (persisted to data/settings.json)"
      />
      <SettingsForm initial={settings} />
    </>
  );
}
