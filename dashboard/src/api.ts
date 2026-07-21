import type { CaseDetail, CaseRow, CreatedCampaign, ExecutionArtifacts, Overview, PaperPacket, PyRITProfile, PyRITReadiness, ReplayCampaignResult, ResearchSummary, TaskWorkspace } from "./types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8787";
const sourceQuery = (source: string) => source === "all" ? "" : `?source=${encodeURIComponent(source)}`;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

export const api = {
  overview: (source = "user-kb") => get<Overview>(`/api/overview${sourceQuery(source)}`),
  cases: (source = "user-kb") => get<CaseRow[]>(`/api/cases${sourceQuery(source)}`),
  caseDetail: (caseId: string) => get<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`),
  research: (source = "user-kb") => get<ResearchSummary>(`/api/research/summary${sourceQuery(source)}`),
  paperPacket: (source = "user-kb") => get<PaperPacket>(`/api/research/paper-packet${sourceQuery(source)}`),
  taskWorkspace: (caseId: string) => get<TaskWorkspace>(`/api/tasks/${encodeURIComponent(caseId)}/workspace`),
  createTask: (payload: unknown) => post<{ case_id: string }>("/api/tasks", payload),
  createTaskDraft: (caseId: string) => post(`/api/tasks/${encodeURIComponent(caseId)}/plan/draft`, {}),
  savePyritProfile: (caseId: string, profile: Partial<PyRITProfile>) => post<PyRITReadiness>(`/api/tasks/${encodeURIComponent(caseId)}/pyrit-profile`, profile),
  approveTaskPlan: (caseId: string, planId: string) => post(`/api/tasks/${encodeURIComponent(caseId)}/plans/${encodeURIComponent(planId)}/approve`, {}),
  executionArtifacts: (caseId: string, planId: string) => get<ExecutionArtifacts>(`/api/tasks/${encodeURIComponent(caseId)}/plans/${encodeURIComponent(planId)}/artifacts`),
  createTaskCampaign: (caseId: string, planId: string, payload: unknown) => post<CreatedCampaign>(`/api/tasks/${encodeURIComponent(caseId)}/plans/${encodeURIComponent(planId)}/campaigns`, payload),
  runTaskReplayCampaign: (caseId: string, campaignId: string, responseText: string) => post<ReplayCampaignResult>(`/api/tasks/${encodeURIComponent(caseId)}/campaigns/${encodeURIComponent(campaignId)}/replay`, { response_text: responseText }),
  addObservation: (caseId: string, payload: unknown) => post(`/api/tasks/${encodeURIComponent(caseId)}/observation`, payload),
};
