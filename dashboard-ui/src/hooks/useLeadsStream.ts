"use client";
import { useEffect } from "react";

type Evt = {
  id: number;
  source_id: number;
  status: string;
  raw_text?: string;
  relevance_score?: number;
};

export function useLeadsStream(handler: (evt: Evt) => void) {
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
    const es = new EventSource(`${base}/api/stream/leads`);

    function onNew(e: MessageEvent) {
      try {
        const data = JSON.parse(e.data) as Evt;
        handler(data);
      } catch {
        /* ignore malformed */
      }
    }
    es.addEventListener("new_lead", onNew);
    return () => {
      es.removeEventListener("new_lead", onNew);
      es.close();
    };
  }, [handler]);
}
