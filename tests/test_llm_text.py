import pytest

from advisor.llm.text import parse_json
from advisor.orchestration.router import llm_route, route_request
from tests.fake_gateway import FakeGateway


def test_parse_json_with_code_fence():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_single_backtick():
    assert parse_json('`json\n{"a": 1}\n`') == {"a": 1}


def test_parse_json_invalid_placeholder_raises():
    with pytest.raises(ValueError):
        parse_json('`json\n{"confidence": 0.0到1.0}\n`')


def test_llm_route_template_echo_falls_back():
    """模型复述模板/占位符时，路由必须兜底为 chat，而不是抛异常。"""
    gateway = FakeGateway(
        queue=[
            {
                "choices": [
                    {
                        "message": {
                            "content": '`json\n{"intent": "chat", "symbols": [], "confidence": 0.0到1.0}\n`',
                        }
                    }
                ]
            }
        ]
    )
    result = route_request("随便聊点什么", gateway=gateway)
    assert result.intent == "chat"
    assert result.confidence < 0.6
    assert result.source == "fallback"


def test_llm_route_valid_parse():
    gateway = FakeGateway(
        queue=[
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"intent": "quote", "symbols": ["600519"], "confidence": 0.9}',
                        }
                    }
                ]
            }
        ]
    )
    result = llm_route(gateway, "600519 什么价格")
    assert result.intent == "quote"
    assert result.symbols == ["600519"]
