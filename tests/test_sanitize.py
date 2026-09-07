from advisor.graph.nodes.text import sanitize_user_facing


def test_removes_internal_tool_labels():
    text = sanitize_user_facing("【来源：get_financial_summary】营收同比 1.3%")
    assert "get_financial_summary" not in text
    assert "来源：" not in text or "东方财富" in text


def test_source_prefix_converted_to_readable_name():
    out = sanitize_user_facing("来源：get_recent_news，公告时间 2026-08-15")
    assert "get_recent_news" not in out
    assert "东方财富公告" in out


def test_tool_evidence_markers_removed():
    out = sanitize_user_facing("[工具证据 get_realtime_quote({'symbol': '600519'})]\n价格 42.37")
    assert "工具证据" not in out
    assert "get_realtime_quote" not in out


def test_summary_prefix_removed_from_start():
    out = sanitize_user_facing("**结论摘要**\n贵州茅台最新价 42.37 元。")
    assert out.startswith("贵州茅台")
    assert "结论摘要" not in out
