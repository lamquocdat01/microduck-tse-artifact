r"""Dựng file làm mù cho vòng gán nhãn thứ hai (đo agreement test–retest).

    python scripts\make_blind_set.py

Sinh hai file:

- `docs/benchmark/lookup_set_vi_blind.csv`      — CHỈ `id_an` và `cau_hoi`, đã xáo
- `docs/benchmark/lookup_set_vi_blind_key.csv`  — bảng ánh xạ, **ĐỪNG đưa chủ nhân xem**

## Vì sao phải làm mù

Vòng hai do **cùng một người** gán, nên mọi gợi nhớ đều làm agreement đẹp lên một cách
giả tạo. Ba thứ bị gỡ:

- **nhãn cũ** (`needs_lookup`, `needs_premise`, `borderline`) — hiển nhiên;
- **`fact_type`** — nó gần như là đáp án: `fast-changing` kéo thẳng tới "cần tra";
- **thứ tự cũ và id gốc** — thứ tự cũng là một gợi nhớ, và `vi-fast-003` thì tự khai loại.

## Gọi đúng tên trong bài

Đây là **intra-rater (test–retest) reliability**, **KHÔNG** phải inter-rater — cùng một
người gán hai lượt. Hai chữ ấy khác nhau về ý nghĩa và không được đổi cho nhau vì chữ kia
nghe oai hơn.

Hạt giống ghim cứng để dựng lại được đúng file này.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "docs" / "benchmark"
NGUON = BENCH / "lookup_set_v1.jsonl"
MU = BENCH / "lookup_set_vi_blind.csv"
KHOA = BENCH / "lookup_set_vi_blind_key.csv"

HAT_GIONG = 20260910


def main() -> int:
    rows = [json.loads(l) for l in NGUON.read_text(encoding="utf-8").splitlines() if l.strip()]
    vi = [r for r in rows if r["lang"] == "vi"]
    if not vi:
        raise SystemExit("Không có câu tiếng Việt nào trong bộ nguồn.")

    thu_tu = list(range(len(vi)))
    random.Random(HAT_GIONG).shuffle(thu_tu)

    mu_rows, khoa_rows = [], []
    for moi, cu in enumerate(thu_tu, start=1):
        r = vi[cu]
        id_an = f"Q{moi:03d}"
        mu_rows.append({"id_an": id_an, "cau_hoi": r["question"]})
        khoa_rows.append({"id_an": id_an, "id_goc": r["id"], "block": r["block"],
                          "fact_type": r.get("fact_type"),
                          "needs_lookup_vong1": r.get("needs_lookup"),
                          "needs_premise_vong1": r.get("needs_premise"),
                          "borderline_vong1": r.get("borderline")})

    with MU.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id_an", "cau_hoi", "needs_lookup_vong2", "ghi_chu"])
        w.writeheader()
        for r in mu_rows:
            w.writerow({**r, "needs_lookup_vong2": "", "ghi_chu": ""})

    with KHOA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(khoa_rows[0]))
        w.writeheader()
        w.writerows(khoa_rows)

    print(f"Ghi {len(mu_rows)} câu (đã xáo, hạt giống {HAT_GIONG}):")
    print(f"  {MU}          <- đưa chủ nhân gán")
    print(f"  {KHOA}   <- KHÔNG đưa chủ nhân xem")
    print("\nCột cần điền: `needs_lookup_vong2` — ghi 1 (cần tra) hoặc 0 (không cần).")
    print("Câu khối B (tiền đề sai) vẫn nằm trong file; nhãn vòng 1 của chúng là rỗng,")
    print("nên khi tính kappa sẽ tự loại — không cần chủ nhân biết câu nào thuộc khối nào.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
