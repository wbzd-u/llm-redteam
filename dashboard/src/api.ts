import type { CaseDetail, CaseRow, Overview, ResearchSummary } from "./types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8787";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => get<Overview>("/api/overview"),
  cases: () => get<CaseRow[]>("/api/cases"),
  caseDetail: (caseId: string) => get<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`),
  research: () => get<ResearchSummary>("/api/research/summary"),
};
