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

export interface BacktestTrade {
  decision_date: string;
  fill_date: string;
  symbol: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  reason: string;
}

export interface BacktestResult {
  total_return: number;
  win_rate: number;
  expectancy: number;
  n_trades: number;
  final_equity: number;
  equity_curve: { date: string; equity: number }[];
  trades: BacktestTrade[];
  max_drawdown: number;
  sharpe_ratio: number;
  avg_holding_days: number;
  tx_cost_ratio: number;
}

export interface FillRecord {
  id: number;
  symbol: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  sec_type: string;
  proposal_id: number | null;
  created_at: string;
}

export interface PnLPosition {
  symbol: string;
  quantity: number;
  avg_cost: number;
  market_price: number;
  market_value: number;
  unrealized_pnl: number;
}

export interface PnLRealized {
  symbol: string;
  quantity: number;
  buy_price: number;
  sell_price: number;
  cost: number;
  proceeds: number;
  pnl: number;
  buy_date: string;
  sell_date: string;
}

export interface PnLResponse {
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  positions: PnLPosition[];
  realized: PnLRealized[];
}

export interface TrackedProposal extends StoredProposal {
  current_price: number;
  hypothetical_return: number;
}

