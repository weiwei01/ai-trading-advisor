"""資料品質檢查腳本：缺日偵測、價格異常。

用法：
    python -m scripts.check_data_quality
"""
from __future__ import annotations

from app.db import get_connection
from app.market import repository as market_repo


def main() -> None:
    conn = get_connection()
    try:
        symbols = market_repo.stored_symbols(conn)
        if not symbols:
            print("資料庫內沒有任何 K 棒資料，請先執行 fetch_history 抓取資料。")
            return

        print(f"開始檢查 {len(symbols)} 檔標的的資料品質 ...\n")
        
        # 1. 建立基準交易日：取所有標的所有出現過的交易日之聯集
        all_dates_by_symbol = {}
        all_market_dates = set()
        for s in symbols:
            candles = market_repo.load_candles(conn, s)
            dates = [c["date"] for c in candles]
            all_dates_by_symbol[s] = (candles, set(dates))
            all_market_dates.update(dates)
            
        sorted_market_dates = sorted(all_market_dates)
        
        warnings_count = 0

        for s in symbols:
            candles, date_set = all_dates_by_symbol[s]
            if not candles:
                continue

            first_date = candles[0]["date"]
            last_date = candles[-1]["date"]

            # 過濾出在該標的時間區間內，市場上所有「應該有交易」的日期
            expected_dates = [
                d for d in sorted_market_dates if first_date <= d <= last_date
            ]
            missing_dates = [d for d in expected_dates if d not in date_set]

            # 缺日檢查
            if missing_dates:
                warnings_count += 1
                print(f"[警告] {s}: 發現 {len(missing_dates)} 個交易日斷層！")
                print(f"  區間: {first_date} ~ {last_date}")
                if len(missing_dates) <= 5:
                    print(f"  缺失日期: {', '.join(missing_dates)}")
                else:
                    print(f"  缺失前五個日期: {', '.join(missing_dates[:5])} ...")

            # 價格異常檢查 (漲跌幅限制 10% 在台灣，若日變動 > 11% 視為除權息跳空或錯誤)
            anomalies = []
            for i in range(1, len(candles)):
                prev = candles[i - 1]
                curr = candles[i]
                
                if prev["close"] <= 0:
                    continue
                    
                ret = (curr["close"] - prev["close"]) / prev["close"]
                if abs(ret) > 0.11:  # 超過 11% 變動
                    anomalies.append((curr["date"], ret, prev["close"], curr["close"]))

            if anomalies:
                warnings_count += len(anomalies)
                print(f"[警告] {s}: 偵測到 {len(anomalies)} 筆價格異常跳空 (變動 > 11%)！")
                for date, ret, p_close, c_close in anomalies[:5]:
                    direction = "上跳" if ret > 0 else "下挫"
                    print(f"  {date}: {direction} {ret*100:.2f}% (前收 {p_close:.2f} -> 收 {c_close:.2f})")
                if len(anomalies) > 5:
                    print(f"  ... 還有 {len(anomalies) - 5} 筆異常")

        if warnings_count == 0:
            print("🎉 資料品質檢查通過！所有標的皆無缺日或價格異常。")
        else:
            print(f"\n⚠️ 檢查結束：共發現 {warnings_count} 個品質警告。請確認是否為除權息所致。")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
