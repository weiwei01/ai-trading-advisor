"""歷史日 K 抓取輔助邏輯測試。"""

from app.db import get_connection, init_db
from app.market import repository as market_repo
from app.market.twse import month_range, parse_month


def test_month_range_inclusive_across_year_boundary():
    assert month_range("2023-11", "2024-02") == [
        "20231101",
        "20231201",
        "20240101",
        "20240201",
    ]


def test_parse_month_accepts_compact_and_dash_formats():
    assert parse_month("2023-01") == (2023, 1)
    assert parse_month("202301") == (2023, 1)
    assert parse_month("20230101") == (2023, 1)


def test_month_data_and_fetch_failure_lifecycle():
    conn = get_connection(":memory:")
    init_db(conn)
    try:
        assert not market_repo.has_month_data(conn, "2330", "20240101")

        market_repo.save_candles(
            conn,
            "2330",
            [{
                "date": "2024-01-02",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1000,
            }],
        )
        assert market_repo.has_month_data(conn, "2330", "20240101")
        assert not market_repo.has_month_data(conn, "2330", "20240201")

        market_repo.record_fetch_failure(conn, "2330", "20240201", "timeout")
        failures = market_repo.list_fetch_failures(conn, ["2330"])
        assert failures == [{
            "symbol": "2330",
            "yyyymm": "20240201",
            "error": "timeout",
            "failed_at": failures[0]["failed_at"],
        }]

        market_repo.clear_fetch_failure(conn, "2330", "20240201")
        assert market_repo.list_fetch_failures(conn, ["2330"]) == []
    finally:
        conn.close()
