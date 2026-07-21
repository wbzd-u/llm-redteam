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

export interface MechanismResearchRow {
  mechanism_id: string;
  name: string;
  category: string;
  summary: string;
  confidence: string;
  tags: string[];
  case_count: number;
  confirmed_cases: number;
  negative_cases: number;
  attempt_count: number;
  verified_evidence_count: number;
  relations: Counts;
  outcomes: Counts;
  applicability_signals: string[];
  negative_signals: string[];
  preconditions: string[];
  targets: Counts;
  carriers: Counts;
  languages: Counts;
  statuses: Counts;
}

export interface CrossTab {
  note: string;
  linked_records: number;
  mechanism_by_status: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
  mechanism_by_target: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
  mechanism_by_carrier: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
  mechanism_by_language: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
  mechanism_by_relation: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
  target_by_carrier: { columns: string[]; rows: Array<{ label: string; total: number; values: Counts }> };
}

export interface PaperPacket {
  summary: ResearchSummary;
  mechanism_matrix: MechanismResearchRow[];
  cross_tabs: CrossTab;
  data_dictionary: Array<{ field: string; meaning: string; unit: string }>;
  readiness: {
    total_cases: number;
    field_coverage: Record<string, { filled: number; total: number; rate: number }>;
    gaps: string[];
  };
  methods_draft: string;
  markdown: string;
}

export interface CaseDetail extends CaseRow {
  challenge: string;
  notes: string;
  intake: { authorization_scope?: string; success_criteria?: string[]; constraints?: string[] } | null;
  turns: Array<{ turn_id: string; role: string; content: string; provenance: string; refusal: boolean }>;
  evidence: Array<{ evidence_id: string; kind: string; description: string; verified: boolean; source: string }>;
  plans: Array<{ plan_id: string; planner: string; status: string; hypotheses?: PlanHypothesis[]; steps: PlanStep[] }>;
  campaigns: Array<{ campaign_id: string; target_kind: string; status: string; executed_turns: number; stop_reason: string }>;
}

export interface MechanismRecommendation {
  mechanism: {
    mechanism_id: string;
    name: string;
    category: string;
    summary: string;
    confidence: string;
    applicability_signals: string[];
    negative_signals: string[];
    preconditions: string[];
  };
  score: number;
  reasons: Array<{ kind: string; terms?: string[]; points?: number; count?: number }>;
  historical_relations: Counts;
}

export interface TaskWorkspace {
  task: CaseDetail;
  recommended_mechanisms: MechanismRecommendation[];
  hypothesis_matrix: { method: string; hypotheses: ResearchHypothesis[] };
  next_action: { action: string; mechanism: string; rationale: string; confidence: string; requires_human_review: boolean; stage: string };
  suggested_plan: { plan_id: string; hypotheses: PlanHypothesis[]; steps: PlanStep[]; notes: string } | null;
}

export interface ResearchHypothesis extends PlanHypothesis {
  mechanism_id: string;
  mechanism: string;
  variables: Record<string, string>;
  preconditions: string[];
  historical_support: { relation_counts: Counts; samples: Array<{ case_id: string; title: string; relation: string; status: string }> };
  stop_condition: string;
  next_if_negative: string;
}

export interface PlanHypothesis {
  id: string;
  statement: string;
  basis: string;
  priority: string;
  positive_signal: string;
  negative_signal: string;
}

export interface PlanStep {
  id: string;
  hypothesis_id: string;
  objective: string;
  variables: Record<string, string>;
  expected_signal: string;
  stop_condition: string;
  approval_required: boolean;
}
