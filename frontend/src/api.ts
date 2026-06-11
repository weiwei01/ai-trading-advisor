import type { BacktestResult, ProposalDecision, StoredProposal } from "./types";

const BASE = "/api";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export function listProposals(decision?: ProposalDecision): Promise<StoredProposal[]> {
  const q = decision ? `?decision=${decision}` : "";
  return fetch(`${BASE}/proposals${q}`).then((r) => json<StoredProposal[]>(r));
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
