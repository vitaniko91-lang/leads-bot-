"use client";
import { useState } from "react";
import { Table, type Column } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Drawer } from "@/components/Drawer";
import { LeadDetailPanel } from "./LeadDetailPanel";
import { fmtRelative, fmtMoney } from "@/lib/format";
import type { LeadListResponse, LeadSummary } from "@/lib/types";
import { useLeadsStream } from "@/hooks/useLeadsStream";

const STATUS_TONE: Record<string, "neutral" | "accent" | "warn" | "danger" | "info"> = {
  new: "info",
  drafted: "warn",
  approved: "accent",
  sent: "accent",
  skipped: "neutral",
  filtered_out: "danger",
  expired: "neutral",
  analysis_failed: "danger",
};

export function LeadsTable({ initial }: { initial: LeadListResponse }) {
  const [rows, setRows] = useState(initial.items);
  const [active, setActive] = useState<number | null>(null);

  useLeadsStream((evt) => {
    setRows((cur) => [
      {
        id: evt.id,
        source_id: evt.source_id,
        source_title: null,
        raw_text: evt.raw_text ?? "",
        posted_at: new Date().toISOString(),
        analyzed_at: null,
        is_lead: null,
        project_type: null,
        budget_usd: null,
        language: null,
        client_country: null,
        urgency: null,
        relevance_score: evt.relevance_score ?? null,
        status: evt.status,
        has_response: false,
      },
      ...cur,
    ]);
  });

  const columns: Column<LeadSummary>[] = [
    {
      key: "id", header: "#", width: "60px",
      render: (l) => <span className="text-textMuted">{l.id}</span>,
    },
    {
      key: "score", header: "Score", width: "80px",
      render: (l) =>
        l.relevance_score == null
          ? <span className="text-textDim">—</span>
          : <span className={l.relevance_score >= 80 ? "text-accent font-semibold" : ""}>{l.relevance_score}</span>,
    },
    {
      key: "text", header: "Message",
      render: (l) => <span className="line-clamp-1 text-text">{l.raw_text.slice(0, 120)}</span>,
    },
    {
      key: "budget", header: "Budget", width: "100px", align: "right",
      render: (l) => fmtMoney(l.budget_usd),
    },
    {
      key: "status", header: "Status", width: "120px",
      render: (l) => <Badge tone={STATUS_TONE[l.status] ?? "neutral"}>{l.status}</Badge>,
    },
    {
      key: "when", header: "Posted", width: "120px",
      render: (l) => <span className="text-textMuted">{fmtRelative(l.posted_at)}</span>,
    },
  ];

  return (
    <>
      <Table
        rows={rows}
        columns={columns}
        rowKey={(l) => l.id}
        onRowClick={(l) => setActive(l.id)}
        empty="No leads match these filters."
      />
      <Drawer
        open={active != null}
        onClose={() => setActive(null)}
        title={active ? `Lead #${active}` : undefined}
      >
        {active != null && <LeadDetailPanel leadId={active} onUpdated={() => {}} />}
      </Drawer>
    </>
  );
}
