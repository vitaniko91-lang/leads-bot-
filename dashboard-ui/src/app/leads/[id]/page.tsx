import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { fmtMoney, fmtDate } from "@/lib/format";
import type { LeadDetail } from "@/lib/types";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await api<LeadDetail>(`/api/leads/${id}`);

  return (
    <>
      <PageHeader
        title={`Lead #${data.id}`}
        subtitle={data.source_title ?? "—"}
        action={
          <Link href="/leads" className="text-sm text-textMuted hover:text-text">
            ← All leads
          </Link>
        }
      />

      <div className="flex flex-wrap items-center gap-2 mb-6">
        <Badge tone="accent">{data.status}</Badge>
        <Badge>score {data.relevance_score ?? "—"}</Badge>
        <Badge>{fmtMoney(data.budget_usd)}</Badge>
        {data.project_type && <Badge tone="info">{data.project_type}</Badge>}
        {data.client_country && <Badge tone="info">{data.client_country}</Badge>}
        {data.language && <Badge>{data.language}</Badge>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Original message" subtitle={fmtDate(data.posted_at)} />
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{data.raw_text}</p>
        </Card>

        {data.responses[0] && (
          <Card>
            <CardHeader
              title="Draft / sent reply"
              subtitle={
                data.responses[0].sent_at
                  ? `Sent ${fmtDate(data.responses[0].sent_at)}`
                  : "Not sent yet"
              }
            />
            <p className="text-sm whitespace-pre-wrap leading-relaxed">
              {data.responses[0].final_text ?? data.responses[0].draft_text}
            </p>
          </Card>
        )}

        {data.reasoning && (
          <Card>
            <CardHeader title="Claude reasoning" />
            <p className="text-sm text-textMuted leading-relaxed">{data.reasoning}</p>
          </Card>
        )}

        {data.responses[0] && (
          <Card>
            <CardHeader title="Status / notes" />
            <dl className="text-sm space-y-2">
              <div className="flex justify-between">
                <dt className="text-textMuted">Client replied</dt>
                <dd>{data.responses[0].client_replied ? "Yes" : "No"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-textMuted">Client status</dt>
                <dd>{data.responses[0].client_status ?? "—"}</dd>
              </div>
              {data.responses[0].notes && (
                <div>
                  <dt className="text-textMuted">Notes</dt>
                  <dd className="mt-1 whitespace-pre-wrap">{data.responses[0].notes}</dd>
                </div>
              )}
            </dl>
          </Card>
        )}
      </div>
    </>
  );
}
