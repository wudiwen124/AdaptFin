from advisor.graph.nodes.extract import llm_extract_facts
from advisor.llm.fake_gateway import FakeGateway


def test_llm_extract_facts_on_natural_expression():
    facts = llm_extract_facts(FakeGateway(), "我打算拿三年，能接受 20% 的回撤")
    assert len(facts) == 1
    assert "长期" in facts[0] or "三年" in facts[0]


def test_llm_extract_drops_irrelevant_text():
    assert llm_extract_facts(FakeGateway(), "帮我查一下600519") == []
    assert llm_extract_facts(None, "我打算拿三年") == []
