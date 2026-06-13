import { useEffect, useState } from "react";
import {
  decideProposal,
  listProposals,
  generateProposalsFromDb,
  addManualFill,
  getStoredPnL,
  listFills,
  listProposalsTracking,
} from "./api";
import BacktestPanel from "./BacktestPanel";
import type { StoredProposal, FillRecord, PnLResponse, TrackedProposal } from "./types";

type Tab = "proposals" | "tracking" | "portfolio" | "fills" | "backtest";

export default function App() {
  const [tab, setTab] = useState<Tab>("proposals");
  const [proposals, setProposals] = useState<StoredProposal[]>([]);
  const [trackedProposals, setTrackedProposals] = useState<TrackedProposal[]>([]);
  const [pnl, setPnl] = useState<PnLResponse | null>(null);
  const [fills, setFills] = useState<FillRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Fill Form State
  const [fillSymbol, setFillSymbol] = useState("");
  const [fillSide, setFillSide] = useState<"buy" | "sell">("buy");
  const [fillPrice, setFillPrice] = useState("");
  const [fillQty, setFillQty] = useState("");
  const [fillSecType, setFillSecType] = useState<"stock" | "etf">("stock");
  const [submittingFill, setSubmittingFill] = useState(false);

  // 產生提案表單
  const [genAdvisor, setGenAdvisor] = useState<"rules" | "codex">("rules");
  const [genStrategy, setGenStrategy] = useState("穩健波段");
  const [genDate, setGenDate] = useState("");
  const [generating, setGenerating] = useState(false);

  async function refresh() {
    try {
      setError(null);
      if (tab === "proposals") {
        setProposals(await listProposals("pending"));
      } else if (tab === "tracking") {
        setTrackedProposals(await listProposalsTracking());
      } else if (tab === "portfolio") {
        setPnl(await getStoredPnL());
      } else if (tab === "fills") {
        setFills(await listFills());
      }
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, [tab]);

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const r = await generateProposalsFromDb({
        advisor: genAdvisor,
        strategy_style: genStrategy,
        as_of: genDate || undefined,
      });
      const blocked = r.blocked.length;
      const src = r.positions_source.startsWith("obsidian:")
        ? `持股讀自 Obsidian（${r.n_positions} 檔）`
        : `持股由成交紀錄推算（${r.n_positions} 檔）`;
      const cashSrc = r.cash_source.startsWith("obsidian:")
        ? `可用現金讀自 Obsidian ${r.cash.toLocaleString()}`
        : `可用現金 ${r.cash.toLocaleString()}（預設值）`;
      setSuccessMsg(
        `${r.advisor} 於 ${r.as_of} 產出 ${r.n_proposed} 筆，` +
          `入庫 ${r.saved_ids.length} 筆${blocked ? `，風控擋下 ${blocked} 筆` : ""}。${src}；${cashSrc}`,
      );
      setTimeout(() => setSuccessMsg(null), 7000);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function decide(id: number, decision: "approved" | "rejected") {
    try {
      await decideProposal(id, decision);
      setSuccessMsg(`提案 ID ${id} 已標記為 ${decision === "approved" ? "已核准" : "已婉拒"}`);
      setTimeout(() => setSuccessMsg(null), 3000);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleAddFill(e: React.FormEvent) {
    e.preventDefault();
    if (!fillSymbol || !fillPrice || !fillQty) {
      setError("所有欄位皆為必填！");
      return;
    }
    setSubmittingFill(true);
    setError(null);
    try {
      await addManualFill({
        symbol: fillSymbol.trim(),
        side: fillSide,
        price: parseFloat(fillPrice),
        quantity: parseInt(fillQty, 10),
        sec_type: fillSecType,
      });
      setSuccessMsg("交易紀錄申報成功！");
      setTimeout(() => setSuccessMsg(null), 3000);
      
      // Reset form
      setFillSymbol("");
      setFillPrice("");
      setFillQty("");
      
      // Refresh current tab
      if (tab === "portfolio" || tab === "fills") {
        refresh();
      } else {
        setTab("portfolio");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmittingFill(false);
    }
  }

  return (
    <div style={containerStyle}>
      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "32px 16px" }}>
        {/* Header Section */}
        <header style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={pulseDotStyle} />
            <h1 style={titleStyle}>AI Trading Advisor</h1>
          </div>
          <p style={subtitleStyle}>
            台股 AI 決策輔助系統 <span style={badgeStyle}>僅供參考 · 系統不送單</span>
          </p>
        </header>

        {/* Tab Navigation */}
        <nav style={navStyle}>
          {(["proposals", "tracking", "portfolio", "fills", "backtest"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={tab === t ? activeTabButtonStyle : tabButtonStyle}
            >
              {t === "proposals" && "待決提案"}
              {t === "tracking" && "提案追蹤"}
              {t === "portfolio" && "投組與部位"}
              {t === "fills" && "歷史帳簿"}
              {t === "backtest" && "回測除錯"}
            </button>
          ))}
        </nav>

        {/* Alerts & Messages */}
        {error && <div style={errorBannerStyle}>⚠️ {error}</div>}
        {successMsg && <div style={successBannerStyle}>✨ {successMsg}</div>}

        {/* Tab Content Panels */}
        <div style={panelContainerStyle}>
          {tab === "proposals" && (
            <section>
              <h2 style={sectionTitleStyle}>待裁決交易提案</h2>
              <p style={sectionDescStyle}>
                由 AI 顧問產出並已通過風控引擎驗證的進出場提案。系統不會自動下單，請手動確認。
              </p>

              <div style={generateBarStyle}>
                <strong style={{ fontSize: 14 }}>產生提案</strong>
                <select
                  value={genAdvisor}
                  onChange={(e) => setGenAdvisor(e.target.value as "rules" | "codex")}
                  style={genInputStyle}
                >
                  <option value="rules">規則型（不燒 Token）</option>
                  <option value="codex">Codex 真實 AI（燒 Token）</option>
                </select>
                <input
                  type="text"
                  value={genStrategy}
                  onChange={(e) => setGenStrategy(e.target.value)}
                  placeholder="策略風格"
                  style={{ ...genInputStyle, width: 120 }}
                />
                <input
                  type="text"
                  value={genDate}
                  onChange={(e) => setGenDate(e.target.value)}
                  placeholder="基準日 YYYY-MM-DD（留空=最新）"
                  style={{ ...genInputStyle, width: 220 }}
                />
                <button onClick={generate} disabled={generating} style={approveButtonStyle}>
                  {generating ? "產生中…" : "產生提案"}
                </button>
              </div>

              {proposals.length === 0 ? (
                <div style={emptyStateStyle}>目前沒有待裁決的提案。</div>
              ) : (
                <div style={{ display: "grid", gap: 16 }}>
                  {proposals.map((p) => (
                    <article key={p.id} style={cardStyle}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <span style={p.action === "buy" ? buyTagStyle : sellTagStyle}>
                          {p.action === "buy" ? "買進 BUY" : "賣出 SELL"}
                        </span>
                        <div style={{ textAlign: "right" }}>
                          <span style={symbolStyle}>{p.symbol}</span>
                          <div style={confidenceStyle}>信心指數: {(p.confidence * 100).toFixed(0)}%</div>
                        </div>
                      </div>

                      <div style={proposalGridStyle}>
                        <div>
                          <div style={fieldLabelStyle}>建議價格</div>
                          <div style={fieldValueStyle}>{p.price} 元</div>
                        </div>
                        <div>
                          <div style={fieldLabelStyle}>建議數量</div>
                          <div style={fieldValueStyle}>{p.quantity} 股</div>
                        </div>
                        <div>
                          <div style={fieldLabelStyle}>預估總值</div>
                          <div style={fieldValueStyle}>{(p.price * p.quantity).toLocaleString()} 元</div>
                        </div>
                        {p.stop_loss && (
                          <div>
                            <div style={fieldLabelStyle}>設定停損</div>
                            <div style={{ ...fieldValueStyle, color: "#f43f5e" }}>{p.stop_loss} 元</div>
                          </div>
                        )}
                      </div>

                      <div style={detailBlockStyle}>
                        <strong>進場理由：</strong> {p.reason}
                      </div>
                      <div style={{ ...detailBlockStyle, borderLeft: "3px solid #e11d48", color: "#fda4af" }}>
                        <strong>風控警示：</strong> {p.risk_note}
                      </div>

                      <div style={actionButtonGroupStyle}>
                        <button onClick={() => decide(p.id, "approved")} style={approveButtonStyle}>
                          核准（我自己去券商下單）
                        </button>
                        <button onClick={() => decide(p.id, "rejected")} style={rejectButtonStyle}>
                          婉拒此提案
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === "tracking" && (
            <section>
              <h2 style={sectionTitleStyle}>決策追蹤與績效對照</h2>
              <p style={sectionDescStyle}>
                追蹤所有歷史提案的事後走勢，包含已婉拒提案，用以檢驗裁決品質。
              </p>
              {trackedProposals.length === 0 ? (
                <div style={emptyStateStyle}>暫無歷史提案紀錄。</div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={tableStyle}>
                    <thead>
                      <tr style={tableHeaderRowStyle}>
                        <th style={thStyle}>時間</th>
                        <th style={thStyle}>標的</th>
                        <th style={thStyle}>方向</th>
                        <th style={thStyle}>提案價</th>
                        <th style={thStyle}>現價</th>
                        <th style={thStyle}>決策</th>
                        <th style={thStyle}>虛擬損益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trackedProposals.map((p) => {
                        const isUp = p.hypothetical_return >= 0;
                        const returnColor = isUp ? "#ef4444" : "#10b981"; // 台灣紅漲綠跌
                        return (
                          <tr key={p.id} style={tableRowStyle}>
                            <td style={tdStyle}>{p.created_at.substring(5, 16)}</td>
                            <td style={tdStyle}>{p.symbol}</td>
                            <td style={tdStyle}>
                              <span style={p.action === "buy" ? buyTextStyle : sellTextStyle}>
                                {p.action === "buy" ? "買進" : "賣出"}
                              </span>
                            </td>
                            <td style={tdStyle}>{p.price}</td>
                            <td style={tdStyle}>{p.current_price || "—"}</td>
                            <td style={tdStyle}>
                              <span style={p.decision === "approved" ? approvedTagStyle : p.decision === "rejected" ? rejectedTagStyle : pendingTagStyle}>
                                {p.decision === "approved" ? "已核准" : p.decision === "rejected" ? "已婉拒" : "待決定"}
                              </span>
                            </td>
                            <td style={{ ...tdStyle, color: returnColor, fontWeight: "bold" }}>
                              {p.hypothetical_return !== 0 ? `${isUp ? "+" : ""}${(p.hypothetical_return * 100).toFixed(2)}%` : "0.00%"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {tab === "portfolio" && (
            <section style={{ display: "grid", gap: 24, gridTemplateColumns: "1fr", "@media (min-width: 768px)": { gridTemplateColumns: "2fr 1fr" } } as any}>
              <div style={{ display: "grid", gap: 24 }}>
                {/* PnL Stats Cards */}
                {pnl && (
                  <div style={pnlGridStyle}>
                    <div style={statCardStyle}>
                      <div style={statLabelStyle}>已實現損益</div>
                      <div style={{ ...statValueStyle, color: pnl.realized_pnl >= 0 ? "#ef4444" : "#10b981" }}>
                        {pnl.realized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元
                      </div>
                    </div>
                    <div style={statCardStyle}>
                      <div style={statLabelStyle}>未實現損益</div>
                      <div style={{ ...statValueStyle, color: pnl.unrealized_pnl >= 0 ? "#ef4444" : "#10b981" }}>
                        {pnl.unrealized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元
                      </div>
                    </div>
                    <div style={statCardStyle}>
                      <div style={statLabelStyle}>累積總損益</div>
                      <div style={{ ...statValueStyle, color: pnl.total_pnl >= 0 ? "#ef4444" : "#10b981" }}>
                        {pnl.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} 元
                      </div>
                    </div>
                  </div>
                )}

                {/* Open Positions */}
                <div style={cardStyle}>
                  <h3 style={{ ...sectionTitleStyle, fontSize: 18, marginTop: 0 }}>當前持有部位</h3>
                  {!pnl || pnl.positions.length === 0 ? (
                    <div style={emptyStateStyle}>目前無持有部位。</div>
                  ) : (
                    <div style={{ overflowX: "auto" }}>
                      <table style={tableStyle}>
                        <thead>
                          <tr style={tableHeaderRowStyle}>
                            <th style={thStyle}>代號</th>
                            <th style={thStyle}>持股數</th>
                            <th style={thStyle}>平均成本</th>
                            <th style={thStyle}>當前價格</th>
                            <th style={thStyle}>市值</th>
                            <th style={thStyle}>未實現損益</th>
                          </tr>
                        </thead>
                        <tbody>
                          {pnl.positions.map((pos) => {
                            const isProfit = pos.unrealized_pnl >= 0;
                            return (
                              <tr key={pos.symbol} style={tableRowStyle}>
                                <td style={{ ...tdStyle, fontWeight: "bold" }}>{pos.symbol}</td>
                                <td style={tdStyle}>{pos.quantity.toLocaleString()}</td>
                                <td style={tdStyle}>{pos.avg_cost.toFixed(2)}</td>
                                <td style={tdStyle}>{pos.market_price}</td>
                                <td style={tdStyle}>{pos.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                <td style={{ ...tdStyle, color: isProfit ? "#ef4444" : "#10b981", fontWeight: "bold" }}>
                                  {isProfit ? "+" : ""}{pos.unrealized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>

              {/* Manual Fill Reporting Form */}
              <div style={cardStyle}>
                <h3 style={{ ...sectionTitleStyle, fontSize: 18, marginTop: 0 }}>手動成交回報</h3>
                <p style={sectionDescStyle}>請在券商端實際成交後，將成交價格與股數回填系統，以利損益與帳戶餘額同步。</p>
                <form onSubmit={handleAddFill} style={{ display: "grid", gap: 12 }}>
                  <div>
                    <label style={formLabelStyle}>股票/ETF 代號</label>
                    <input
                      type="text"
                      placeholder="例如: 2330"
                      value={fillSymbol}
                      onChange={(e) => setFillSymbol(e.target.value)}
                      style={inputStyle}
                      required
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div>
                      <label style={formLabelStyle}>交易方向</label>
                      <select
                        value={fillSide}
                        onChange={(e) => setFillSide(e.target.value as "buy" | "sell")}
                        style={inputStyle}
                      >
                        <option value="buy">買進</option>
                        <option value="sell">賣出</option>
                      </select>
                    </div>
                    <div>
                      <label style={formLabelStyle}>標的種類</label>
                      <select
                        value={fillSecType}
                        onChange={(e) => setFillSecType(e.target.value as "stock" | "etf")}
                        style={inputStyle}
                      >
                        <option value="stock">股票 (個股)</option>
                        <option value="etf">ETF</option>
                      </select>
                    </div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div>
                      <label style={formLabelStyle}>成交價格 (元)</label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="價格"
                        value={fillPrice}
                        onChange={(e) => setFillPrice(e.target.value)}
                        style={inputStyle}
                        required
                      />
                    </div>
                    <div>
                      <label style={formLabelStyle}>成交數量 (股)</label>
                      <input
                        type="number"
                        placeholder="股數"
                        value={fillQty}
                        onChange={(e) => setFillQty(e.target.value)}
                        style={inputStyle}
                        required
                      />
                    </div>
                  </div>
                  <button type="submit" disabled={submittingFill} style={submitButtonStyle}>
                    {submittingFill ? "提交中..." : "確認送出成交回報"}
                  </button>
                </form>
              </div>
            </section>
          )}

          {tab === "fills" && (
            <section>
              <h2 style={sectionTitleStyle}>歷史實盤交易帳簿</h2>
              <p style={sectionDescStyle}>使用者自行回報之真實交易紀錄 (Fills)，做為 FIFO 損益的計算基石。</p>
              {fills.length === 0 ? (
                <div style={emptyStateStyle}>暫無交易紀錄。</div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={tableStyle}>
                    <thead>
                      <tr style={tableHeaderRowStyle}>
                        <th style={thStyle}>成交時間</th>
                        <th style={thStyle}>標的</th>
                        <th style={thStyle}>方向</th>
                        <th style={thStyle}>成交價</th>
                        <th style={thStyle}>股數</th>
                        <th style={thStyle}>種類</th>
                        <th style={thStyle}>總金額</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fills.map((f) => (
                        <tr key={f.id} style={tableRowStyle}>
                          <td style={tdStyle}>{f.created_at}</td>
                          <td style={{ ...tdStyle, fontWeight: "bold" }}>{f.symbol}</td>
                          <td style={tdStyle}>
                            <span style={f.side === "buy" ? buyTextStyle : sellTextStyle}>
                              {f.side === "buy" ? "買進" : "賣出"}
                            </span>
                          </td>
                          <td style={tdStyle}>{f.price}</td>
                          <td style={tdStyle}>{f.quantity.toLocaleString()}</td>
                          <td style={tdStyle}>{f.sec_type.toUpperCase()}</td>
                          <td style={tdStyle}>{(f.price * f.quantity).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {tab === "backtest" && <BacktestPanel />}
        </div>
      </main>
    </div>
  );
}

// --- CSS Styles (Deep Dark Premium Space Theme) ---

const containerStyle: React.CSSProperties = {
  backgroundColor: "#0b0f19",
  backgroundImage: "radial-gradient(at 50% 0%, #1e1b4b 0px, transparent 50%), radial-gradient(at 0% 100%, #020617 0px, transparent 50%)",
  minHeight: "100vh",
  color: "#f8fafc",
  fontFamily: "'Inter', -apple-system, sans-serif",
};

const headerStyle: React.CSSProperties = {
  marginBottom: 32,
  borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
  paddingBottom: 20,
};

const titleStyle: React.CSSProperties = {
  fontSize: 28,
  fontWeight: 800,
  letterSpacing: "-0.025em",
  margin: 0,
  background: "linear-gradient(to right, #60a5fa, #3b82f6)",
  WebkitBackgroundClip: "text",
  WebkitTextFillColor: "transparent",
};

const pulseDotStyle: React.CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: "50%",
  backgroundColor: "#10b981",
  boxShadow: "0 0 12px #10b981",
};

const subtitleStyle: React.CSSProperties = {
  color: "#94a3b8",
  marginTop: 6,
  marginBottom: 0,
  fontSize: 14,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const badgeStyle: React.CSSProperties = {
  background: "rgba(239, 68, 68, 0.15)",
  color: "#f43f5e",
  border: "1px solid rgba(239, 68, 68, 0.3)",
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 600,
};

const navStyle: React.CSSProperties = {
  display: "flex",
  gap: 8,
  backgroundColor: "rgba(15, 23, 42, 0.6)",
  padding: 6,
  borderRadius: 8,
  marginBottom: 24,
  overflowX: "auto",
};

const tabButtonStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "#94a3b8",
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 500,
  transition: "all 0.2s ease",
};

const activeTabButtonStyle: React.CSSProperties = {
  ...tabButtonStyle,
  backgroundColor: "rgba(59, 130, 246, 0.2)",
  color: "#60a5fa",
  fontWeight: 600,
  border: "1px solid rgba(59, 130, 246, 0.3)",
};

const panelContainerStyle: React.CSSProperties = {
  animation: "fadeIn 0.3s ease",
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  margin: "0 0 8px 0",
};

const sectionDescStyle: React.CSSProperties = {
  color: "#94a3b8",
  fontSize: 14,
  margin: "0 0 20px 0",
  lineHeight: 1.5,
};

const cardStyle: React.CSSProperties = {
  backgroundColor: "rgba(30, 41, 59, 0.4)",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  borderRadius: 12,
  padding: 24,
  boxShadow: "0 4px 30px rgba(0, 0, 0, 0.15)",
};

const emptyStateStyle: React.CSSProperties = {
  textAlign: "center",
  padding: "48px 0",
  color: "#64748b",
  border: "2px dashed rgba(255, 255, 255, 0.05)",
  borderRadius: 12,
  fontSize: 14,
};

const buyTagStyle: React.CSSProperties = {
  backgroundColor: "rgba(239, 68, 68, 0.15)",
  color: "#ef4444",
  border: "1px solid rgba(239, 68, 68, 0.3)",
  padding: "4px 10px",
  borderRadius: 6,
  fontWeight: 700,
  fontSize: 12,
};

const sellTagStyle: React.CSSProperties = {
  backgroundColor: "rgba(16, 185, 129, 0.15)",
  color: "#10b981",
  border: "1px solid rgba(16, 185, 129, 0.3)",
  padding: "4px 10px",
  borderRadius: 6,
  fontWeight: 700,
  fontSize: 12,
};

const symbolStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 800,
  color: "#f8fafc",
};

const confidenceStyle: React.CSSProperties = {
  fontSize: 11,
  color: "#94a3b8",
  marginTop: 2,
};

const proposalGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: 16,
  backgroundColor: "rgba(15, 23, 42, 0.4)",
  padding: 16,
  borderRadius: 8,
  margin: "16px 0",
};

const fieldLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#64748b",
  marginBottom: 4,
};

const fieldValueStyle: React.CSSProperties = {
  fontSize: 16,
  fontWeight: 700,
};

const detailBlockStyle: React.CSSProperties = {
  backgroundColor: "rgba(15, 23, 42, 0.2)",
  padding: 12,
  borderRadius: 6,
  borderLeft: "3px solid #3b82f6",
  color: "#cbd5e1",
  fontSize: 13,
  lineHeight: 1.5,
  marginBottom: 12,
};

const actionButtonGroupStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  marginTop: 20,
  flexWrap: "wrap",
};

const buttonBaseStyle: React.CSSProperties = {
  padding: "10px 20px",
  borderRadius: 8,
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 600,
  border: "none",
  transition: "all 0.2s ease",
};

const approveButtonStyle: React.CSSProperties = {
  ...buttonBaseStyle,
  backgroundColor: "#3b82f6",
  color: "white",
  boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)",
};

const generateBarStyle: React.CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap",
  padding: 12,
  marginBottom: 16,
  borderRadius: 8,
  backgroundColor: "#f1f5f9",
  border: "1px solid #e2e8f0",
};

const genInputStyle: React.CSSProperties = {
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid #cbd5e1",
  fontSize: 13,
};

const rejectButtonStyle: React.CSSProperties = {
  ...buttonBaseStyle,
  backgroundColor: "rgba(255, 255, 255, 0.05)",
  color: "#cbd5e1",
  border: "1px solid rgba(255, 255, 255, 0.1)",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
  color: "#cbd5e1",
};

const tableHeaderRowStyle: React.CSSProperties = {
  borderBottom: "2px solid rgba(255, 255, 255, 0.08)",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "12px 16px",
  color: "#64748b",
  fontWeight: 600,
};

const tableRowStyle: React.CSSProperties = {
  borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
  transition: "background-color 0.2s",
};

const tdStyle: React.CSSProperties = {
  padding: "12px 16px",
};

const buyTextStyle: React.CSSProperties = {
  color: "#ef4444",
  fontWeight: "bold",
};

const sellTextStyle: React.CSSProperties = {
  color: "#10b981",
  fontWeight: "bold",
};

const approvedTagStyle: React.CSSProperties = {
  backgroundColor: "rgba(59, 130, 246, 0.15)",
  color: "#60a5fa",
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 11,
};

const rejectedTagStyle: React.CSSProperties = {
  backgroundColor: "rgba(244, 63, 94, 0.15)",
  color: "#fda4af",
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 11,
};

const pendingTagStyle: React.CSSProperties = {
  backgroundColor: "rgba(100, 116, 139, 0.15)",
  color: "#94a3b8",
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 11,
};

const pnlGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
};

const statCardStyle: React.CSSProperties = {
  backgroundColor: "rgba(30, 41, 59, 0.4)",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  borderRadius: 12,
  padding: 20,
  textAlign: "center",
};

const statLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#64748b",
  marginBottom: 8,
};

const statValueStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 800,
};

const formLabelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  color: "#64748b",
  marginBottom: 6,
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  backgroundColor: "rgba(15, 23, 42, 0.6)",
  border: "1px solid rgba(255, 255, 255, 0.1)",
  borderRadius: 6,
  padding: "8px 12px",
  color: "white",
  fontSize: 13,
};

const submitButtonStyle: React.CSSProperties = {
  ...buttonBaseStyle,
  backgroundColor: "#10b981",
  color: "white",
  width: "100%",
  marginTop: 12,
  boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
};

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: "rgba(239, 68, 68, 0.15)",
  color: "#f43f5e",
  border: "1px solid rgba(239, 68, 68, 0.2)",
  padding: 12,
  borderRadius: 8,
  marginBottom: 16,
  fontSize: 13,
};

const successBannerStyle: React.CSSProperties = {
  backgroundColor: "rgba(16, 185, 129, 0.15)",
  color: "#34d399",
  border: "1px solid rgba(16, 185, 129, 0.2)",
  padding: 12,
  borderRadius: 8,
  marginBottom: 16,
  fontSize: 13,
};
