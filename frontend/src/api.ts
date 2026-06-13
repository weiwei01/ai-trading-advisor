import type {
  BacktestResult,
  ProposalDecision,
  StoredProposal,
  FillRecord,
  PnLResponse,
  TrackedProposal,
} from "./types";

const BASE = "/api";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export function listProposals(decision?: ProposalDecision): Promise<StoredProposal[]> {
  const q = decision ? `?decision=${decision}` : "";
  return fetch(`${BASE}/proposals${q}`).then((r) => json<StoredProposal[]>(r));
}

export interface GenerateFromDbResult {
  saved_ids: number[];
  blocked: { symbol: string; reasons: string[] }[];
  as_of: string;
  advisor: string;
  n_proposed: number;
}

export function generateProposalsFromDb(payload: {
  advisor?: "rules" | "codex" | "stub";
  strategy_style?: string;
  as_of?: string;
}): Promise<GenerateFromDbResult> {
  return fetch(`${BASE}/proposals/generate-from-db`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<GenerateFromDbResult>(r));
}

export function decideProposal(
  id: number,
  decision: ProposalDecision,
): Promise<StoredProposal> {
  return fetch(`${BASE}/proposals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  }).then((r) => json<StoredProposal>(r));
}

export function runBacktest(payload: {
  candles: Record<string, unknown[]>;
  days?: number;
  initial_cash?: number;
  strategy_style?: string;
}): Promise<BacktestResult> {
  return fetch(`${BASE}/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<BacktestResult>(r));
}

export function listStoredSymbols(): Promise<string[]> {
  return fetch(`${BASE}/backtest/symbols`).then((r) => json<string[]>(r));
}

export function runStoredBacktest(payload: {
  symbols?: string[];
  days?: number;
  initial_cash?: number;
  strategy_style?: string;
  etf_symbols?: string[];
}): Promise<BacktestResult> {
  return fetch(`${BASE}/backtest/run-stored`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<BacktestResult>(r));
}

export function addManualFill(payload: {
  symbol: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  sec_type: "stock" | "etf";
}): Promise<{ id: number; status: string }> {
  return fetch(`${BASE}/portfolio/fills`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => json<{ id: number; status: string }>(r));
}

export function listFills(): Promise<FillRecord[]> {
  return fetch(`${BASE}/portfolio/fills`).then((r) => json<FillRecord[]>(r));
}

export function getStoredPnL(): Promise<PnLResponse> {
  return fetch(`${BASE}/portfolio/pnl`).then((r) => json<PnLResponse>(r));
}

export function listProposalsTracking(): Promise<TrackedProposal[]> {
  return fetch(`${BASE}/proposals/tracking`).then((r) => json<TrackedProposal[]>(r));
}
