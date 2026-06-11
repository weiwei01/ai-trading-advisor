import { useEffect, useState } from "react";
import { listStoredSymbols, runStoredBacktest } from "./api";
import type { BacktestResult } from "./types";

/**
 * 回測除錯面板 — 定位是「除錯儀表板」，不是成績單。
 * 陽春 SVG 權益曲線 + 進出場標記，用來肉眼檢查回測邏輯
 * （隔日開盤成交、出場時機、費用扣除）是否合理。
 */
export default function BacktestPanel() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [days, setDays] = useState(90);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listStoredSymbols().then(setSymbols).catch((e) => setError(String(e)));
  }, []);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setResult(await runStoredBacktest({ days }));
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <section>
      <h2>回測（除錯用）</h2>
      <p style={{ color: "#888", marginTop: 0 }}>
        DB 內標的：{symbols.length ? symbols.join("、") : "（尚無，請先跑 scripts.fetch_history）"}
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
        <label>
          天數{" "}
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            style={{ width: 72 }}
          />
        </label>
        <button onClick={run} disabled={running || symbols.length === 0}>
          {running ? "跑回測中…" : "跑回測"}
        </button>
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {result && (
        <>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 12 }}>
            <Stat label="總報酬" value={`${(result.total_return * 100).toFixed(2)}%`} />
            <Stat label="成交筆數" value={String(result.n_trades)} />
            <Stat label="勝率" value={`${(result.win_rate * 100).toFixed(1)}%`} />
            <Stat label="期望值/筆" value={result.expectancy.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="期末權益" value={result.final_equity.toLocaleString()} />
            <Stat label="最大回撤 (MDD)" value={`${(result.max_drawdown * 100).toFixed(2)}%`} />
            <Stat label="Sharpe Ratio" value={result.sharpe_ratio.toFixed(2)} />
            <Stat label="平均持有" value={`${result.avg_holding_days.toFixed(1)} 天`} />
            <Stat label="交易成本佔獲利比" value={`${(result.tx_cost_ratio * 100).toFixed(2)}%`} />
          </div>

          <EquityChart result={result} />

          <h3>逐筆成交</h3>
          {result.trades.length === 0 && <p style={{ color: "#888" }}>無成交。</p>}
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                {["成交日", "標的", "方向", "價格", "股數", "理由"].map((h) => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.trades.map((t, i) => (
                <tr key={i}>
                  <td style={td}>{t.fill_date}</td>
                  <td style={td}>{t.symbol}</td>
                  <td style={{ ...td, color: t.side === "buy" ? "#c33" : "#383" }}>
                    {t.side === "buy" ? "買" : "賣"}
                  </td>
                  <td style={td}>{t.price}</td>
                  <td style={td}>{t.quantity}</td>
                  <td style={td}>{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "#888" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left", borderBottom: "2px solid #ccc", padding: "4px 8px", fontSize: 13,
};
const td: React.CSSProperties = {
  borderBottom: "1px solid #eee", padding: "4px 8px", fontSize: 13,
};

function EquityChart({ result }: { result: BacktestResult }) {
  const W = 800;
  const H = 260;
  const PAD = 36;
  const curve = result.equity_curve;
  if (curve.length === 0) return <p style={{ color: "#888" }}>無權益曲線。</p>;

  const values = curve.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const x = (i: number) =>
    PAD + (i / Math.max(curve.length - 1, 1)) * (W - PAD * 2);
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - PAD * 2);

  const path = curve
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`)
    .join(" ");

  const dateIndex = new Map(curve.map((p, i) => [p.date, i]));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", maxWidth: W, border: "1px solid #eee", borderRadius: 8 }}
    >
      {/* 起始資金基準線 */}
      {(() => {
        const first = curve[0].equity;
        return (
          <line
            x1={PAD} x2={W - PAD} y1={y(first)} y2={y(first)}
            stroke="#bbb" strokeDasharray="4 4"
          />
        );
      })()}
      <path d={path} fill="none" stroke="#2563eb" strokeWidth={1.5} />

      {/* 進出場標記：買=紅色上三角、賣=綠色下三角（台股紅漲綠跌習慣） */}
      {result.trades.map((t, i) => {
        const idx = dateIndex.get(t.fill_date);
        if (idx === undefined) return null;
        const cx = x(idx);
        const cy = y(curve[idx].equity);
        const up = t.side === "buy";
        const points = up
          ? `${cx},${cy - 10} ${cx - 5},${cy - 2} ${cx + 5},${cy - 2}`
          : `${cx},${cy + 10} ${cx - 5},${cy + 2} ${cx + 5},${cy + 2}`;
        return (
          <polygon key={i} points={points} fill={up ? "#c33" : "#383"}>
            <title>{`${t.fill_date} ${t.side} ${t.symbol} ${t.quantity}@${t.price}\n${t.reason}`}</title>
          </polygon>
        );
      })}

      {/* 首尾日期與金額刻度 */}
      <text x={PAD} y={H - 8} fontSize={11} fill="#888">{curve[0].date}</text>
      <text x={W - PAD} y={H - 8} fontSize={11} fill="#888" textAnchor="end">
        {curve[curve.length - 1].date}
      </text>
      <text x={PAD - 4} y={y(max) + 4} fontSize={11} fill="#888" textAnchor="end">
        {Math.round(max / 1000)}k
      </text>
      <text x={PAD - 4} y={y(min) + 4} fontSize={11} fill="#888" textAnchor="end">
        {Math.round(min / 1000)}k
      </text>
    </svg>
  );
}
