from advisor.orchestration.router import rule_route


def test_rule_risk():
    r = rule_route("我想做一次风险测评")
    assert r.intent == "risk"
    assert r.source == "rule"


def test_rule_portfolio():
    r = rule_route("看看我的持仓风险大不大")
    assert r.intent == "portfolio"


def test_rule_quote():
    r = rule_route("贵州茅台600519现在多少钱")
    assert r.intent == "quote"
    assert r.symbols == ["600519"]


def test_rule_research():
    r = rule_route("分析一下600519的基本面")
    assert r.intent == "research"
    assert r.symbols == ["600519"]


def test_ambiguous_low_confidence():
    r = rule_route("600519 现在价格怎么样，值得分析吗")
    assert r.confidence < 0.75  # 交给 LLM 判断


def test_no_keyword_with_code():
    r = rule_route("600519")
    assert r.intent == "quote"


def test_plain_chat_no_rule():
    assert rule_route("你好，介绍一下你们能做什么") is None
