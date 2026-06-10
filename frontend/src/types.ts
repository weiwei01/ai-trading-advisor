export type Action = "buy" | "sell" | "hold";
export type ProposalDecision = "pending" | "approved" | "rejected";

export interface StoredProposal {
  id: number;
  symbol: string;
  action: Action;
  price: number;
  quantity: number;
  confidence: number;
  reason: string;
  risk_note: string;
  stop_loss: number | null;
  take_profit: number | null;
  decision: ProposalDecision;
  created_at: string;
}

export interface BacktestResult {
  total_return: number;
  win_rate: number;
  expectancy: number;
  n_trades: number;
  final_equity: number;
  equity_curve: { date: string; equity: number }[];
}
