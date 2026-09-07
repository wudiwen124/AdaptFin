"""为存量记忆补向量（启用 embedder 后执行一次即可）。

用法：python scripts/embed_backfill.py
"""

from advisor.config import load_settings
from advisor.store import ProfileStore
from advisor.store.embeddings import build_embedder


def main() -> None:
    settings = load_settings()
    embedder = build_embedder(settings)
    if embedder is None:
        print("embedder 未启用（ADVISOR_MEMORY_EMBEDDER 需为 siliconflow/zhipu 且有 key）")
        return
    store = ProfileStore(settings.store.db_path)
    pending = store.list_unembedded_facts()
    if not pending:
        print("没有需要回填的记忆")
        return
    done = 0
    for user_id, fact in pending:
        try:
            store.save_fact_embedding(user_id, fact, embedder.embed(fact))
            done += 1
        except Exception as exc:
            print(f"失败: {user_id} | {exc}")
    print(f"回填完成: {done}/{len(pending)}")


if __name__ == "__main__":
    main()
