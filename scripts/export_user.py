"""用户数据导出 CLI。

用法：
    python scripts/export_user.py --user demo_user --out data/backups/demo.json
    python scripts/export_user.py --all --out data/backups/all.json
"""

import argparse
import json
from pathlib import Path

from advisor.config import load_settings
from advisor.store import ProfileStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    store = ProfileStore(load_settings().store.db_path)

    if args.all:
        data = store.export_all_users()
    elif args.user:
        data = store.export_user(args.user)
    else:
        raise SystemExit("需要 --user 或 --all")
    out = args.out or Path(f"data/backups/{'all' if args.all else args.user}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导出: {out}")


if __name__ == "__main__":
    main()
