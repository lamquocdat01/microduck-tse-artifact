r"""Dựng bộ thử định tuyến tra cứu: FreshQA (tiếng Anh) + bộ Việt native.

    python scripts\build_lookup_set.py --freshqa <freshqa.csv>
    python scripts\build_lookup_set.py --download          # tải thẳng từ Google Sheets

Giao thức gán nhãn: `docs/benchmark/LABELING-PROTOCOL.md` — viết TRƯỚC khi gán.
Đầu ra: `docs/benchmark/lookup_set_v1.jsonl`.

FreshQA: Vu et al., *FreshLLMs*, Findings of ACL 2024, repo `freshllms/freshqa`,
Apache-2.0. Bảng cập nhật hằng tuần nên `--download` lấy bản MỚI NHẤT — vì thế mỗi
dòng đều mang `labeled_at`, và bộ đã dựng thì đừng dựng lại đè lên.

Lấy mẫu TẤT ĐỊNH (`random.Random(SEED)`), để dựng lại từ cùng một bản CSV ra đúng
cùng một bộ. Cùng lý do với `temperature=0` ở tầng STT (ADR-007): một bộ dữ liệu
không tái lập được thì mọi con số đo trên nó cũng không.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import enable_utf8_console
from scripts.lookup_set_vi import (
    FALSE_PREMISE_VI,
    FAST_CHANGING_VI,
    NEVER_CHANGING_VI,
    SLOW_CHANGING_VI,
)

REPO_DIR = Path(__file__).resolve().parents[2]
OUT = REPO_DIR / "docs" / "benchmark" / "lookup_set_v1.jsonl"
SHEET = ("https://docs.google.com/spreadsheets/d/"
         "1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM/export?format=csv")
SEED = 20260909

# Khối A, theo LABELING-PROTOCOL §4. Mỗi ngôn ngữ một cột như nhau.
QUOTA = {"never-changing": 25, "fast-changing": 15, "slow-changing": 10}
PREMISE_QUOTA = 10                       # khối B, mỗi ngôn ngữ

# LABELING-PROTOCOL §3.1
NEEDS_LOOKUP = {"never-changing": False, "slow-changing": True, "fast-changing": True}


def doc_freshqa(path: Path) -> list[dict]:
    """Bảng có hai dòng cảnh báo trước dòng tiêu đề — bỏ chúng đi."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("id,split,question"))
    return list(csv.DictReader(lines[start:]))


def tai_freshqa(path: Path) -> None:
    import urllib.request

    print(f"Tải FreshQA từ Google Sheets → {path}")
    with urllib.request.urlopen(SHEET, timeout=60) as response:
        path.write_bytes(response.read())


def dung_khoi_a_en(rows: list[dict], rng: random.Random) -> list[dict]:
    """Khối A tiếng Anh: tiền đề ĐÚNG, lấy mẫu theo hạn ngạch từng `fact_type`."""
    ra: list[dict] = []
    for fact_type, quota in QUOTA.items():
        ung_vien = [r for r in rows
                    if r["fact_type"] == fact_type
                    and r["false_premise"].strip().upper() == "FALSE"
                    and r["question"].strip()]
        if len(ung_vien) < quota:
            raise SystemExit(f"FreshQA chỉ có {len(ung_vien)} câu {fact_type} tiền đề đúng, "
                             f"cần {quota}")
        for i, r in enumerate(sorted(rng.sample(ung_vien, quota), key=lambda x: x["id"])):
            ra.append(dong(
                id=f"en-{fact_type.split('-')[0]}-{i + 1:03d}",
                lang="en", question=r["question"].strip(),
                fact_type=fact_type, needs_premise=False, block="A",
                source="freshqa", source_id=r["id"], annotator="freshqa-authors",
            ))
    return ra


def dung_khoi_b_en(rows: list[dict], rng: random.Random) -> list[dict]:
    """Khối B tiếng Anh: tiền đề SAI, rải trên cả ba `fact_type`."""
    ung_vien = [r for r in rows
                if r["false_premise"].strip().upper() == "TRUE" and r["question"].strip()]
    if len(ung_vien) < PREMISE_QUOTA:
        raise SystemExit(f"FreshQA chỉ có {len(ung_vien)} câu tiền đề sai")
    # Rải đều ba fact_type thay vì bốc ngẫu nhiên cả cụm: bốc thẳng thì hay lệch về
    # nhóm đông nhất, và ta mất mất khả năng nói "tiền đề sai ở mọi mức động học".
    theo_loai: dict[str, list[dict]] = {}
    for r in ung_vien:
        theo_loai.setdefault(r["fact_type"], []).append(r)
    chon: list[dict] = []
    vong = 0
    while len(chon) < PREMISE_QUOTA:
        for loai in sorted(theo_loai):
            if len(chon) >= PREMISE_QUOTA:
                break
            con = [r for r in theo_loai[loai] if r not in chon]
            if con:
                chon.append(rng.choice(con))
        vong += 1
        if vong > PREMISE_QUOTA:
            break
    return [dong(id=f"en-fp-{i + 1:03d}", lang="en", question=r["question"].strip(),
                 fact_type=r["fact_type"], needs_premise=True, block="B",
                 source="freshqa", source_id=r["id"], annotator="freshqa-authors")
            for i, r in enumerate(sorted(chon, key=lambda x: x["id"]))]


