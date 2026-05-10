import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { LeadFiltersBar } from "@/components/LeadFiltersBar";
import { LeadsTable } from "./LeadsTable";
import type { LeadListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type SP = Record<string, string | undefined>;

function buildQuery(sp: SP): string {
  const p = new URLSearchParams();
  for (const k of ["status", "min_score", "language", "region", "source_id"]) {
    const v = sp[k];
    if (v) p.set(k, v);
  }
  if (!p.has("limit")) p.set("limit", "50");
  return p.toString();
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<SP>;
}) {
  const sp = await searchParams;
  const data = await api<LeadListResponse>(`/api/leads?${buildQuery(sp)}`);

  return (
    <>
      <PageHeader title="Leads" subtitle={`${data.total} total`} />
      <LeadFiltersBar />
      <LeadsTable initial={data} />
    </>
  );
}
