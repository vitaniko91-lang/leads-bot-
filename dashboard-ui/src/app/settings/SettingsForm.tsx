"use client";
import { useState } from "react";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { SettingsPayload } from "@/lib/types";

export function SettingsForm({ initial }: { initial: SettingsPayload }) {
  const [data, setData] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof SettingsPayload>(k: K, v: SettingsPayload[K]) {
    setData((d) => ({ ...d, [k]: v }));
  }

  async function save() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await clientApi("/api/settings", {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      setSaved(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Quiet hours (HH:MM-HH:MM)"
            value={data.quiet_hours}
            onChange={(e) => set("quiet_hours", e.target.value)}
            hint="e.g. 23:00-08:00"
          />
          <Input
            label="Min budget (USD)"
            type="number"
            value={data.min_budget_usd}
            onChange={(e) => set("min_budget_usd", Number(e.target.value))}
          />
          <Input
            label="Min relevance score"
            type="number"
            min={0}
            max={100}
            value={data.min_relevance_score}
            onChange={(e) => set("min_relevance_score", Number(e.target.value))}
          />
          <Input
            label="Max responses / hour"
            type="number"
            value={data.max_responses_per_hour}
            onChange={(e) => set("max_responses_per_hour", Number(e.target.value))}
          />
          <Input
            label="Max responses / day"
            type="number"
            value={data.max_responses_per_day}
            onChange={(e) => set("max_responses_per_day", Number(e.target.value))}
          />
          <Input
            label="Max responses / week"
            type="number"
            value={data.max_responses_per_week}
            onChange={(e) => set("max_responses_per_week", Number(e.target.value))}
          />
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} loading={saving}>Save settings</Button>
        {saved && <span className="text-sm text-accent">Saved.</span>}
        {error && <span className="text-sm text-danger">{error}</span>}
      </div>
    </div>
  );
}
