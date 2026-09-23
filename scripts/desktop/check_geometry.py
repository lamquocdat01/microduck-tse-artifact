r"""Cổng HÌNH HỌC: ký tự nào nằm NGOÀI khối chữ trên trang render — luật C2, lớp lỗi mới.

    python scripts\check_geometry.py --pdf bai.pdf
    python scripts\check_geometry.py --pdf bai.pdf --eps 2 --max-in 40

## Vì sao có cổng này

Đợt 26: chủ nhân mở bản nộp, trang 15, và thấy Bảng 8 **tràn lề phải** — cột cuối
"Wilson 95 %" bị cắt. Cả chuỗi cổng lúc ấy xanh: `check_refs`, `check_markup`,
`check_anon` đều **trích text**, và một ký tự nằm ngoài lề — kể cả ngoài MÉP GIẤY — vẫn
nằm nguyên trong content stream. Bộ trích đọc được đủ; chỉ người cầm trang là không.

Đo lại thì không phải một bảng: 18/26 bảng rộng hơn khối chữ, sáu bảng chạy quá mép giấy
(Bảng 26 rộng gấp bảy lần khối chữ), và mã commit của mục Data availability — đúng câu người
phản biện đọc để tìm bản phát hành — chạy ra khỏi trang.

Câu hỏi của cổng này là câu duy nhất các cổng kia không hỏi: *ký tự này có nằm TRONG
khung mà mắt người nhìn thấy không?* Nên nó đọc TOẠ ĐỘ, không đọc chữ.

## Khung lấy từ đâu

Không gõ cứng lề, và không đọc `\textwidth` từ LaTeX. Khung lấy từ **chính tài liệu**:
văn xuôi căn đều hai bên, nên phần lớn dòng chữ bắt đầu ở cùng một x0 và kết thúc ở cùng
một x1. Hai giá trị mốt ấy là lề trái và lề phải thật. Cổng in chúng ra, và từ chối kết
luận (rc=2) nếu mốt quá yếu — tức tài liệu không có khối chữ căn đều để làm thước.

Lý do không đọc từ LaTeX: đổi lớp, đổi khổ giấy, đổi `geometry` thì một con số gõ cứng
lặng lẽ sai, và cổng thành "đạt" với một khung không còn là khung của trang.

## Kiểm gì

  - mọi ký tự nhìn thấy: `x0 ≥ lề trái − ε` và `x1 ≤ lề phải + ε`, ε = 2 pt;
  - mọi ĐƯỜNG KẺ ngang (\hline): cùng luật. Một tabular rộng hơn khối chữ đúng bằng
    khoảng đệm `\tabcolsep` có chữ nằm trong lề nhưng đường kẻ thò ra 6 pt — XeLaTeX
    ghi nó là "Overfull \hbox (5.9pt too wide)", nên cổng này cũng phải thấy;
  - mọi ký tự: nằm TRONG MÉP GIẤY theo cả hai chiều. Vượt mép giấy là nội dung mất hẳn,
    không chỉ xấu — in riêng để không lẫn với tràn lề vài pt.

Mã thoát: 0 = mọi thứ trong khung, 1 = có vi phạm, 2 = dùng sai / không đo được.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

MM = 25.4 / 72
# Hai glyph liền nhau chồng lên nhau quá ngần này là chữ đè chữ, không phải kerning.
# Đo, không đoán: ở 1.5 pt lần chạy đầu trên bản nộp đợt 25 bắn 12 báo động giả, CẢ 12 là
# cặp dấu đóng ngoặc kép cong + dấu chấm (kerning Latin Modern, 1.5–1.7 pt). Một ô tràn
# chỉ đè glyph thật khi nó ăn hết khoảng đệm 2·\tabcolsep = 12 pt, nên 2.5 pt vẫn dư sức.
DE_PT = 2.5


def khung(pdf) -> tuple[float, float, float, int]:
    """(lề trái, lề phải, tỉ lệ dòng rơi đúng mốt, số dòng) từ các dòng chữ của tài liệu."""
    x0s: list[float] = []
    x1s: list[float] = []
    for pg in pdf.pages:
        for l in pg.extract_text_lines():
            x0s.append(l["x0"]); x1s.append(l["x1"])
    if not x0s:
        return 0.0, 0.0, 0.0, 0

    def mot(vals: list[float]) -> tuple[float, float]:
        # Gom theo ô 1 pt, lấy ô đông nhất CỘNG hai ô kề: 484.44 và 484.51 là cùng
        # một lề, và làm tròn thẳng thì chúng rơi vào hai ô rồi mốt yếu đi một nửa.
        dem = Counter(round(v) for v in vals)
        o, _ = dem.most_common(1)[0]
        gan = [v for v in vals if abs(v - o) <= 1.0]
        gan.sort()
        return gan[len(gan) // 2], len(gan) / len(vals)

    trai, ti_trai = mot(x0s)
    phai, ti_phai = mot(x1s)
    return trai, phai, min(ti_trai, ti_phai), len(x0s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True, help="bản PDF đã render")
    ap.add_argument("--eps", type=float, default=2.0, help="dung sai, pt (mặc định 2)")
    ap.add_argument("--max-in", type=int, default=40, help="in tối đa bấy nhiêu chỗ vi phạm")
    enable_utf8_console()
    args = ap.parse_args()

    try:
        import pdfplumber
    except ImportError:
        print("Cần `pdfplumber` để đọc toạ độ ký tự: pip install pdfplumber")
        return 2
    p = Path(args.pdf)
    if not p.exists():
        print(f"Không có {p}.")
        return 2

    with pdfplumber.open(str(p)) as pdf:
        trai, phai, ti, n_dong = khung(pdf)
        # Dưới 30 % dòng rơi đúng lề thì "lề" chỉ là một con số ngẫu nhiên, và một cổng
        # đo theo thước ngẫu nhiên thì xanh hay đỏ đều không nghĩa gì.
        if n_dong < 50 or ti < 0.30:
            print(f"Không dựng được khung: {n_dong} dòng, chỉ {ti:.0%} dòng rơi đúng lề. "
                  "Tài liệu không có khối chữ căn đều để làm thước.")
            return 2
        p1 = pdf.pages[0]
        print(f"Khổ giấy: {p1.width:.0f} × {p1.height:.0f} pt "
              f"({p1.width * MM:.0f} × {p1.height * MM:.0f} mm)"
              f"{'  = Letter' if (round(p1.width), round(p1.height)) == (612, 792) else ''}"
              f"{'  = A4' if (round(p1.width), round(p1.height)) == (595, 842) else ''}")
        print(f"Khung chữ (mốt của {n_dong} dòng, {ti:.0%} dòng đúng lề): "
              f"trái {trai:.2f} pt ({trai * MM:.1f} mm) · phải {phai:.2f} pt "
              f"(cách mép {(p1.width - phai) * MM:.1f} mm) · ε = {args.eps} pt")

        # Mỗi DÒNG vi phạm in một lần, không phải mỗi ký tự: một ô bảng tràn 300 pt là
        # 60 ký tự, và 60 dòng báo cho cùng một chỗ thì che mất chỗ thứ hai.
        vp: list[tuple[int, float, float, str, str, bool]] = []
        n_kytu = 0
        n_ke = 0
        n_giay = 0
        n_de = [0]
        for i, pg in enumerate(pdf.pages, 1):
            chars = [c for c in pg.chars if c["text"].strip()]
            dong: dict[float, list] = {}
            for c in chars:
                dong.setdefault(round(c["top"]), []).append(c)
            for top, cs in sorted(dong.items()):
                cs.sort(key=lambda c: c["x0"])
                xau = [k for k, c in enumerate(cs)
                       if c["x0"] < trai - args.eps or c["x1"] > phai + args.eps
                       or c["x0"] < 0 or c["x1"] > pg.width
                       or c["top"] < 0 or c["bottom"] > pg.height]
                # CHỮ ĐÈ CHỮ trên cùng dòng: ô bảng overfull đẩy chữ sang cột bên. Nằm
                # trong lề nên luật lề không thấy — ca thật ở lần sửa đầu của đợt 26,
                # bảng 8 cột Mục 3, 18 ô overfull mà cổng vẫn chỉ đỏ ở trang khác.
                for a, b in zip(cs, cs[1:]):
                    if b["x0"] < a["x1"] - DE_PT and abs(b["top"] - a["top"]) < 1.0:
                        n_de[0] += 1
                        chu = "".join(c["text"] for c in cs)
                        k = cs.index(b)
                        vp.append((i, b["x0"], top, chu[max(0, k - 20):k + 20],
                                   f"chữ đè chữ {a['x1'] - b['x0']:.1f} pt "
                                   f"({a['text']!r} tới {a['x1']:.1f}, {b['text']!r} từ {b['x0']:.1f})",
                                   False))
                        break
                if not xau:
                    continue
                n_kytu += len(xau)
                ngoai_giay = any(cs[k]["x1"] > pg.width or cs[k]["x0"] < 0
                                 or cs[k]["top"] < 0 or cs[k]["bottom"] > pg.height
                                 for k in xau)
                n_giay += sum(1 for k in xau if cs[k]["x1"] > pg.width or cs[k]["x0"] < 0
                              or cs[k]["top"] < 0 or cs[k]["bottom"] > pg.height)
                k = xau[0]
                chu = "".join(c["text"] for c in cs)
                ctx = chu[max(0, k - 20):k + 20]
                x_max = max(c["x1"] for c in cs)
                vp.append((i, cs[k]["x0"], top, ctx, f"x1 max {x_max:.1f} (tràn {x_max - phai:+.1f} pt)",
                           ngoai_giay))
            # đường kẻ ngang: \hline ra PDF là rect mảnh hoặc line
            for r in pg.rects + pg.lines:
                if abs(r["bottom"] - r["top"]) > 1.5 or r["width"] < 30:
                    continue
                if r["x0"] < trai - args.eps or r["x1"] > phai + args.eps:
                    n_ke += 1
                    vp.append((i, r["x0"], r["top"], "── đường kẻ ──",
                               f"x0..x1 {r['x0']:.1f}..{r['x1']:.1f} (tràn {r['x1'] - phai:+.1f} pt)",
                               r["x1"] > pg.width))

    trang = sorted({v[0] for v in vp})
    print(f"\n  ký tự ngoài khung       {n_kytu:5d}      <-- mục tiêu 0")
    print(f"    trong đó ngoài MÉP GIẤY {n_giay:5d}      (nội dung mất hẳn trên trang in)")
    print(f"  đường kẻ ngoài khung    {n_ke:5d}      <-- mục tiêu 0")
    print(f"  dòng có chữ đè chữ      {n_de[0]:5d}      <-- mục tiêu 0   (ô tràn sang cột bên, trong lề)")
    if vp:
        print(f"  trang có vi phạm: {', '.join(map(str, trang))}")
        print("\n  -- chỗ vi phạm (mỗi dòng chữ một lần) --")
        for i, x0, top, ctx, do, giay in vp[:args.max_in]:
            print(f"     trang {i:2d}  x0={x0:6.1f} y={top:6.1f}  {do}"
                  f"{'  NGOÀI MÉP GIẤY' if giay else ''}\n         «{ctx}»")
        if len(vp) > args.max_in:
            print(f"     ... và {len(vp) - args.max_in} chỗ nữa")

    rc = 1 if vp else 0
    print("\n" + ("ĐẠT: mọi ký tự và đường kẻ nằm trong khung chữ." if rc == 0 else
                  "CHƯA ĐẠT — nội dung nằm ngoài khung chữ trên trang render. Sửa ở bộ sinh"
                  " (build_tex.py), không sửa tay .tex."))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
