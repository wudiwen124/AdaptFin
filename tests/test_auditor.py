from advisor.graph.nodes.auditor import after_audit, auditor_node
from advisor.graph.state import initial_state
from advisor.schemas.research import EvidenceRecord


def _state(**overrides):
    state = initial_state("u1", [])
    state.update(overrides)
    return state


def test_disclaimer_auto_appended():
    out = auditor_node(_state(final_answer="600519 价格是 42.37"))
    assert "不构成投资建议" in out["final_answer"]
    assert "免责声明" in (out["audit_issue"] or "")


def test_chat_greeting_skips_investment_disclaimer():
    out = auditor_node(_state(final_answer="你好！我是 AdaptFin。", intent="chat"))
    assert out["audit_issue"] is None
    assert "不构成投资建议" not in out["final_answer"]


def test_forbidden_imperative_triggers_revision():
    out = auditor_node(_state(final_answer="建议立即买入 600519，不构成投资建议。"))
    assert "指令性买卖表述" in (out["audit_issue"] or "")
    assert after_audit(out) == "advisor"


def test_hallucinated_decimal_detected():
    state = _state(
        final_answer="PE 为 99.99。不构成投资建议。",
        intent="research",
        tool_observations=[
            EvidenceRecord(
                tool="get_valuation",
                args={"symbol": "600519"},
                output='{"symbol": "sh600519", "pe_ttm": 30.5, "meta": {"source": "demo", "data_as_of": "2026-09-07"}}',
                source="demo",
                data_as_of="2026-09-07",
            )
        ],
    )
    out = auditor_node(state)
    assert "99.99" in (out["audit_issue"] or "")


def test_grounded_numbers_pass():
    state = _state(
        final_answer="最新价 42.37 元，来源 demo。不构成投资建议。",
        intent="quote",
        tool_observations=[
            EvidenceRecord(
                tool="get_realtime_quote",
                args={"symbol": "600519"},
                output='{"price": 42.37, "meta": {"source": "demo", "data_as_of": "2026-09-07 15:00:00"}}',
                source="demo",
                data_as_of="2026-09-07 15:00:00",
            )
        ],
    )
    out = auditor_node(state)
    assert out["audit_issue"] is None
    assert after_audit(out) == "memory_writer"


def test_pit_date_outside_evidence_detected():
    state = _state(
        final_answer="2027-01-01 后业绩会改善。不构成投资建议。",
        intent="research",
        tool_observations=[
            EvidenceRecord(
                tool="get_daily_kline",
                args={"symbol": "600519"},
                output='{"meta": {"source": "demo", "data_as_of": "2026-09-07"}}',
                source="demo",
                data_as_of="2026-09-07",
            )
        ],
    )
    out = auditor_node(state)
    assert "日期" in (out["audit_issue"] or "")


def test_pit_as_of_blocks_late_observation():
    state = _state(
        final_answer="按 2025-06-30 的数据分析。不构成投资建议。",
        intent="research",
        as_of_date="2025-06-30",
        tool_observations=[
            EvidenceRecord(
                tool="get_daily_kline",
                args={"symbol": "600519"},
                output='{"meta": {"source": "demo", "data_as_of": "2026-09-07"}}',
                source="demo",
                data_as_of="2026-09-07",
            )
        ],
    )
    out = auditor_node(state)
    assert "晚于研究截止日" in (out["audit_issue"] or "")


def test_pit_as_of_allows_observations_within_date():
    state = _state(
        final_answer="按 2025-06-30 的数据分析。不构成投资建议。",
        intent="research",
        as_of_date="2025-06-30",
        tool_observations=[
            EvidenceRecord(
                tool="get_daily_kline",
                args={"symbol": "600519"},
                output='{"meta": {"source": "demo", "data_as_of": "2025-06-27"}}',
                source="demo",
                data_as_of="2025-06-27",
            )
        ],
    )
    out = auditor_node(state)
    assert out["audit_issue"] is None


def test_pit_blocks_future_news_published_date():
    state = _state(
        final_answer="按 2025-06-30 的公告分析。不构成投资建议。",
        intent="research",
        as_of_date="2025-06-30",
        tool_observations=[
            EvidenceRecord(
                tool="get_recent_news",
                args={"symbol": "600519"},
                output='[{"title": "未来公告", "published_at": "2026-08-15"}]',
                source="东方财富公告",
                data_as_of=None,
            )
        ],
    )
    out = auditor_node(state)
    assert "晚于研究截止日" in (out["audit_issue"] or "")


def test_pit_allows_news_published_within_date():
    state = _state(
        final_answer="按 2025-06-30 的公告分析。不构成投资建议。",
        intent="research",
        as_of_date="2025-06-30",
        tool_observations=[
            EvidenceRecord(
                tool="get_recent_news",
                args={"symbol": "600519"},
                output='[{"title": "历史公告", "published_at": "2025-06-28"}]',
                source="东方财富公告",
                data_as_of=None,
            )
        ],
    )
    out = auditor_node(state)
    assert out["audit_issue"] is None
