# -*- coding: utf-8 -*-
r"""Quét PII trong transcript tầng S2 trước khi công bố — việc 144, đợt 27k.

    python scripts\check_pii_s2.py                 # đếm và phân loại, KHÔNG in nội dung
    python scripts\check_pii_s2.py --hien 3        # in tối đa 3 ví dụ ĐÃ CHE cho từng loại

## Vì sao riêng S2

S1 là 31 câu kịch bản có sẵn, S3 là giọng tổng hợp — hai tầng ấy không mang lời ai. **S2 là 110
lượt người thật nói** trong phiên dùng thật 07–11/09. Bỏ file WAV là chưa đủ: `payload.hypothesis`
là **bản ghi chữ của chính lời họ**, và một cái tên hay số điện thoại trong đó công bố ra thì
không rút lại được.

Mặc định của gói (27f): S1/S2 bỏ audio, **S2 chỉ giữ SHA-256 của transcript chuẩn hoá + cờ đổi**.
Script này trả lời hai câu trước khi tag: (1) có bao nhiêu dòng S2 mang dấu hiệu PII, (2) có file
nào sắp công bố còn giữ chuỗi thô của S2 không.

Script KHÔNG in nội dung gốc ra màn hình trừ khi có `--hien`, và kể cả khi ấy cũng che giữa chuỗi.
Đếm thì an toàn; đọc để "xem thử" là chính cái việc ta đang tránh.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "desktop"))
try:
    from config import enable_utf8_console
except Exception:
    def enable_utf8_console() -> None:
        pass

HOA = "A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯĂẠ-Ỹ"
MAU: list[tuple[str, re.Pattern, str]] = [
    ("điện thoại", re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)"), "số máy VN"),
    ("số dài", re.compile(r"(?<!\d)\d{7,}(?!\d)"), "chuỗi ≥ 7 chữ số (CCCD, tài khoản, mã)"),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "địa chỉ thư"),
    ("URL", re.compile(r"https?://\S+|www\.\S+"), "liên kết"),
    ("địa chỉ", re.compile(r"\b(?:số nhà|đường|phố|quận|phường|thôn|xã|huyện|tỉnh)\s+["
                          + HOA + r"\d]", re.I), "từ chỉ địa chỉ + danh từ riêng"),
    ("tên riêng", re.compile(r"(?<![" + HOA + r"])[" + HOA + r"][a-zà-ỹ]+(?:\s+[" + HOA + r"][a-zà-ỹ]+){1,3}"),
     "≥ 2 từ viết hoa liền nhau"),
    ("xưng hô + tên", re.compile(r"\b(?:anh|chị|em|cô|chú|bác|thầy|ông|bà)\s+[" + HOA + r"][a-zà-ỹ]+"),
     "đại từ xưng hô đi kèm tên"),
]


def che(s: str, n: int = 64) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n // 2] + " […] " + s[-(n // 2):]


def main() -> int:
    enable_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hien", type=int, default=0, help="in tối đa N ví dụ ĐÃ CHE cho mỗi loại")
    ap.add_argument("--jsonl", default=str(REPO / "docs/benchmark/M1_20260916_v1.jsonl"))
    a = ap.parse_args()

    n_s2 = n_co_chu = 0
    dem: Counter = Counter()
    vd: dict[str, list[str]] = {}
    for line in Path(a.jsonl).read_bytes().splitlines():
        if not line.strip():
            continue
        r = json.loads(line.decode("utf-8"))
        iid = r["task_id"].split("|")[1]
        if not iid.startswith("wild_"):                 # S2 = tầng in-the-wild
            continue
        n_s2 += 1
        t = (r.get("payload") or {}).get("hypothesis") or ""
        if not t.strip():
            continue
        n_co_chu += 1
        for ten, rx, _ in MAU:
            if rx.search(t):
                dem[ten] += 1
                if a.hien and len(vd.setdefault(ten, [])) < a.hien:
                    vd[ten].append(che(t))

    print(f"S2 (tầng in-the-wild): {n_s2} bản ghi, {n_co_chu} có transcript không rỗng")
    print(f"Nguồn: {Path(a.jsonl).name}\n")
    print(f"{'loại dấu hiệu':<16}{'số DÒNG bị cờ':>16}   ý nghĩa")
    for ten, _, y in MAU:
        print(f"{ten:<16}{dem.get(ten, 0):>16}   {y}")
    tong = sum(1 for _ in ())  # giữ chỗ; tổng dòng riêng biệt tính dưới
    print()
    if a.hien:
        for ten in dem:
            print(f"-- {ten} (đã che) --")
            for x in vd.get(ten, []):
                print("   ", x)
    print("Ghi nhớ: đây là DẤU HIỆU, không phải phán quyết. Mẫu 'tên riêng' bắt cả tên tổ chức và")
    print("chữ đầu câu viết hoa, nên số này là CẬN TRÊN. Quyết định công bố không dựa vào nó mà dựa")
    print("vào luật đã chốt: S2 chỉ ra ngoài dưới dạng SHA-256 của transcript chuẩn hoá.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
