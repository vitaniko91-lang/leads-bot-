"use client";
import { useEffect, useState } from "react";
import { clientApi } from "@/hooks/useApi";
import type { LeadDetail } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Textarea } from "@/components/Textarea";
import { Select } from "@/components/Select";
import { fmtMoney, fmtDate } from "@/lib/format";

const CLIENT_STATUSES = [
  { value: "", label: "—" },
  { value: "replied", label: "Replied" },
  { value: "in_dialog", label: "In dialog" },
  { value: "in_work", label: "In work" },
  { value: "rejected", label: "Rejected" },
  { value: "no_response", label: "No response" },
];

export function LeadDetailPanel({
  leadId,
  onUpdated,
}: {
  leadId: number;
  onUpdated: () => void;
}) {
  const [data, setData] = useState<LeadDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [clientStatus, setClientStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    clientApi<LeadDetail>(`/api/leads/${leadId}`).then((d) => {
      if (live) {
        setData(d);
        setNotes(d.responses[0]?.notes ?? "");
        setClientStatus(d.responses[0]?.client_status ?? "");
      }
    });
    return () => { live = false; };
  }, [leadId]);

  async function save() {
    setSaving(true);
    try {
      const updated = await clientApi<LeadDetail>(`/api/leads/${leadId}`, {
        method: "PATCH",
        body: JSON.stringify({
          notes: notes || null,
          client_status: clientStatus || null,
        }),
      });
      setData(updated);
      onUpdated();
    } finally {
      setSaving(false);
    }
  }

  if (!data) return <div className="text-textMuted">Loading…</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge tone="accent">{data.status}</Badge>
        <Badge>score {data.relevance_score ?? "—"}</Badge>
        <Badge>{fmtMoney(data.budget_usd)}</Badge>
        {data.client_country && <Badge tone="info">{data.client_country}</Badge>}
      </div>

      <section>
        <div className="uppercase-label mb-1.5">Original</div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{data.raw_text}</p>
      </section>

      {data.responses[0] && (
        <section>
          <div className="uppercase-label mb-1.5">Draft</div>
          <p className="text-sm whitespace-pre-wrap leading-relaxed bg-surfaceHi p-3 rounded-md border border-border">
            {data.responses[0].final_text ?? data.responses[0].draft_text}
          </p>
          {data.responses[0].sent_at && (
            <div className="text-xs text-textMuted mt-2">Sent {fmtDate(data.responses[0].sent_at)}</div>
          )}
        </section>
      )}

      {data.reasoning && (
        <section>
          <div className="uppercase-label mb-1.5">Claude reasoning</div>
          <p className="text-sm text-textMuted">{data.reasoning}</p>
        </section>
      )}

      <section className="space-y-3 pt-3 border-t border-border">
        <div className="uppercase-label">Mini-CRM</div>
        <Select
          label="Client status"
          value={clientStatus}
          onChange={(e) => setClientStatus(e.target.value)}
          options={CLIENT_STATUSES}
        />
        <Textarea
          label="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Conversation notes, follow-up reminders…"
        />
        <Button onClick={save} loading={saving} fullWidth>
          Save
        </Button>
      </section>
    </div>
  );
}
