from pathlib import Path

import pytest

from advisor.schemas.risk import RiskProfile
from advisor.schemas.risk import CONSTRAINTS, RiskLevel
from advisor.schemas.user import Holding, UserProfile
from advisor.store import ProfileStore


def _store(tmp_path):
    return ProfileStore(tmp_path / "test.db")


def test_roundtrip_profile(tmp_path):
    store = _store(tmp_path)
    profile = UserProfile(
        user_id="u1",
        risk=RiskProfile(score=30, level=RiskLevel.C3, constraints=CONSTRAINTS[RiskLevel.C3]),
        holdings=[Holding(symbol="600519", name="贵州茅台", qty=100, cost=1450.0)],
        facts=["用户提到 2026 年有出国计划"],
    )
    store.upsert_profile(profile)
    loaded = store.get_profile("u1")
    assert loaded is not None
    assert loaded.risk.level == RiskLevel.C3
    assert loaded.holdings[0].qty == 100
    assert loaded.facts == profile.facts


def test_set_risk_and_holdings(tmp_path):
    store = _store(tmp_path)
    store.set_risk("u2", RiskProfile(score=50, level=RiskLevel.C5, constraints=CONSTRAINTS[RiskLevel.C5]))
    store.add_holding("u2", Holding(symbol="510300", name="沪深300ETF", qty=1000))
    profile = store.get_profile("u2")
    assert profile.risk.level == RiskLevel.C5
    assert [h.symbol for h in profile.holdings] == ["510300"]
    store.add_holding("u2", Holding(symbol="510300", name="沪深300ETF", qty=2000))
    assert store.get_holdings("u2")[0].qty == 2000  # 同标的覆盖


def test_fact_dedup(tmp_path):
    store = _store(tmp_path)
    store.add_fact("u3", "厌恶频繁交易")
    store.add_fact("u3", "厌恶频繁交易")
    assert store.get_profile("u3").facts == ["厌恶频繁交易"]


def test_risk_history_keeps_previous_levels(tmp_path):
    store = _store(tmp_path)
    c1 = RiskProfile(score=10, level=RiskLevel.C1, constraints=CONSTRAINTS[RiskLevel.C1])
    c5 = RiskProfile(score=60, level=RiskLevel.C5, constraints=CONSTRAINTS[RiskLevel.C5])
    store.set_risk("u_hist", c1)
    store.set_risk("u_hist", c5)
    history = store.risk_history("u_hist")
    assert [h["level"] for h in history] == ["C1", "C5"]
    assert store.get_profile("u_hist").risk.level == RiskLevel.C5


def test_list_user_ids_by_recency(tmp_path):
    store = _store(tmp_path)
    store.set_risk("u_a", RiskProfile(score=10, level=RiskLevel.C1, constraints=CONSTRAINTS[RiskLevel.C1]))
    store.set_risk("u_b", RiskProfile(score=60, level=RiskLevel.C5, constraints=CONSTRAINTS[RiskLevel.C5]))
    store.add_fact("u_b", "偏好红利低波")  # 让 u_b 更新更晚
    ids = store.list_user_ids()
    assert ids[0] == "u_b"
    assert set(ids[:2]) == {"u_a", "u_b"}


def test_delete_user_and_clear_all(tmp_path):
    store = _store(tmp_path)
    store.set_risk("u_d1", RiskProfile(score=10, level=RiskLevel.C1, constraints=CONSTRAINTS[RiskLevel.C1]))
    store.add_fact("u_d1", "偏好红利低波")
    store.add_holding("u_d1", Holding(symbol="510300", qty=100))
    store.set_risk("u_d2", RiskProfile(score=60, level=RiskLevel.C5, constraints=CONSTRAINTS[RiskLevel.C5]))

    store.delete_user("u_d1")
    assert store.get_profile("u_d1") is None
    assert store.get_holdings("u_d1") == []
    assert store.recall_memory("u_d1", "红利") == []
    assert store.get_profile("u_d2") is not None  # 不影响其他人

    assert store.clear_all_users() == 1
    assert store.list_user_ids() == []


def test_delete_checkpoints_for_user(tmp_path):
    import sqlite3

    ckpt = tmp_path / "ckpt.db"
    conn = sqlite3.connect(ckpt)
    conn.execute("CREATE TABLE checkpoints (thread_id TEXT)")
    conn.execute("CREATE TABLE writes (thread_id TEXT)")
    for t in ("ui_u_x", "cli_u_x", "u_x", "ui_other"):
        conn.execute("INSERT INTO checkpoints VALUES (?)", (t,))
    conn.commit()
    conn.close()

    store = ProfileStore(tmp_path / "p.db", checkpoint_db_path=ckpt)
    store.delete_checkpoints_for_user("u_x")

    conn = sqlite3.connect(ckpt)
    rest = [r[0] for r in conn.execute("SELECT thread_id FROM checkpoints").fetchall()]
    conn.close()
    assert rest == ["ui_other"]


def test_export_and_backup_user(tmp_path):
    store = _store(tmp_path)
    store.set_risk("u_exp", RiskProfile(score=30, level=RiskLevel.C3, constraints=CONSTRAINTS[RiskLevel.C3]))
    store.add_holding("u_exp", Holding(symbol="600519", qty=100))
    store.add_fact("u_exp", "偏好红利低波")

    data = store.export_user("u_exp")
    assert data["profile"]["risk"]["level"] == "C3"
    assert data["holdings"][0]["symbol"] == "600519"
    assert data["memory"][0]["fact"] == "偏好红利低波"

    backup = store.backup_user("u_exp")
    assert Path(backup).exists()
    store.delete_user("u_exp")
    assert Path(backup).exists()  # 备份在删除后仍可恢复

    with pytest.raises(KeyError):
        store.export_user("u_exp")
