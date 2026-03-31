export type NodeRecord = {
  id: string;
  label: string;
  x: number;
  y: number;
};

export type EdgeRecord = {
  id: string;
  source: string;
  target: string;
  cost: number;
  blocked: boolean;
};

export type GraphPayload = {
  nodes: NodeRecord[];
  edges: EdgeRecord[];
};

export type CandidateRoute = {
  route: string[];
  total_cost: number | null;
  status: string;
  rejection_reason: string | null;
};

export type PlanResponse = {
  run_id: string;
  trace_id: string;
  status: string;
  route: string[];
  total_cost: number | null;
  candidates: CandidateRoute[];
  summary: string;
};

export type TraceStep = {
  step_index: number;
  step_type: string;
  name: string;
  summary: string;
  payload: Record<string, unknown>;
  highlights: Record<string, unknown>;
  latency_ms: number | null;
};

export type TracePayload = {
  trace_id: string;
  run_id: string;
  steps: TraceStep[];
};
