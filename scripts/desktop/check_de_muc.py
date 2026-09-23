# -*- coding: utf-8 -*-
r"""Đếm ĐỀ MỤC: mọi `##`/`###`/`####` của nguồn md phải có mặt trong .tex, hoặc được duyệt bỏ.

    python scripts\check_de_muc.py --goc "Submission TSE/latex"
    python scripts\check_de_muc.py --goc "Submission TSE/supplement"

## Vì sao có script này (I-24, 23/09)

Ba regex rời nhau trong `build_tex.py` đều đòi số mục bắt đầu bằng chữ số, nên `## S9.1 …` không
khớp ở đâu cả và **bị bỏ hẳn dòng**. Năm đề mục mục con của Supplement §S9 vắng khỏi mọi bản dựng
suốt sáu ngày, không cổng nào đỏ. Trước đó I-05 đã là đúng lớp lỗi ấy với `## N.M`.

## Vì sao KHÔNG đếm thô

`## Open items` và `## Numbers used in this section, with provenance` là mục làm việc, bộ dựng bỏ
**có chủ ý**; `## IX. TITLE` là đề mục chương do `body.tex` đặt. Đếm thô sẽ đỏ oan ở những chỗ ấy
rồi bị tắt đi, và cổng tắt là cổng không có.

## Vì sao KHÔNG so theo regex số mục

Đó chính là regex đã sai. So theo **văn bản tiêu đề**: tiêu đề nào có trong md mà không xuất hiện
trong `\section/\subsection/\subsubsection` của .tex thì coi là BỊ BỎ, và mọi chỗ bị bỏ phải có
tên trong `de_muc_bo.json` — tức đã có người nhìn và đồng ý. Thêm một chỗ bỏ mới ⇒ đỏ, phải khai
báo mới qua được. Cách này không lặp lại giả định của bộ dựng.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "desktop"))
try:
    from config import enable_utf8_console
except Exception:                                    # chạy rời, không có gói desktop
    def enable_utf8_console() -> None:
        pass

DE_MUC = re.compile(r"^(#{2,4})\s+(.*?)\s*$", re.M)
LENH = re.compile(r"\\(?:sub)*section\*?\{")


def chuan(t: str) -> str:
    """Bỏ đánh dấu inline và số thứ tự đầu đề mục — .tex giữ CHỮ, không giữ số.

    Hai bên viết cùng một tiêu đề bằng hai thứ tiếng đánh dấu: md có `` `fast` ``, .tex có
    `\\texttt{fast}`. Không gỡ cả hai thì cổng báo thiếu ở đúng những đề mục CÓ mã trong tên.
    """
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*([^*]*)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]*)\*", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", t)     # \texttt{x}, \textbf{x} -> x
    t = re.sub(r"\\[a-zA-Z]+\s*", " ", t)                    # lệnh không tham số
    t = t.replace("{", "").replace("}", "")
    # Gạch dài: md viết `—`, .tex viết `---`. Không chuẩn hoá thì mọi tiêu đề có gạch đều báo thiếu.
    for d in ("---", "--", "\u2014", "\u2013"):
        t = t.replace(d, "-")
    # CHỈ cắt token thật sự là SỐ MỤC: có chữ số (`8.1`, `S9.1b`), hoặc số La Mã / một chữ cái
    # có dấu chấm (`IX.`, `A.`). Bản đầu của hàm này cắt `[0-9A-Za-z]+` nên nuốt luôn từ đầu của
    # tiêu đề — "Grounding across the milestones" thành "across the milestones" — và cổng báo
    # thiếu ở mọi file. Đúng kiểu cổng sai làm người ta mất niềm tin vào cổng.
    t = re.sub(r"^\s*(?:[A-Za-z]?\d+(?:\.[0-9A-Za-z]+)*|[IVXL]{1,6}\.|[A-Z]\.)[.)]?\s+", "", t)
    return " ".join(t.split()).lower()


def tieu_de_tex(tex: str) -> list[str]:
    """Tiêu đề trong `\\section{...}` — ĐẾM NGOẶC, không dùng regex không tham lam.

    `\\subsection{The \\texttt{fast} / \\texttt{slow} direction…}` có ngoặc lồng; `\\{(.+?)\\}` dừng ở
    `}` đầu tiên và trả về "The \\texttt{fast", nên cổng báo thiếu đúng những tiêu đề CÓ mã bên trong.
    """
    ra = []
    for m in re.finditer(r"\\(?:sub)*section\*?\{", tex):
        i, sau = m.end(), 1
        while i < len(tex) and sau:
            sau += {"{": 1, "}": -1}.get(tex[i], 0)
            i += 1
        ra.append(tex[m.end():i - 1])
    return ra


def doc_bo(goc: Path) -> tuple[dict[str, list[str]], list[re.Pattern]]:
    """`de_muc_bo.json`: đề mục CỐ Ý không ra bản in, khai theo file hoặc theo mẫu.

    Mẫu (`_mau`) dành cho thứ lặp ở mọi chương — "Numbers used in this section…", "Open items…",
    đề mục chương số La Mã do `body.tex` đặt. Liệt kê từng file cho ba chục chương là danh sách
    không ai đọc, mà danh sách không ai đọc thì không phải là duyệt.
    """
    p = goc / "de_muc_bo.json"
    if not p.exists():
        return {}, []
    d = json.loads(p.read_text(encoding="utf-8"))
    mau = [re.compile(x, re.I) for x in d.get("_mau", [])]
    return {k: v for k, v in d.items() if not k.startswith("_")}, mau


def main() -> int:
    enable_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goc", required=True, help="thư mục latex/ hoặc supplement/ cần kiểm")
    ap.add_argument("--paper", default=str(REPO / "paper"), help="thư mục md nguồn")
    a = ap.parse_args()
    goc, paper = Path(a.goc).resolve(), Path(a.paper).resolve()
    bo, mau = doc_bo(goc)

    tong_thieu, tong_de_muc, n_file = [], 0, 0
    for tex in sorted((goc / "sections").glob("*.tex")):
        md = paper / (tex.stem + ".md")
        if not md.exists():
            continue
        n_file += 1
        noi_dung = md.read_text(encoding="utf-8")
        # Bỏ khối ghi chú đầu chương (build_tex bỏ từ `# Section` tới `---` đầu tiên — I-11).
        if noi_dung.lstrip().startswith("# "):
            k = noi_dung.find("\n---")
            if k != -1:
                noi_dung = noi_dung[k:]
        tex_txt = tex.read_text(encoding="utf-8")
        co_trong_tex = {chuan(m) for m in tieu_de_tex(tex_txt)}
        duyet_bo = {chuan(x) for x in bo.get(tex.stem, [])}
        for _, tieu_de in DE_MUC.findall(noi_dung):
            tong_de_muc += 1
            c = chuan(tieu_de)
            if not c or c in co_trong_tex or c in duyet_bo or any(r.search(tieu_de) for r in mau):
                continue
            tong_thieu.append((tex.stem, tieu_de))
        print(f"  {tex.stem:26s} md {len(DE_MUC.findall(noi_dung)):2d} đề mục · "
              f"tex {len(LENH.findall(tex_txt)):2d} lệnh · duyệt bỏ {len(duyet_bo)}")

    print(f"\n{n_file} file · {tong_de_muc} đề mục nguồn · "
          f"{len(tong_thieu)} BIẾN MẤT không khai      <-- mục tiêu 0")
    if tong_thieu:
        print("\n  -- đề mục có trong md mà KHÔNG ra .tex, và chưa khai ở de_muc_bo.json --")
        for stem, t in tong_thieu:
            print(f"     [{stem}] {t}")
        print("\n  Hoặc bộ dựng đang nuốt chúng (I-05, I-24), hoặc chúng cố ý bỏ —")
        print(f"  nếu cố ý thì khai vào {goc / 'de_muc_bo.json'} để lần sau không ai phải đoán.")
        return 1
    print("\nĐẠT: mọi đề mục nguồn hoặc ra được .tex, hoặc đã khai là cố ý bỏ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
