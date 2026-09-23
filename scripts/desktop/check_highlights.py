r"""Đếm ký tự Highlights — Elsevier: 3–5 gạch đầu dòng, TỐI ĐA 85 ký tự mỗi dòng.

    python scripts\check_highlights.py

Đếm **kể cả dấu cách**, và đếm **bằng máy**. Đếm bằng mắt là cách hỏng: 85 và 87 nhìn
giống hệt nhau, và cổng nộp thì không.

Đọc `paper/HIGHLIGHTS.md`. Ứng viên nằm dưới mục `## Ứng viên`, dòng chọn nằm dưới
`## Đã chọn`. Soạn 8–10 rồi chọn 5 — viết đúng 5 rồi cố nhét là cách làm ra năm câu tệ.

⚠ Con số 85 là **của Elsevier nói chung** và đã xác minh cho JSA. ESWA/IP&M chưa xác minh
riêng; xem `[[XÁC MINH]]` trong HIGHLIGHTS.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
HL = REPO / "paper" / "HIGHLIGHTS.md"
GIOI_HAN = 85
TOI_THIEU, TOI_DA = 3, 5


def lay(text: str, tieu_de: str) -> list[str]:
    m = re.search(rf"^##\s*{re.escape(tieu_de)}\s*$(.*?)(?=^##\s|\Z)", text,
                  re.M | re.S)
    if not m:
        return []
    ra = []
    for line in m.group(1).split("\n"):
        s = line.strip()
        if s.startswith("- "):
            # bỏ đánh dấu markdown khi đếm: cổng nộp nhận văn bản thuần
            noi_dung = re.sub(r"\*\*|`|\*", "", s[2:]).strip()
            if noi_dung:
                ra.append(noi_dung)
    return ra


def bang(ten: str, ds: list[str]) -> int:
    if not ds:
        print(f"\n## {ten}: (chưa có)")
        return 0
    print(f"\n## {ten} — {len(ds)} dòng")
    qua = 0
    for i, s in enumerate(ds, 1):
        n = len(s)
        dau = "OK " if n <= GIOI_HAN else "QUÁ"
        if n > GIOI_HAN:
            qua += 1
        print(f"  {dau} {n:>3}/{GIOI_HAN}  {s}")
    return qua


def main() -> int:
    enable_utf8_console()   # console Windows mac dinh la cp1258, in tieng Viet la vo
    if not HL.exists():
        print(f"Chưa có {HL}")
        return 2
    text = HL.read_text(encoding="utf-8")
    ung_vien = lay(text, "Ứng viên")
    da_chon = lay(text, "Đã chọn")

    qua_uv = bang("Ứng viên", ung_vien)
    qua_ch = bang("Đã chọn", da_chon)

    print("\n" + "=" * 60)
    loi = []
    if len(ung_vien) < 8:
        loi.append(f"chỉ có {len(ung_vien)} ứng viên, cần 8–10 để còn chỗ mà chọn")
    if da_chon and not (TOI_THIEU <= len(da_chon) <= TOI_DA):
        loi.append(f"đã chọn {len(da_chon)} dòng, phải trong khoảng {TOI_THIEU}–{TOI_DA}")
    if qua_ch:
        loi.append(f"{qua_ch} dòng ĐÃ CHỌN vượt {GIOI_HAN} ký tự")
    if not da_chon:
        loi.append("chưa chọn dòng nào (mục '## Đã chọn' trống)")

    if qua_uv:
        print(f"  ({qua_uv} ứng viên vượt {GIOI_HAN} — chỉ là ứng viên, không chặn)")
    if loi:
        for l in loi:
            print(f"  !! {l}")
        return 1
    print(f"  ĐẠT: {len(da_chon)} dòng, đều ≤ {GIOI_HAN} ký tự.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
