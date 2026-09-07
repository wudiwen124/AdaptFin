from advisor.graph.nodes.extract import extract_memory_updates


def test_buy_with_qty_and_preference():
    holdings, removed, facts = extract_memory_updates("我买了100股510300，不喜欢频繁交易")
    assert [h.symbol for h in holdings] == ["510300"]
    assert holdings[0].qty == 100
    assert removed == []
    assert "用户不喜欢频繁交易" in facts


def test_buy_without_qty_and_qty_after_code():
    h1, _, _ = extract_memory_updates("我加仓了 600519")
    assert h1[0].qty is None
    h2, _, _ = extract_memory_updates("我持有600519 100股")
    assert h2[0].qty == 100


def test_sell_removes_holding():
    holdings, removed, _ = extract_memory_updates("卖出510300")
    assert holdings == []
    assert removed == ["510300"]


def test_positive_preference():
    _, _, facts = extract_memory_updates("我比较偏好红利低波，也关注新能源")
    assert any("红利低波" in f for f in facts)
    assert any("新能源" in f for f in facts)
