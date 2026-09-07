import httpx

from advisor.llm.client import ModelGateway


def _ok_body() -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}


def test_read_timeout_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("read timed out", request=request)
        return httpx.Response(200, json=_ok_body())

    gw = ModelGateway(
        "test-key",
        base_url="https://example.test/v4",
        max_retries=1,
        retry_base_delay=0.0,
        transport=httpx.MockTransport(handler),
    )
    out = gw.chat([{"role": "user", "content": "hi"}], tier="router")
    assert calls["n"] == 2
    assert out["choices"][0]["message"]["content"] == "ok"


def test_quota_exhausted_switches_to_fallback_model():
    used_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = request.read().decode("utf-8")  # noqa: SIM115
        import json

        model = json.loads(model)["model"]
        used_models.append(model)
        if model == "quota-dead":
            return httpx.Response(429, json={"error": {"code": "1305", "message": "quota"}})
        return httpx.Response(200, json=_ok_body())

    gw = ModelGateway(
        "test-key",
        base_url="https://example.test/v4",
        router_model="quota-dead",
        router_fallbacks=["good-model"],
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    out = gw.chat([{"role": "user", "content": "hi"}], tier="router")
    assert used_models == ["quota-dead", "good-model"]
    assert out["choices"][0]["message"]["content"] == "ok"
