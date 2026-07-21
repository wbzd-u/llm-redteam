import type { CaseDetail, CaseRow, Overview, PaperPacket, ResearchSummary } from "./types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8787";
const sourceQuery = (source: string) => source === "all" ? "" : `?source=${encodeURIComponent(source)}`;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

export const api = {
  overview: (source = "user-kb") => get<Overview>(`/api/overview${sourceQuery(source)}`),
  cases: (source = "user-kb") => get<CaseRow[]>(`/api/cases${sourceQuery(source)}`),
  caseDetail: (caseId: string) => get<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`),
  research: (source = "user-kb") => get<ResearchSummary>(`/api/research/summary${sourceQuery(source)}`),
  paperPacket: (source = "user-kb") => get<PaperPacket>(`/api/research/paper-packet${sourceQuery(source)}`),
};