def dung_vi() -> list[dict]:
    ra: list[dict] = []
    nguon = [("never-changing", NEVER_CHANGING_VI),
             ("fast-changing", FAST_CHANGING_VI),
             ("slow-changing", SLOW_CHANGING_VI)]
    for fact_type, cau_hoi in nguon:
        if len(cau_hoi) != QUOTA[fact_type]:
            raise SystemExit(f"bộ Việt {fact_type} có {len(cau_hoi)} câu, "
                             f"giao thức đòi {QUOTA[fact_type]}")
        for i, q in enumerate(cau_hoi):
            ra.append(dong(id=f"vi-{fact_type.split('-')[0]}-{i + 1:03d}",
                           lang="vi", question=q, fact_type=fact_type,
                           needs_premise=False, block="A",
                           source="microduck-vi", source_id="",
                           annotator="claude-opus-5-20260909"))
    if len(FALSE_PREMISE_VI) != PREMISE_QUOTA:
        raise SystemExit(f"bộ Việt tiền đề sai có {len(FALSE_PREMISE_VI)} câu, "
                         f"giao thức đòi {PREMISE_QUOTA}")
    for i, (q, fact_type) in enumerate(FALSE_PREMISE_VI):
        ra.append(dong(id=f"vi-fp-{i + 1:03d}", lang="vi", question=q,
                       fact_type=fact_type, needs_premise=True, block="B",
                       source="microduck-vi", source_id="",
                       annotator="claude-opus-5-20260909"))
    return ra


def dong(**kw) -> dict:
    """Một dòng theo LABELING-PROTOCOL §8."""
    fact_type, needs_premise = kw["fact_type"], kw["needs_premise"]
    return {
        "id": kw["id"],
        "lang": kw["lang"],
        "question": kw["question"],
        # §3.3: tiền đề sai thì KHÔNG chấm định tuyến — hành vi đúng là phản bác,
        # mà vịt gắn thêm [lookup] để nói "cần kiểm chứng" cũng không sai.
        "needs_lookup": None if needs_premise else NEEDS_LOOKUP[fact_type],
        "needs_premise": needs_premise,
        "borderline": fact_type == "slow-changing" and not needs_premise,
        "fact_type": fact_type,
        "source": kw["source"],
        "source_id": kw["source_id"],
        "annotator": kw["annotator"],
        "labeled_at": date.today().isoformat(),
        "block": kw["block"],
    }


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--freshqa", default=None, help="file CSV đã tải sẵn")
    parser.add_argument("--download", action="store_true", help="tải bản mới nhất")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    csv_path = Path(args.freshqa) if args.freshqa else (REPO_DIR / "docs" / "benchmark" / "freshqa.csv")
    if args.download or not csv_path.exists():
        tai_freshqa(csv_path)

    rows = doc_freshqa(csv_path)
    print(f"FreshQA: {len(rows)} câu — "
          f"{dict(Counter(r['fact_type'] for r in rows))}, "
          f"tiền đề sai {sum(1 for r in rows if r['false_premise'].strip().upper() == 'TRUE')}")

    rng = random.Random(SEED)
    bo = dung_khoi_a_en(rows, rng) + dung_khoi_b_en(rows, rng) + dung_vi()

    out = Path(args.out) if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in bo:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    khoi_a = [r for r in bo if r["block"] == "A"]
    print(f"\nGhi {len(bo)} câu vào {out}")
    print(f"  khối A (chấm [lookup]): {len(khoi_a)} — "
          f"{sum(1 for r in khoi_a if r['needs_lookup'])} cần tra / "
          f"{sum(1 for r in khoi_a if r['needs_lookup'] is False)} không")
    print(f"  khối B (chấm [premise]): {sum(1 for r in bo if r['block'] == 'B')}")
    print(f"  ranh giới (slow-changing): {sum(1 for r in bo if r['borderline'])}")
    for lang in ("en", "vi"):
        con = [r for r in bo if r["lang"] == lang]
        print(f"  {lang}: {len(con)} — {dict(Counter(r['fact_type'] for r in con))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
