"""Đánh index shared/knowledge/*.md bằng embeddings CPU (bỏ qua private/).

    python scripts\build_index.py            # đánh lại nếu tài liệu đổi
    python scripts\build_index.py --force    # đánh lại bằng mọi giá
    python scripts\build_index.py --ask "anh Đạt làm ở đâu?"   # thử truy hồi

app.py tự gọi build() lúc khởi động; script này để soi index và đo chất lượng.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.knowledge import Knowledge  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="bỏ cache, mã hoá lại từ đầu")
    parser.add_argument("--ask", default=None, help="thử một câu hỏi, in top-k đoạn")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    cfg = Config.load()
    knowledge = Knowledge(cfg.knowledge_dir, cfg.knowledge_index, top_k=args.top_k)

    started = time.perf_counter()
    count = knowledge.build(force=args.force)
    print(f"{count} đoạn từ {cfg.knowledge_dir}  ({time.perf_counter() - started:.1f}s)")
    print(f"cache: {cfg.knowledge_index}")
    for chunk in knowledge.chunks:
        head = f" › {chunk.heading}" if chunk.heading else ""
        print(f"  [{chunk.source}{head}] {chunk.text[:70].replace(chr(10), ' ')}...")

    if args.ask:
        started = time.perf_counter()
        hits = knowledge.search(args.ask)
        print(f"\n'{args.ask}'  ({(time.perf_counter() - started) * 1000:.0f} ms)")
        for chunk, score in hits:
            print(f"  {score:.3f}  [{chunk.source}] {chunk.text[:80].replace(chr(10), ' ')}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
