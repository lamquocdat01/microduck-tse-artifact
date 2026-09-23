# -*- coding: utf-8 -*-
r"""Sáu cổng chạy trên CÂY SẮP ĐẨY, ngay trước `git add` — việc 144, đợt 27m.

    python scripts\check_goi_truoc_day.py --goi paper/data-package/build

## Vì sao kiểm lại ở đây khi `make_package.py` đã kiểm

Vì hai thứ khác nhau. `make_package` kiểm **nguồn** rồi mới ghi; cổng này kiểm **thứ thật sự nằm
trên đĩa sắp đẩy đi**. Giữa hai thời điểm ấy có một bước biến đổi (băm S2, nén gzip) và một bước
ghi MANIFEST — đúng khoảng mà một hash lệch sẽ không ai thấy cho tới khi C7 đỏ, lúc đã public.

Đẩy lên GitHub public là việc **không rút lại được**: commit vẫn nằm trong lịch sử kể cả sau khi
xoá file. Nên cổng cuối phải đứng ở chỗ cuối.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "desktop"))
try:
    from config import enable_utf8_console
except Exception:
    def enable_utf8_console() -> None:
        pass

BS = chr(92)
BI_MAT = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "khoá Google API"),
    (re.compile(r"(?<![A-Za-z0-9_\-])sk-[A-Za-z0-9]{20,}"), "khoá kiểu OpenAI"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{16,}"), "gán bí mật"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_.]{20,}"), "header Bearer"),
]
RIENG = [
    (re.compile(r"[A-Za-z]:" + re.escape(BS) + r"THS|[A-Za-z]:/THS"), "đường dẫn máy tác giả"),
    (re.compile(r"[Cc]:[" + re.escape(BS) + r"/]Users[" + re.escape(BS) + r"/]"), "C:/Users"),
    (re.compile(r"\b(?:DESKTOP|LAPTOP)-[A-Z0-9]{5,}\b"), "tên máy Windows"),
]
DUOI_VAN_BAN = {".jsonl", ".json", ".md", ".py", ".csv", ".txt", ".yaml", ".yml", ".cff"}
TRAN = 95 * 1024 * 1024


def bam(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for k in iter(lambda: f.read(1 << 20), b""):
            h.update(k)
    return h.hexdigest()


def main() -> int:
    enable_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goi", default=str(REPO / "paper/data-package/build"))
    ap.add_argument("--s3-manifest", default=str(REPO / "docs/benchmark/M1_s3_manifest.json"))
    a = ap.parse_args()
    goi = Path(a.goi).resolve()
    if not goi.exists():
        print(f"KHÔNG CÓ cây gói: {goi}")
        return 2
    files = [f for f in sorted(goi.rglob("*")) if f.is_file()]
    print(f"Cây sắp đẩy: {goi}\n{len(files)} file\n")
    do: list[str] = []

    # 1 + 2 --------------------------------------------------------------
    n_bi_mat = n_rieng = 0
    for f in files:
        if f.suffix.lower() not in DUOI_VAN_BAN:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        for rx, ten in BI_MAT:
            for m in rx.finditer(t):
                n_bi_mat += 1
                do.append(f"BÍ MẬT [{ten}] {f.relative_to(goi)}")
        for rx, ten in RIENG:
            for m in rx.finditer(t):
                n_rieng += 1
                do.append(f"ĐƯỜNG DẪN RIÊNG [{ten}] {f.relative_to(goi)}: {m.group(0)[:60]}")
    print(f"  1. bí mật                 {n_bi_mat:>6}      <-- mục tiêu 0")
    print(f"  2. đường dẫn riêng        {n_rieng:>6}      <-- mục tiêu 0")

    # 3 ------------------------------------------------------------------
    wav = [f for f in files if f.suffix.lower() == ".wav"]
    ngoai = [f for f in wav if "data/stt/s3" not in f.relative_to(goi).as_posix()]
    man = json.loads(Path(a.s3_manifest).read_text(encoding="utf-8"))
    nhan = {m["sha256"] for m in man["files"] if m.get("accepted")}
    lech = [f for f in wav if bam(f) not in nhan]
    cho = man["tong"]["nhan"]
    print(f"  3. .wav                   {len(wav):>6}      <-- chờ {cho}, ngoài data/stt/s3 {len(ngoai)}, "
          f"hash không khớp manifest {len(lech)}")
    if len(wav) != cho or ngoai or lech:
        do.append(f"WAV: {len(wav)} file (chờ {cho}), {len(ngoai)} sai chỗ, {len(lech)} sai hash")

    # 4 ------------------------------------------------------------------
    to = [f for f in files if f.stat().st_size >= TRAN]
    print(f"  4. file ≥ 95 MB           {len(to):>6}      <-- mục tiêu 0 (trần GitHub 100 MB)")
    for f in to:
        do.append(f"QUÁ TO {f.relative_to(goi)}: {f.stat().st_size/1e6:.1f} MB")

    # 5 ------------------------------------------------------------------
    m1 = goi / "measurements/benchmark/M1_20260916_v1.jsonl"
    n_tho = n_hash = 0
    if m1.exists():
        for line in m1.read_bytes().splitlines():
            if not line.strip():
                continue
            r = json.loads(line.decode("utf-8"))
            tid = r.get("task_id", "")
            if "|" not in tid or not tid.split("|")[1].startswith("wild_"):
                continue
            pl = r.get("payload") or {}
            n_tho += "hypothesis" in pl
            n_hash += "hypothesis_sha256" in pl
    print(f"  5. S2 transcript thô      {n_tho:>6}      <-- quyết định 27l: giữ thô (băm {n_hash})")
    if n_tho == 0:
        do.append("S2: không còn chuỗi thô — trái quyết định 27l")

    # 6 ------------------------------------------------------------------
    mf = goi / "MANIFEST.json"
    thieu_dong = thieu_file = sai_hash = 0
    if not mf.exists():
        do.append("THIẾU MANIFEST.json")
    else:
        ke = json.loads(mf.read_text(encoding="utf-8"))["files"]
        trong_mf = {x["path"] for x in ke}
        # Loại file meta Ở GỐC gói, không loại theo TÊN: `measurements/baseline/README.md` là dữ
        # liệu, có dòng trong MANIFEST, và lọc theo tên làm nó thành "thừa dòng" oan.
        META = {"MANIFEST.json", "MANIFEST.md", "README.md", "EXCLUDED.md", "LICENSE-DATA.txt"}
        tren_dia = {f.relative_to(goi).as_posix() for f in files
                    if not (f.parent == goi and f.name in META)}
        thieu_dong = len(tren_dia - trong_mf)
        thieu_file = len(trong_mf - tren_dia)
        for x in ke:
            f = goi / x["path"]
            if f.exists() and bam(f) != x["sha256"]:
                sai_hash += 1
        for t in sorted(tren_dia - trong_mf)[:5]:
            do.append(f"MANIFEST thiếu dòng cho: {t}")
        for t in sorted(trong_mf - tren_dia)[:5]:
            do.append(f"MANIFEST có dòng mà không có file: {t}")
    print(f"  6. MANIFEST               {len(ke) if mf.exists() else 0:>6} dòng  <-- thiếu dòng {thieu_dong}, "
          f"thừa dòng {thieu_file}, sai hash {sai_hash}")
    if sai_hash:
        do.append(f"MANIFEST: {sai_hash} dòng có hash KHÁC file trên đĩa")

    print()
    if do:
        print(f"CHƯA ĐẠT — {len(do)} vấn đề, KHÔNG đẩy:")
        for x in do[:20]:
            print("   " + x)
        return 1
    print("ĐẠT: sáu cổng xanh trên cây sắp đẩy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
