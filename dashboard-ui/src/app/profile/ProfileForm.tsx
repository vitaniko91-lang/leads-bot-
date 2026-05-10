"use client";
import { useState } from "react";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { ProfilePayload } from "@/lib/types";

const empty: ProfilePayload = {
  name: "",
  portfolio_url: "",
  telegram: "",
  min_rate_usd_per_hour: 50,
  tone: "",
  payment_methods: [],
  cases: [],
};

export function ProfileForm({ initial }: { initial: ProfilePayload | null }) {
  const [data, setData] = useState<ProfilePayload>(initial ?? empty);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  function set<K extends keyof ProfilePayload>(k: K, v: ProfilePayload[K]) {
    setData((d) => ({ ...d, [k]: v }));
  }

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      await clientApi<ProfilePayload>("/api/profile", {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Name"
            value={data.name}
            onChange={(e) => set("name", e.target.value)}
          />
          <Input
            label="Telegram"
            value={data.telegram}
            onChange={(e) => set("telegram", e.target.value)}
          />
          <Input
            label="Portfolio URL"
            value={data.portfolio_url}
            onChange={(e) => set("portfolio_url", e.target.value)}
          />
          <Input
            label="Rate (USD/hour)"
            type="number"
            value={data.min_rate_usd_per_hour}
            onChange={(e) => set("min_rate_usd_per_hour", Number(e.target.value))}
          />
        </div>
      </Card>

      <Card>
        <Textarea
          label="Tone"
          value={data.tone}
          onChange={(e) => set("tone", e.target.value)}
          placeholder="friendly but professional, no formality, no excessive emoji"
        />
        <div className="mt-3">
          <Input
            label="Payment methods (comma-separated)"
            value={data.payment_methods.join(", ")}
            onChange={(e) =>
              set("payment_methods", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))
            }
          />
        </div>
      </Card>

      <Card>
        <div className="uppercase-label mb-2">Cases</div>
        <div className="text-sm text-textMuted mb-3">
          {data.cases.length} cases. Edit JSON via Telegram /profile or directly in <code>data/profile.json</code>.
        </div>
        <pre className="text-xs bg-surfaceHi p-3 rounded-md border border-border overflow-x-auto">
          {JSON.stringify(data.cases, null, 2)}
        </pre>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} loading={saving}>Save profile</Button>
        {saved && <span className="text-sm text-accent">Saved.</span>}
      </div>
    </div>
  );
}
