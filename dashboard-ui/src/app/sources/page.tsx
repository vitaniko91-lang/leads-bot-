import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { DiscoveryPanel } from "@/components/DiscoveryPanel";
import { PageHeader } from "@/components/PageHeader";
import { SourcesTable } from "./SourcesTable";
import type { SourceSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const data = await api<{ items: SourceSummary[] }>("/api/sources");

  return (
    <>
      <PageHeader
        title="Sources"
        subtitle={`${data.items.length} channels tracked`}
      />

      <Card className="mb-6">
        <CardHeader
          title="Pending channels (discovery)"
          subtitle="Found by weekly auto-scan — Add to start tracking, Reject to never suggest again"
        />
        <DiscoveryPanel />
      </Card>

      <SourcesTable initial={data.items} />
    </>
  );
}
