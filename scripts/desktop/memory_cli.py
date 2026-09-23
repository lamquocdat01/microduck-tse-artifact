r"""Xem và sửa ký ức của vịt trong shared/memory/memory.v1.json.

    python scripts\memory_cli.py                      # in tất cả
    python scripts\memory_cli.py find "cà phê"         # tìm
    python scripts\memory_cli.py forget "cà phê"       # xoá theo mô tả
    python scripts\memory_cli.py rm f_003              # xoá theo id (fact hoặc habit)
    python scripts\memory_cli.py add "Anh Đạt thích cà phê đậm"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.memory import HABIT_THRESHOLD, Memory  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402


def show(memory: Memory, query: str = "") -> None:
    facts = memory.recall(query, limit=100)
    print(f"\nFACTS ({len(facts)}/{len(memory.facts)})")
    if not facts:
        print("  (trống)")
    for fact in facts:
        print(f"  {fact.id}  c={fact.confidence:.2f}  n={fact.evidence_count}  [{fact.lang}]  {fact.text}")
        print(f"        nhớ {fact.created_at[:16]} · xác nhận gần nhất {fact.last_confirmed[:16]} · {fact.source}")

    print(f"\nHABITS ({len(memory.habits)})   >= {HABIT_THRESHOLD} mới được chèn vào prompt")
    if not memory.habits:
        print("  (trống)")
    for habit in sorted(memory.habits, key=lambda h: -h.confidence):
        mark = "*" if habit.confidence >= HABIT_THRESHOLD else " "
        where = ", ".join(f"{k}={v}" for k, v in habit.context.items() if v)
        print(f" {mark}{habit.id}  c={habit.confidence:.2f}  n={habit.evidence_count}  "
              f"{habit.pattern}={habit.value}  ({where})")

    if memory.feedback_log:
        print(f"\nFEEDBACK (5 gần nhất / {len(memory.feedback_log)})")
        for entry in memory.feedback_log[-5:]:
            print(f"  {entry['ts'][:16]}  {entry['signal']}  {entry.get('reason', '')}")

    block = memory.priorities_block()
    if block:
        print("\nKhối 'Ưu tiên hiện tại' đang được chèn vào system prompt:")
        print("\n".join(f"  {line}" for line in block.splitlines()))


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="show", choices=["show", "find", "forget", "rm", "add"])
    parser.add_argument("argument", nargs="?", default="")
    args = parser.parse_args()

    cfg = Config.load()
    memory = Memory(cfg.memory_path)
    print(f"{cfg.memory_path}")

    if args.command in {"show", "find"}:
        show(memory, args.argument)
    elif args.command == "forget":
        if not args.argument:
            print("Cần mô tả cần quên."); return 1
        removed = memory.forget(args.argument)
        print(f"Đã xoá {len(removed)} ký ức:" if removed else "Không khớp ký ức nào.")
        for fact in removed:
            print(f"  {fact.id}  {fact.text}")
    elif args.command == "rm":
        target = args.argument
        before = len(memory.facts) + len(memory.habits)
        memory.facts = [f for f in memory.facts if f.id != target]
        memory.habits = [h for h in memory.habits if h.id != target]
        after = len(memory.facts) + len(memory.habits)
        memory.save()
        print(f"Đã xoá {before - after} mục có id {target}.")
    elif args.command == "add":
        if not args.argument:
            print("Cần nội dung cần nhớ."); return 1
        fact = memory.remember(args.argument, source="cli")
        print(f"Đã nhớ {fact.id}: {fact.text}  (c={fact.confidence:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
