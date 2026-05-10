"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Select } from "./Select";
import { Input } from "./Input";

const STATUSES = [
  { value: "", label: "All" },
  { value: "new", label: "New" },
  { value: "drafted", label: "Drafted" },
  { value: "approved", label: "Approved" },
  { value: "sent", label: "Sent" },
  { value: "skipped", label: "Skipped" },
  { value: "filtered_out", label: "Filtered out" },
];

export function LeadFiltersBar() {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(Array.from(params.entries()));
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/leads?${next.toString()}`);
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <Select
        label="Status"
        value={params.get("status") ?? ""}
        onChange={(e) => update("status", e.target.value)}
        options={STATUSES}
      />
      <Input
        label="Min score"
        type="number"
        min={0}
        max={100}
        defaultValue={params.get("min_score") ?? ""}
        onBlur={(e) => update("min_score", e.target.value)}
      />
      <Input
        label="Language"
        placeholder="en, ru, uk"
        defaultValue={params.get("language") ?? ""}
        onBlur={(e) => update("language", e.target.value)}
      />
      <Input
        label="Region"
        placeholder="ua, eu, en_global"
        defaultValue={params.get("region") ?? ""}
        onBlur={(e) => update("region", e.target.value)}
      />
    </div>
  );
}
