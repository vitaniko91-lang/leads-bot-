"use client";

import { useState } from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";
import { Textarea } from "./Textarea";
import { TrafficShareSlider } from "./TrafficShareSlider";
import { clientApi } from "@/hooks/useApi";
import type { Template } from "@/lib/types";

export function TemplateEditor({ initial }: { initial: Template }) {
  const [t, setT] = useState(initial);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await clientApi(`/api/templates/${t.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: t.name,
          prompt: t.prompt,
          traffic_share: t.traffic_share,
          active: t.active,
        }),
      });
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    setBusy(true);
    try {
      const data = await clientApi<{ draft: string }>("/api/templates/preview", {
        method: "POST",
        body: JSON.stringify({ prompt: t.prompt }),
      });
      setPreview(data.draft);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <div className="space-y-4">
        <Input
          label="Name"
          value={t.name}
          onChange={(e) => setT({ ...t, name: e.target.value })}
        />

        <Textarea
          label="Prompt (system)"
          value={t.prompt}
          onChange={(e) => setT({ ...t, prompt: e.target.value })}
          rows={20}
          className="font-mono"
        />

        <Card>
          <TrafficShareSlider
            value={t.traffic_share}
            onChange={(v) => setT({ ...t, traffic_share: v })}
            disabled={!t.active}
          />
          <label className="mt-4 flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={t.active}
              onChange={(e) => setT({ ...t, active: e.target.checked })}
              className="accent-accent"
            />
            Active
          </label>
        </Card>

        <div className="flex gap-3 pt-2">
          <Button onClick={save} loading={busy}>Save</Button>
          <Button onClick={runPreview} loading={busy} variant="secondary">
            Preview with Claude
          </Button>
        </div>
      </div>

      <Card>
        <div className="uppercase-label mb-3">Live preview</div>
        {preview ? (
          <p className="whitespace-pre-wrap text-sm text-text">{preview}</p>
        ) : (
          <p className="text-sm text-textMuted">
            Click &quot;Preview with Claude&quot; to render this prompt against a sample
            lead.
          </p>
        )}
      </Card>
    </div>
  );
}
