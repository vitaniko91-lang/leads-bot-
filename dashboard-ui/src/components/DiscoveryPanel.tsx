"use client";

import { useEffect, useState } from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { clientApi } from "@/hooks/useApi";
import type { DiscoveryCandidate } from "@/lib/types";

export function DiscoveryPanel() {
  const [items, setItems] = useState<DiscoveryCandidate[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await clientApi<DiscoveryCandidate[]>(
        "/api/discovery/pending?limit=20",
      );
      setItems(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(id: number, action: "approve" | "reject") {
    await clientApi(`/api/discovery/${id}/${action}`, { method: "POST" });
    setItems((prev) => prev.filter((c) => c.id !== id));
  }

  if (loading) return <p className="text-textMuted">Loading discovery…</p>;
  if (items.length === 0)
    return (
      <p className="text-textMuted">
        No pending channels. New ones appear weekly (Wed scan).
      </p>
    );

  return (
    <div className="space-y-2">
      {items.map((c) => (
        <Card key={c.id} className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h4 className="truncate text-text font-medium">{c.title}</h4>
              <span className="text-xs text-textDim">
                {c.predicted_region} · {c.language} · {c.member_count} members
              </span>
            </div>
            {c.description && (
              <p className="mt-1 line-clamp-2 text-sm text-textMuted">
                {c.description}
              </p>
            )}
            <p className="mt-1 text-xs text-textDim">query: {c.matched_query}</p>
          </div>
          <div className="ml-4 flex gap-2 shrink-0">
            <Button size="sm" onClick={() => act(c.id, "approve")}>Add</Button>
            <Button size="sm" variant="ghost" onClick={() => act(c.id, "reject")}>
              Reject
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
