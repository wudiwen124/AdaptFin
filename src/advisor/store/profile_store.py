"""长期记忆雏形：用户画像 / 持仓 / 事实的 SQLite 存储（P4 将挂到 LangGraph Store 语义下）。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from advisor.schemas.risk import RiskProfile
from advisor.schemas.user import Holding, UserProfile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holdings (
    user_id    TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    payload    TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, symbol)
);
CREATE TABLE IF NOT EXISTS facts (
    user_id    TEXT NOT NULL,
    fact       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, fact)
);
CREATE TABLE IF NOT EXISTS risk_history (
    user_id    TEXT NOT NULL,
    level      TEXT NOT NULL,
    score      INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    request_id TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    intent     TEXT,
    final_len  INTEGER,
    degraded   INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS memory_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    fact       TEXT NOT NULL,
    source     TEXT DEFAULT 'rule',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, fact)
);
CREATE TABLE IF NOT EXISTS memory_embeddings (
    note_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    vector  TEXT NOT NULL
);
"""


class ProfileStore:
    def __init__(self, db_path: str | Path, checkpoint_db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path)
        self.checkpoint_db_path = str(checkpoint_db_path) if checkpoint_db_path else None
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- users ----
    def upsert_profile(self, profile: UserProfile) -> None:
        profile.updated_at = datetime.now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(user_id, payload, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (profile.user_id, profile.model_dump_json(), profile.updated_at.isoformat()),
            )
            self._sync_holdings(conn, profile)

    def get_profile(self, user_id: str) -> UserProfile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        return UserProfile.model_validate_json(row["payload"])

    def list_user_ids(self, limit: int = 100) -> list[str]:
        """按最近更新排序返回已有用户 ID（供 UI 选择“继续对话”）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM users ORDER BY updated_at DESC LIMIT ?",
                (max(limit, 1),),
            ).fetchall()
        return [r["user_id"] for r in rows]

    def delete_user(self, user_id: str) -> None:
        """删除单用户画像/持仓/记忆/历史/审计；会话 checkpoint 一并清理。"""
        tables = ("audit_log", "risk_history", "memory_notes", "facts", "holdings", "users")
        with self._connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        self.delete_checkpoints_for_user(user_id)

    def clear_all_users(self) -> int:
        """清空所有用户（返回删除数）。"""
        ids = self.list_user_ids()
        for user_id in ids:
            self.delete_user(user_id)
        return len(ids)

    def delete_checkpoints_for_user(self, user_id: str) -> None:
        """删除该用户常见前缀线程（ui_/cli_/裸 user_id）；自定义 thread 不在清理范围。"""
        if not self.checkpoint_db_path or not Path(self.checkpoint_db_path).exists():
            return
        patterns = (f"ui_{user_id}%", f"cli_{user_id}%", user_id)
        conn = sqlite3.connect(self.checkpoint_db_path)
        try:
            for table in ("checkpoints", "writes"):
                for pattern in patterns:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id LIKE ?", (pattern,))
            conn.commit()
        finally:
            conn.close()

    def set_risk(self, user_id: str, risk: RiskProfile) -> UserProfile:
        profile = self.get_profile(user_id) or UserProfile(user_id=user_id)
        profile.risk = risk
        self.upsert_profile(profile)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO risk_history(user_id, level, score, created_at) VALUES(?,?,?,?)",
                (user_id, risk.level.value, risk.score, risk.answered_at.isoformat()),
            )
        return profile

    def risk_history(self, user_id: str) -> list[dict]:
        """按时间顺序返回该用户的历史测评（level/score/created_at）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT level, score, created_at FROM risk_history WHERE user_id=? ORDER BY created_at",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def record_audit(
        self,
        *,
        request_id: str,
        user_id: str,
        intent: str | None = None,
        final_len: int = 0,
        degraded: bool = False,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO audit_log(request_id, user_id, intent, final_len, degraded, created_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    request_id,
                    user_id,
                    intent,
                    final_len,
                    1 if degraded else 0,
                    datetime.now().isoformat(),
                ),
            )

    def list_audit(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        if user_id:
            rows = self._connect().execute(
                "SELECT * FROM audit_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = self._connect().execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_holding(self, user_id: str, holding: Holding) -> UserProfile:
        profile = self.get_profile(user_id) or UserProfile(user_id=user_id)
        profile.holdings = [h for h in profile.holdings if h.symbol != holding.symbol] + [holding]
        self.upsert_profile(profile)
        return profile

    def remove_holding(self, user_id: str, symbol: str) -> UserProfile:
        profile = self.get_profile(user_id) or UserProfile(user_id=user_id)
        profile.holdings = [h for h in profile.holdings if h.symbol != symbol]
        self.upsert_profile(profile)
        return profile

    def add_fact(self, user_id: str, fact: str) -> UserProfile:
        profile = self.get_profile(user_id) or UserProfile(user_id=user_id)
        if fact not in profile.facts:
            profile.facts.append(fact)
        self.upsert_profile(profile)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO memory_notes(user_id, fact, source, created_at) VALUES(?,?,?,?)",
                (user_id, fact, "rule", datetime.now().isoformat()),
            )
        return profile

    def recall_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        embedder=None,
        min_similarity: float = 0.62,
    ) -> list[str]:
        """P8 语义记忆第一版：同义词扩展 + 子串命中（离线、零额外依赖）。

        传入 embedder 时先做向量召回，不足再补关键词结果（混合召回）。
        """
        from advisor.store.recall import score_facts  # 延迟导入避免循环

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fact FROM memory_notes WHERE user_id=? ORDER BY created_at DESC LIMIT 200",
                (user_id,),
            ).fetchall()
        if not rows:
            return []
        facts = [r["fact"] for r in rows]
        result: list[str] = []
        if embedder is not None:
            try:
                query_vec = embedder.embed(query)
                result = self._recall_by_vector(user_id, query_vec, limit, min_similarity)
            except Exception:
                result = []  # embedding 失败不阻塞，回退关键词
        if len(result) < limit:
            scored = score_facts(facts, query)
            for fact, _ in scored:
                if fact not in result:
                    result.append(fact)
                if len(result) >= limit:
                    break
        return result[:limit]

    def save_fact_embedding(self, user_id: str, fact: str, vector: list[float]) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM memory_notes WHERE user_id=? AND fact=?",
                (user_id, fact),
            ).fetchone()
            if row is None:
                return
            conn.execute(
                "INSERT OR REPLACE INTO memory_embeddings(note_id, user_id, vector) VALUES(?,?,?)",
                (row["id"], user_id, json.dumps(vector)),
            )

    def list_unembedded_facts(self) -> list[tuple[str, str]]:
        """存量记忆中没有向量的 (user_id, fact)，供回填脚本使用。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT n.user_id, n.fact FROM memory_notes n "
                "LEFT JOIN memory_embeddings e ON e.note_id = n.id "
                "WHERE e.note_id IS NULL"
            ).fetchall()
        return [(r["user_id"], r["fact"]) for r in rows]

    def _recall_by_vector(
        self,
        user_id: str,
        query_vec: list[float],
        limit: int,
        min_similarity: float,
    ) -> list[str]:
        from advisor.store.embeddings import cosine_similarity

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT n.fact, e.vector FROM memory_embeddings e "
                "JOIN memory_notes n ON n.id = e.note_id WHERE e.user_id=?",
                (user_id,),
            ).fetchall()
        scored = []
        for r in rows:
            sim = cosine_similarity(query_vec, [float(x) for x in json.loads(r["vector"])])
            if sim >= min_similarity:
                scored.append((sim, r["fact"]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [fact for _, fact in scored[:limit]]

    # ---- holdings 冗余表（便于独立查询）----
    def get_holdings(self, user_id: str) -> list[Holding]:
        profile = self.get_profile(user_id)
        return list(profile.holdings) if profile else []

    @staticmethod
    def _sync_holdings(conn: sqlite3.Connection, profile: UserProfile) -> None:
        conn.execute("DELETE FROM holdings WHERE user_id=?", (profile.user_id,))
        now = datetime.now().isoformat()
        conn.executemany(
            "INSERT INTO holdings(user_id, symbol, payload, updated_at) VALUES(?,?,?,?)",
            [
                (profile.user_id, h.symbol, h.model_dump_json(), h.updated_at.isoformat() or now)
                for h in profile.holdings
            ],
        )

    def json_snapshot(self, user_id: str) -> dict:
        """供演示/调试：打印某用户完整画像。"""
        profile = self.get_profile(user_id)
        return json.loads(profile.model_dump_json()) if profile else {}

    def export_user(self, user_id: str) -> dict:
        """导出单个用户的全部数据（画像/持仓/记忆/测评历史/审计），用于备份与迁移。"""
        profile = self.get_profile(user_id)
        if profile is None:
            raise KeyError(f"用户不存在: {user_id}")
        with self._connect() as conn:
            memory = [
                dict(r)
                for r in conn.execute(
                    "SELECT fact, source, created_at FROM memory_notes WHERE user_id=? ORDER BY created_at",
                    (user_id,),
                ).fetchall()
            ]
            audit = [
                dict(r)
                for r in conn.execute(
                    "SELECT intent, final_len, degraded, created_at FROM audit_log WHERE user_id=? ORDER BY created_at",
                    (user_id,),
                ).fetchall()
            ]
        return {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "profile": json.loads(profile.model_dump_json()),
            "holdings": [json.loads(h.model_dump_json()) for h in profile.holdings],
            "memory": memory,
            "risk_history": self.risk_history(user_id),
            "audit_log": audit,
        }

    def export_all_users(self) -> dict:
        return {"exported_at": datetime.now().isoformat(), "users": [self.export_user(u) for u in self.list_user_ids()]}

    def backup_user(self, user_id: str) -> str:
        """删除前备份到 data/backups/{user_id}_{ts}.json，返回文件路径。"""
        backup_dir = Path(self.db_path).parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        path = backup_dir / f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(self.export_user(user_id), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
