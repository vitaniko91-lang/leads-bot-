import { api } from "@/lib/api";
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
      <SourcesTable initial={data.items} />
    </>
  );
}
