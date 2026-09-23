r"""Tải audio FLEURS cho đúng 50 câu thăm dò × 4 ngôn ngữ. Chỉ cần cho F1 = ASR.

    ..\..\desktop\.venv\Scripts\python.exe scripts\build_fleurs.py

FLEURS không cho tải lẻ từng WAV — audio đóng thành `<split>.tar.gz` một cục. Nên
script phải chảy qua cả tar nhưng chỉ GHI ra đĩa 200 file cần dùng, rồi bỏ phần đuôi.

    tải về   ~732 MB (dev của bốn ngôn ngữ)
    giữ lại  ~50 MB

Chạy lại được: file đã có thì bỏ qua, đứt mạng thì chạy lại tiếp phần thiếu.
KHÔNG chạy nếu chỉ định làm phần oracle — phần oracle không cần một byte audio nào.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import fleurs                               # noqa: E402

DATA = ROOT / "data"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--n-probe", type=int, default=50)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--langs", nargs="*", default=list(fleurs.LANGUAGES))
    parser.add_argument("--meta-only", action="store_true", help="chỉ TSV, không audio")
    args = parser.parse_args()

    fleurs.download_metadata(DATA / "fleurs_meta")
    table = fleurs.FleursText(DATA / "fleurs_meta", splits=(args.split,))
    selection = fleurs.select(table, n_probe=args.n_probe, max_depth=args.max_depth)

    manifest = {
        **selection.as_dict(),
        "split": args.split,
        "counts": table.counts(),
        "probe_texts": {
            sid: {lang: table.text(sid, lang) for lang in fleurs.LANGUAGES}
            for sid in selection.probe_ids
        },
        "history_texts": {
            sid: {lang: table.text(sid, lang) for lang in fleurs.LANGUAGES}
            for sid in sorted(selection.history_ids)
        },
    }
    out = DATA / "selection.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ghi {out}: {len(selection.probe_ids)} câu thăm dò, "
          f"{len(selection.history_ids)} câu lịch sử, seed {selection.seed}")

    if args.meta_only:
        print("--meta-only: dừng, không tải audio.")
        return 0

    paths = fleurs.fetch_audio(
        table, selection.probe_ids, DATA / "audio",
        langs=tuple(args.langs), split=args.split,
    )
    missing = [k for k, p in paths.items() if not p.exists()]
    print(f"{len(paths) - len(missing)}/{len(paths)} WAV có trên đĩa"
          + (f", THIẾU {len(missing)}" if missing else ""))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
