import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import type { Template } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function TemplatesPage() {
  const templates = await api<Template[]>("/api/templates");

  return (
    <>
      <PageHeader
        title="Templates"
        subtitle={`${templates.length} drafter prompts`}
        action={
          <Link href="/templates">
            <Button variant="primary" size="sm">+ New template</Button>
          </Link>
        }
      />

      <div className="grid gap-3">
        {templates.map((t) => (
          <Link key={t.id} href={`/templates/${t.id}`}>
            <Card className="transition-colors hover:border-borderHi">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base font-semibold tracking-tight">{t.name}</h3>
                    <Badge>{t.variant}</Badge>
                    {t.is_winner && <Badge tone="accent">🏆 Winner</Badge>}
                    {!t.active && <Badge>paused</Badge>}
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm text-textMuted shrink-0">
                  <div className="text-right">
                    <div className="uppercase-label">Share</div>
                    <div className="text-text tabular-nums">{t.traffic_share}%</div>
                  </div>
                  <div className="text-right">
                    <div className="uppercase-label">Sent</div>
                    <div className="text-text tabular-nums">{t.sent_count}</div>
                  </div>
                  <div className="text-right">
                    <div className="uppercase-label">Replies</div>
                    <div className="text-text tabular-nums">{t.reply_count}</div>
                  </div>
                  <div className="text-right">
                    <div className="uppercase-label">Conv.</div>
                    <div className="text-text tabular-nums">
                      {(t.conversion_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
