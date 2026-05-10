import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { TemplateEditor } from "@/components/TemplateEditor";
import type { Template } from "@/lib/types";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function TemplateDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const all = await api<Template[]>("/api/templates");
  const t = all.find((x) => x.id === Number(id));
  if (!t) notFound();

  return (
    <>
      <PageHeader
        title={`Edit: ${t.name}`}
        action={
          <Link href="/templates" className="text-sm text-textMuted hover:text-text">
            ← All templates
          </Link>
        }
      />
      <TemplateEditor initial={t} />
    </>
  );
}
