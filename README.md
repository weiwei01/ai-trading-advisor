# AI Trading Advisor

台股 **AI 決策輔助**系統。串接行情與 LLM，自動讀盤、篩選標的，並為每筆進場寫出理由與風險條件。

> **定位：非自動化交易。** 系統不會送出任何委託單。AI 負責研究與提案，最終是否拿真錢進場，由扛風險的人（你）決定，並自行於券商端送單。

## 設計重點

- **TradingAdvisor 介面**（`app/advisor/base.py`）：把「呼叫 AI 做決策」抽象出來。測試時塞 `StubAdvisor` 跑完整條流程，不燒 Token、不被網路/模型延遲卡住。
- **穩定 vs 非穩定分層**：
  - 穩定層（純函式，`app/advisor/prompt.py`）：組 prompt、解析回應、定義 schema，穩定輸入穩定輸出。
  - 非穩定層（`app/advisor/codex.py`）：唯一碰網路與模型隨機性的地方，用 smoke test 處理。
- **Pydantic 嚴格驗證**（`app/schemas.py`）：價格 > 0、數量為正整數、信心 0~1、理由/風險不可空白，違規直接擋下，防 LLM 格式不穩定與幻覺。
- **損益計算**（`app/pnl.py`）：FIFO 配對，成本實扣手續費與證交稅，ETF 與個股稅率分開。寧願多算成本，也不要自欺欺人的漂亮損益。
- **回測引擎**（`app/backtest.py`）：第 d 天只餵到第 d 天為止的 K 棒；成交價用隔一交易日開盤價；跑在隔離暫存 DB，走與實盤相同的風控引擎，手續費與稅照算。輸出權益曲線、總報酬、勝率、期望值。

## 技術堆疊

後端 Python / FastAPI / SQLite / Pydantic · 前端 React + TypeScript + Vite · 行情：證交所公開 API（日 K 歷史）+ 永豐 Shioaji（盤中即時）· 決策 LLM：OpenAI Codex SDK。

## 後端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://localhost:8000 ，文件 /docs
pytest                              # 跑單元 + 流程測試（不含 smoke）
pytest -m smoke                     # 真正呼叫 Codex 的冒煙測試（需 OPENAI_API_KEY，會燒 Token）
```

### 抓真實日 K 並回測

```bash
# 1) 從證交所抓最近 3 個月日 K，存入本地 SQLite（回測本身不需再連網）
python -m scripts.fetch_history 2330 0050 --months 3

# 2) 對已存資料跑回測。用規則型 advisor 可不燒 Token 就跑出有成交的結果，
#    先驗證 決策→風控→損益 整條鏈路正確，再換 Codex。
USE_RULES=1 python -m scripts.run_backtest 2330 0050 --days 90 --style 均線+突破 --etf 0050

# 要用真實 Codex 決策（逐日呼叫 LLM，較燒 Token）：
USE_CODEX=1 OPENAI_API_KEY=sk-... python -m scripts.run_backtest 2330 --days 20
```

預設用 stub advisor 與 stub 報價，不需任何金鑰即可跑。切到真實整合：

| 環境變數 | 作用 |
|---|---|
| `USE_RULES=1` | 改用規則型 advisor（均線交叉 + 突破，不燒 Token，用來驗證鏈路） |
| `USE_CODEX=1` + `OPENAI_API_KEY` | 改用真實 Codex 決策 |
| `USE_SHIOAJI=1` + `SHIOAJI_API_KEY` / `SHIOAJI_SECRET_KEY` | 改用永豐即時報價 |

並取消 `requirements.txt` 中 `openai` / `shioaji` 的註解後安裝。

## 前端

> **需求：Node.js 18 以上**（Vite 5）。目前機器若為 Node 12，請先升級（建議用 nvm）。

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 ，/api 代理到後端 8000
```

## 目錄

```
backend/app/
  schemas.py          # Pydantic 提案契約（穩定層）
  advisor/            # TradingAdvisor 介面、stub、codex、prompt 純函式
  market/             # twse 日K、shioaji 即時報價（介面化、可 stub）
  pnl.py              # FIFO 損益（含手續費與證交稅）
  risk.py             # 風控引擎（實盤/回測共用）
  backtest.py         # 逐日回測引擎
  routers/            # proposals / portfolio / backtest API
backend/tests/        # 單元、端到端流程、回測測試 + codex smoke
frontend/src/         # React 提案裁決介面
```
