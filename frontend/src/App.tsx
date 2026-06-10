import { useEffect, useState } from "react";
import { decideProposal, listProposals } from "./api";
import type { StoredProposal } from "./types";

export default function App() {
  const [proposals, setProposals] = useState<StoredProposal[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setProposals(await listProposals("pending"));
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function decide(id: number, decision: "approved" | "rejected") {
    await decideProposal(id, decision);
    refresh();
  }

  return (
    <main style={{ maxWidth: 880, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <header>
        <h1 style={{ marginBottom: 4 }}>AI Trading Advisor</h1>
        <p style={{ color: "#666", marginTop: 0 }}>
          決策輔助系統 · <strong>系統不會自動送單</strong>，是否進場由你決定。
        </p>
      </header>

      {error && <p style={{ color: "crimson" }}>讀取失敗：{error}</p>}

      <h2>待裁決提案</h2>
      {proposals.length === 0 && <p style={{ color: "#888" }}>目前沒有待裁決的提案。</p>}

      <div style={{ display: "grid", gap: 12 }}>
        {proposals.map((p) => (
          <article
            key={p.id}
            style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong>
                {p.symbol} · {p.action.toUpperCase()} {p.quantity} 股 @ {p.price}
              </strong>
              <span>信心 {(p.confidence * 100).toFixed(0)}%</span>
            </div>
            <p style={{ margin: "8px 0 4px" }}>
              <strong>理由：</strong>
              {p.reason}
            </p>
            <p style={{ margin: "0 0 12px", color: "#a15" }}>
              <strong>風險：</strong>
              {p.risk_note}
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => decide(p.id, "approved")}>核准（我自己去下單）</button>
              <button onClick={() => decide(p.id, "rejected")}>婉拒</button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
