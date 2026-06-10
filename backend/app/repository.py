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
