export type Counts = Record<string, number>;

export interface ResearchSummary {
  totals: {
    cases: number;
    attempts: number;
    campaigns: number;
    confirmed_cases: number;
    confirmed_case_rate: number;
    historical_confirmed_cases: number;
    historical_confirmed_rate: number;
    user_kb_cases: number;
    reproduced_cases: number;
    reproduced_case_rate: number;
    observed_cost: number;
  };
  cases_by_target: Counts;
  cases_by_carrier: Counts;
  cases_by_language: Counts;
  cases_by_source: Counts;
  cases_by_stage: Counts;
  attempts_by_outcome: Counts;
  campaigns_by_status: Counts;
  mechanism_links_by_relation: Counts;
}

export interface CaseRow {
  case_id: string;
  title: string;
  target: string;
  carrier: string;
  mechanism: string;
  status: string;
  stage: string;
  language: string;
  source: string;
  tags: string[];
  attempt_count: number;
  turn_count: number;
  evidence_count: number;
  verified_evidence_count: number;
  plan_count: number;
  campaign_count: number;
  campaign_turns: number;
  observed_cost: number;
  confirmed: boolean;
  reproduced: boolean;
  attempt_outcomes: string[];
  campaign_statuses: string[];
  mechanism_relations: string[];
}

export interface Overview {
  summary: ResearchSummary;
  recent_cases: CaseRow[];
}

export interface CaseDetail extends CaseRow {
  challenge: string;
  notes: string;
  intake: { authorization_scope?: string; success_criteria?: string[]; constraints?: string[] } | null;
  turns: Array<{ turn_id: string; role: string; content: string; provenance: string; refusal: boolean }>;
  evidence: Array<{ evidence_id: string; kind: string; description: string; verified: boolean; source: string }>;
  plans: Array<{ plan_id: string; planner: string; status: string; steps: unknown[] }>;
  campaigns: Array<{ campaign_id: string; target_kind: string; status: string; executed_turns: number; stop_reason: string }>;
}
