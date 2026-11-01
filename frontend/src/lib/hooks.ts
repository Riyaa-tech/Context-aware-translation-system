import { useEffect, useState } from "react";
import { api } from "./api";

/** Fetch JSON; keeps the previous data while refetching (no layout jump). */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true); setError(null);
    api<T>(path).then((d) => live && setData(d)).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [path]);
  return { data, error, loading };
}

export interface RunSummary { experiment_id: string; name: string; status: string; split: string; reportable: boolean;
  created_at: string; finished_at: string | null; n_examples: number; directions: string[]; conditions: Record<string, string> }
export interface Batch { batch_id: string; experiment_id: string; n_items: number; raters: Record<string, number>; conditions: string[] }
