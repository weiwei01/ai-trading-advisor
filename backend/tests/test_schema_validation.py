"""Pydantic 驗證測試 — 對 LLM 不穩定輸出的第一道防線。"""
import pytest
from pydantic import ValidationError

from app.advisor.prompt import parse_response
from app.schemas import Proposal


def test_valid_proposal():
    p = Proposal(
        symbol="2330", action="buy", price=100.0, quantity=1000,
        confidence=0.8, reason="均線多頭排列", risk_note="跌破月線停損",
    )
    assert p.symbol == "2330"


@pytest.mark.parametrize("field,value", [
    ("price", 0),            # 價格須 > 0
    ("price", -5),
    ("quantity", 0),         # 數量須 > 0
    ("confidence", 1.5),     # 信心須 0~1
    ("confidence", -0.1),
])
def test_invalid_numeric_fields_rejected(field, value):
    kwargs = dict(
        symbol="2330", action="buy", price=100.0, quantity=1000,
        confidence=0.8, reason="x", risk_note="y",
    )
    kwargs[field] = value
    with pytest.raises(ValidationError):
        Proposal(**kwargs)


def test_blank_reason_rejected():
    with pytest.raises(ValidationError):
        Proposal(
            symbol="2330", action="buy", price=100.0, quantity=1000,
            confidence=0.8, reason="   ", risk_note="y",
        )


def test_parse_response_strips_code_fence():
    raw = '```json\n{"proposals": [], "model_note": "ok"}\n```'
    batch = parse_response(raw)
    assert batch.proposals == []
    assert batch.model_note == "ok"


def test_parse_response_rejects_bad_proposal():
    raw = '{"proposals": [{"symbol":"2330","action":"buy","price":-1,'\
          '"quantity":1,"confidence":0.5,"reason":"a","risk_note":"b"}]}'
    with pytest.raises(ValueError):
        parse_response(raw)
