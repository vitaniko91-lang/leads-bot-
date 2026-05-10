"use client";
import { useState } from "react";
import { Table, type Column } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import { fmtNum, fmtPct } from "@/lib/format";
import type { SourceSummary } from "@/lib/types";

export function SourcesTable({ initial }: { initial: SourceSummary[] }) {
  const [rows, setRows] = useState(initial);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function toggle(src: SourceSummary) {
    setBusyId(src.id);
    try {
      const next = src.status === "active" ? "paused" : "active";
      const updated = await clientApi<SourceSummary>(`/api/sources/${src.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      setRows((cur) => cur.map((r) => (r.id === src.id ? { ...r, status: updated.status } : r)));
    } finally {
      setBusyId(null);
    }
  }

  async function muteHour(src: SourceSummary) {
    setBusyId(src.id);
    try {
      await clientApi(`/api/sources/${src.id}`, {
        method: "PATCH",
        body: JSON.stringify({ mute_for_minutes: 60 }),
      });
    } finally {
      setBusyId(null);
    }
  }

  const columns: Column<SourceSummary>[] = [
    { key: "id", header: "#", width: "60px", render: (s) => <span className="text-textMuted">{s.id}</span> },
    { key: "title", header: "Title", render: (s) => s.title },
    { key: "region", header: "Region", width: "100px", render: (s) => <Badge>{s.region}</Badge> },
    { key: "lang", header: "Lang", width: "70px", render: (s) => s.language },
    {
      key: "leads", header: "Leads/d", width: "90px", align: "right",
      render: (s) => <span className="tabular-nums">{fmtNum(s.leads_per_day)}</span>,
    },
    {
      key: "sent", header: "Sent/d", width: "90px", align: "right",
      render: (s) => <span className="tabular-nums">{fmtNum(s.sent_per_day)}</span>,
    },
    {
      key: "conv", header: "Conv.", width: "90px", align: "right",
      render: (s) => <span className="tabular-nums">{fmtPct(s.conversion_pct)}</span>,
    },
    {
      key: "status", header: "Status", width: "110px",
      render: (s) => (
        <Badge tone={s.status === "active" ? "accent" : s.status === "paused" ? "warn" : "danger"}>
          {s.status}
        </Badge>
      ),
    },
    {
      key: "actions", header: "", width: "180px", align: "right",
      render: (s) => (
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={busyId === s.id}
            onClick={() => toggle(s)}
          >
            {s.status === "active" ? "Pause" : "Resume"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busyId === s.id}
            onClick={() => muteHour(s)}
          >
            Mute 1h
          </Button>
        </div>
      ),
    },
  ];

  return <Table rows={rows} columns={columns} rowKey={(s) => s.id} empty="No sources yet." />;
}
