"""提案 / 成交的資料存取，與 DB 細節隔離。"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from app.schemas import Proposal, ProposalDecision, StoredProposal


def save_proposal(conn: sqlite3.Connection, p: Proposal) -> int:
    cur = conn.execute(
        """INSERT INTO proposals
           (symbol, action, price, quantity, confidence, reason, risk_note, stop_loss, take_profit)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            p.symbol, p.action.value, p.price, p.quantity, p.confidence,
            p.reason, p.risk_note, p.stop_loss, p.take_profit,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_proposals(
    conn: sqlite3.Connection, decision: Optional[ProposalDecision] = None
) -> List[StoredProposal]:
    sql = "SELECT * FROM proposals"
    params: tuple = ()
    if decision is not None:
        sql += " WHERE decision = ?"
        params = (decision.value,)
    sql += " ORDER BY created_at DESC, id DESC"
    return [_row_to_proposal(r) for r in conn.execute(sql, params).fetchall()]


def set_decision(
    conn: sqlite3.Connection, proposal_id: int, decision: ProposalDecision
) -> bool:
    cur = conn.execute(
        "UPDATE proposals SET decision = ? WHERE id = ?",
        (decision.value, proposal_id),
    )
    conn.commit()
    return cur.rowcount > 0


def _row_to_proposal(r: sqlite3.Row) -> StoredProposal:
    return StoredProposal(
        id=r["id"],
        symbol=r["symbol"],
        action=r["action"],
        price=r["price"],
        quantity=r["quantity"],
        confidence=r["confidence"],
        reason=r["reason"],
        risk_note=r["risk_note"],
        stop_loss=r["stop_loss"],
        take_profit=r["take_profit"],
        decision=ProposalDecision(r["decision"]),
        created_at=r["created_at"],
    )


# --- Fills (Manual Trades) ---

def save_fill(
    conn: sqlite3.Connection,
    symbol: str,
    side: str,
    price: float,
    quantity: int,
    sec_type: str = "stock",
    proposal_id: Optional[int] = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO fills (symbol, side, price, quantity, sec_type, proposal_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (symbol, side, price, quantity, sec_type, proposal_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_fills(conn: sqlite3.Connection) -> List[dict]:
    cur = conn.execute("SELECT * FROM fills ORDER BY created_at DESC, id DESC")
    return [dict(r) for r in cur.fetchall()]


# --- Security Metadata ---

def get_security_metadata(conn: sqlite3.Connection, symbol: str) -> Optional[dict]:
    cur = conn.execute("SELECT * FROM security_metadata WHERE symbol = ?", (symbol,))
    row = cur.fetchone()
    return dict(row) if row else None


def list_securities(conn: sqlite3.Connection) -> List[dict]:
    cur = conn.execute("SELECT * FROM security_metadata ORDER BY symbol")
    return [dict(r) for r in cur.fetchall()]


def save_security(
    conn: sqlite3.Connection,
    symbol: str,
    name: str,
    market_type: str,
    sec_type: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO security_metadata (symbol, name, market_type, sec_type)
           VALUES (?, ?, ?, ?)""",
        (symbol, name, market_type, sec_type),
    )
    conn.commit()


# --- Token Usage Tracking ---

def log_token_usage(
    conn: sqlite3.Connection,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    conn.execute(
        """INSERT INTO token_usage (model, prompt_tokens, completion_tokens)
           VALUES (?, ?, ?)""",
        (model, prompt_tokens, completion_tokens),
    )
    conn.commit()


def get_total_token_usage(conn: sqlite3.Connection) -> dict:
    cur = conn.execute(
        """SELECT
             COUNT(*) as total_calls,
             SUM(prompt_tokens) as total_prompt_tokens,
             SUM(completion_tokens) as total_completion_tokens
           FROM token_usage"""
    )
    row = cur.fetchone()
    return {
        "calls": row["total_calls"] or 0,
        "prompt_tokens": row["total_prompt_tokens"] or 0,
        "completion_tokens": row["total_completion_tokens"] or 0,
    }


# --- Backtest Caching ---

def get_backtest_cache(conn: sqlite3.Connection, context_hash: str) -> Optional[str]:
    cur = conn.execute("SELECT response_json FROM backtest_cache WHERE context_hash = ?", (context_hash,))
    row = cur.fetchone()
    return row["response_json"] if row else None


def save_backtest_cache(conn: sqlite3.Connection, context_hash: str, response_json: str) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO backtest_cache (context_hash, response_json)
           VALUES (?, ?)""",
        (context_hash, response_json),
    )
    conn.commit()


# --- Rejected Proposal Tracking ---

def list_rejected_proposals(conn: sqlite3.Connection) -> List[StoredProposal]:
    return list_proposals(conn, ProposalDecision.REJECTED)

