import time

from advisor.datasources.cache import TTLCache, cache_key


def test_cache_get_set():
    c = TTLCache()
    key = cache_key("quote", "600519")
    assert c.get(key) is None
    c.set(key, {"price": 1700.0}, ttl=60)
    assert c.get(key) == {"price": 1700.0}
    c.clear()
    assert c.get(key) is None


def test_cache_expiry():
    c = TTLCache()
    key = cache_key("k")
    c.set(key, 1, ttl=0.01)
    time.sleep(0.02)
    assert c.get(key) is None
