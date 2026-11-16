async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(url, init); } catch {
    throw new Error("Cannot reach the backend. Start it with scripts\\start_windows.ps1 and reload.");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail
      : Array.isArray(j.detail) ? j.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ") : msg; } catch { /* keep default */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

import type { Dashboard, Investigation, InvestigationDetail, RecordRow, SearchResponse, SourceFile, StructuredQuery } from "./types";

export const api = {
  dashboard: () => req<Dashboard>("/api/dashboard"),
  investigations: (q = "") => req<Investigation[]>(`/api/investigations?q=${encodeURIComponent(q)}`),
  investigation: (id: number) => req<InvestigationDetail>(`/api/investigations/${id}`),
  createInvestigation: (b: Partial<Investigation> & { title: string }) => req<Investigation>("/api/investigations", json(b)),
  records: (fileId: number, offset: number, status?: string) =>
    req<{ total: number; records: RecordRow[]; file: SourceFile }>(`/api/files/${fileId}/records?offset=${offset}&limit=25${status ? `&status=${status}` : ""}`),
  importFile: (form: FormData) => req<SourceFile>("/api/ingestion/import", { method: "POST", body: form }),
  loadSynthetic: () => req<{ created: boolean }>("/api/demo/synthetic", { method: "POST" }),
  variables: () => req<{ measurements: { key: string; label: string }[]; targets: { key: string; label: string }[] }>("/api/variables"),
  parse: (text: string) => req<StructuredQuery>("/api/questions/parse", json({ text })),
  search: (q: StructuredQuery) => req<SearchResponse>("/api/evidence/search", json(q)),
  question: (id: number) => req<SearchResponse>(`/api/questions/${id}`),
  report: (id: number) => req<Record<string, unknown>>(`/api/reports/${id}`),
  methodology: () => req<Record<string, unknown>>("/api/methodology"),
};
