"""Cổng ẩn danh cho bản nộp IP&M — trả MÃ THOÁT, không trả lời bằng mắt.

IP&M phản biện **double anonymized**. Guide-for-authors (bản sống, 11/09/2026):

    "The anonymized manuscript should contain the main body of your paper,
     including references and tables. It is important that your manuscript
     AND ANY SUPPLEMENTARY MATERIALS do not contain any identifying information
     such as author names or affiliations, OR ACKNOWLEDGEMENTS."

Vì sao là script chứ không phải một dòng trong checklist: ẩn danh hỏng theo đúng
kiểu mà mắt người bỏ sót — một dòng `\\author` sót lại, một URL repo mang tên tài
khoản, một `Copyright (c) 2026 <tên>` nằm trong file LICENSE của gói bổ sung. Cùng
lý do `build_numbers.py --check` và `check_refs.py` tồn tại: chặn bằng cơ chế, không
chặn bằng cẩn thận hơn.

Dùng:
    python desktop/scripts/check_anon.py            # quét bản thảo (mặc định)
    python desktop/scripts/check_anon.py --supp     # quét cả gói bổ sung
    python desktop/scripts/check_anon.py --pdf paper/latex/main.pdf

Mã thoát: 0 = sạch, 1 = còn chỗ nhận diện, 2 = lỗi dùng sai.

⚠ Script này KHÔNG quét được: metadata của .pdf/.docx đã render, tên file, và nội
dung ảnh. Ba chỗ ấy vẫn phải xem bằng mắt trước khi nộp — nhưng chúng là ba chỗ,
không phải cả cây thư mục.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]

# Mỗi mẫu là một chỗ nhận diện THẬT trong repo này, không phải mẫu chung chung.
# Thêm mẫu mới thì thêm cả lý do — một mẫu không có lý do là một mẫu không ai dám xoá.
MAU: list[tuple[str, str]] = [
    (r"lamquocdat", "e-mail / tên tài khoản GitHub của tác giả"),
    (r"\bDat Lam\b|\bLam Quoc\b|\bLAM QUOC\b", "tên tác giả"),
    (r"\bFPT\b", "đơn vị công tác"),
    (r"0009-0004-5432-9343", "ORCID của tác giả"),
    (r"\bORCID\b", "nhãn ORCID (kể cả khi số đã bỏ)"),
    (r"github\.com/[A-Za-z0-9._-]+", "URL repo — mang tên tài khoản"),
    (r"\bmicroduck\b|\bduckly\b", "tên dự án"),
    (r"\bES3C28P\b", "tên board thương mại"),
    # Siết hơn mẫu đầu tiên: "deferred:\textbf" từng khớp "[A-Za-z]:\\[A-Za-z]" và
    # báo động giả trên một câu văn bình thường. Ổ đĩa phải đi kèm một tên thư mục
    # thật thì mới là đường dẫn.
    (r"(?<![A-Za-z])[A-Za-z]:[\\/]{1,2}(THS|Users|Program|home)"
     r"|THS Programing|/Users/[A-Za-z]|/home/[a-z]+/", "đường dẫn máy tác giả"),
    (r"\\markboth", "running head — in họ tác giả lên mọi trang"),
    (r"IEEEbiography", "khối tiểu sử — Elsevier không có, và nó lộ danh tính"),
    (r"\\section\*?\{Acknowledg", "mục Acknowledgements — guide bắt để CHỈ ở title page"),
]

# Bản thảo ẩn danh: đây là những file THỰC SỰ nộp.
BAN_THAO = [
    "paper/latex/main.tex",
    "paper/latex/abstract.tex",
    "paper/latex/keywords.tex",
    "paper/latex/ai-declaration.tex",
    "paper/latex/body.tex",
    "paper/latex/refs.bib",
]
BAN_THAO_THUMUC = ["paper/latex/sections"]

# Gói bổ sung. Guide nói rõ "and any supplementary materials".
SUPP_THUMUC = ["paper/data-package/github"]

# Bản ẩn danh của gói dữ liệu, dựng bằng paper/data-package/make_anon.py.
# Tách khỏi SUPP_THUMUC có chủ ý: bản CÔNG KHAI phải ĐỎ ở cổng này và đó là ĐÚNG —
# giấy phép CC BY 4.0 đòi ghi công, gỡ tên khỏi bản công khai là làm hỏng giấy phép.
# Cái phải sạch là bản ẩn danh, và nó là một cây thư mục khác.
ANON_THUMUC = ["paper/data-package/anon"]

# titlepage.tex ĐƯỢC PHÉP mang mọi thứ — nó là file kia của cặp hai file.
# titlepage.tex va cover-letter.tex DUOC PHEP mang moi thu — chung la hai file
# BIEN TAP VIEN doc, khong phai file nguoi phan bien doc. Duong B cua dot 22 dat
# URL repo (mang ten tai khoan) o dung hai cho nay va khong cho nao khac.
MIEN = {"paper/latex/titlepage.tex", "paper/latex/cover-letter.tex"}


def quet(p: Path) -> list[tuple[int, str, str]]:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    ra = []
    for i, dong in enumerate(text.splitlines(), 1):
        for rx, ly_do in MAU:
            if re.search(rx, dong):
                ra.append((i, ly_do, dong.strip()[:100]))
    return ra


def gom(duong_dan: list[str], thu_muc: list[str]) -> list[Path]:
    ra = []
    for d in duong_dan:
        p = GOC / d
        if p.is_file():
            ra.append(p)
    for d in thu_muc:
        t = GOC / d
        if t.is_dir():
            ra += [
                f for f in sorted(t.rglob("*"))
                if f.is_file()
                # LICENSE / NOTICE / AUTHORS không có đuôi, mà LICENSE lại là chỗ tên
                # tác giả nằm chắc chắn nhất trong một gói dữ liệu. Bản đầu của cổng
                # này bỏ sót đúng file ấy vì lọc theo đuôi.
                and (f.suffix.lower() in {".tex", ".bib", ".md", ".py", ".txt", ".cff",
                                          ".json", ".csv", ".yaml", ".yml"}
                     or f.name in {"LICENSE", "LICENCE", "NOTICE", "AUTHORS", "COPYING"})
                and "__pycache__" not in f.parts
            ]
    return [f for f in ra if str(f.relative_to(GOC)).replace("\\", "/") not in MIEN]


# ---------------------------------------------------------------------------
# CHẾ ĐỘ NGƯỢC (đợt 27e việc 141). IEEE TSE phản biện SINGLE-BLIND: bản thảo PHẢI mang tên tác giả, đơn vị,
# ORCID và repo thật. Lỗi bây giờ là CHIỀU NGƯỢC LẠI — một câu ẩn danh thời IP&M còn sót ("URL withheld to
# preserve double-anonymized review") hoặc khối tác giả bị quên. Hai loại kiểm:
#   (1) placeholder ẩn danh trong nguồn TSE → rc 1;
#   (2) thiếu một mục bắt buộc của khối tác giả trong main.tex/titlepage TSE → rc 1.
NGUOC_PLACEHOLDER: list[tuple[str, str]] = [
    (r"double[- ]anonymi[sz]ed|double[- ]blind", "câu nhắc phản biện ẩn danh hai chiều (TSE là single-blind)"),
    (r"withheld (?:from this manuscript|to preserve)", "URL/ danh tính bị giữ lại vì ẩn danh"),
    (r"will be provided on acceptance", "hứa cung cấp sau khi nhận — dấu hiệu ẩn danh"),
    (r"anonymi[sz]ed proxy|anonymous\.4open\.science", "proxy ẩn danh"),
    (r"\[ANONYMI[SZ]ED\]|\[ANON\]|Anonymous Author", "placeholder tác giả ẩn danh"),
    (r"Anonymised(?: as in Section|:)", "ghi chú ẩn danh đầu chương"),
]
NGUOC_BAT_BUOC: list[tuple[str, str]] = [
    (r"Dat Lam Quoc", "tên tác giả"),
    (r"FPT (?:School of Business and Technology|University)", "đơn vị"),
    (r"0009-0004-5432-9343", "ORCID"),
    (r"github\.com/lamquocdat01/retrieval-decision-determinism", "URL repo thật"),
]
NGUOC_NGUON = ["Submission TSE/latex/main.tex", "Submission TSE/latex/abstract.tex"]
NGUOC_THUMUC = ["Submission TSE/latex/sections"]


def nguoc() -> int:
    files = gom(NGUOC_NGUON, NGUOC_THUMUC)
    if not files:
        print("KHÔNG có nguồn TSE để quét", file=sys.stderr)
        return 2
    hong = 0
    gop = ""
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="replace")
        gop += txt + "\n"
        for i, dong in enumerate(txt.splitlines(), 1):
            if dong.lstrip().startswith("%"):
                continue                       # chú thích LaTeX không ra trang
            for mau, ly_do in NGUOC_PLACEHOLDER:
                if re.search(mau, dong, re.I):
                    hong += 1
                    print(f"  [placeholder] {f.relative_to(GOC)}:{i}: {ly_do}\n    | {dong.strip()[:140]}")
    khong_chu_thich = "\n".join(l for l in gop.splitlines() if not l.lstrip().startswith("%"))
    for mau, ten in NGUOC_BAT_BUOC:
        if not re.search(mau, khong_chu_thich):
            hong += 1
            print(f"  [THIẾU] {ten} — không có trong nguồn TSE (ngoài chú thích)")
    print(f"\n{len(files)} file quét (chế độ ngược, single-blind), {hong} vấn đề.")
    print("SẠCH." if not hong else "KHÔNG NỘP: còn dấu ẩn danh hoặc thiếu khối tác giả.")
    return 1 if hong else 0


def main() -> int:
    if "--nguoc" in sys.argv:
        return nguoc()
    ap = argparse.ArgumentParser()
    ap.add_argument("--supp", action="store_true",
                    help="quét cả gói dữ liệu bổ sung (bản CÔNG KHAI — có tên là đúng)")
    ap.add_argument("--anon", action="store_true",
                    help="quét BẢN ẨN DANH của gói dữ liệu (phải sạch, rc 0)")
    ap.add_argument("--cay", type=Path, default=None,
                    help="quét MỘT THƯ MỤC bất kỳ (ví dụ zip nguồn đã giải nén). "
                         "Quét CẢ dòng comment: với zip nguồn, comment là nội dung "
                         "nhà xuất bản nhận.")
    ap.add_argument("--pdf", type=Path, default=None,
                    help="quét thêm một PDF đã render (cần pdftotext hoặc pypdf)")
    args = ap.parse_args()

    if args.cay:
        goc = args.cay.resolve()
        if not goc.is_dir():
            print(f"Không có thư mục {goc}", file=sys.stderr)
            return 2
        files = sorted(f for f in goc.rglob("*")
                       if f.is_file()
                       and f.suffix.lower() in {".tex", ".bib", ".bbl", ".txt", ".md",
                                                ".cls", ".sty", ".json", ".csv"}
                       and "__pycache__" not in f.parts)
        nhan = {f: "zip nguồn" for f in files}
    else:
        files = gom(BAN_THAO, BAN_THAO_THUMUC)
        nhan = {f: "bản thảo" for f in files}
    if args.supp:
        supp = gom([], SUPP_THUMUC)
        files += supp
        nhan.update({f: "gói bổ sung" for f in supp})
    if args.anon:
        an = gom([], ANON_THUMUC)
        if not an:
            print("Chưa có bản ẩn danh. Dựng: python paper/data-package/make_anon.py",
                  file=sys.stderr)
            return 2
        files += an
        nhan.update({f: "gói ẩn danh" for f in an})

    if not files:
        print("KHÔNG có file nào để quét — sai đường dẫn?", file=sys.stderr)
        return 2

    tong = 0
    for f in files:
        hit = quet(f)
        if not hit:
            continue
        tong += len(hit)
        try:
            rel = f.relative_to(GOC)
        except ValueError:
            rel = f
        print(f"\n[{nhan[f]}] {rel}")
        for dong, ly_do, noi_dung in hit:
            print(f"  dòng {dong}: {ly_do}")
            print(f"    | {noi_dung}")

    if args.pdf:
        tong += quet_pdf(args.pdf)

    print(f"\n{len(files)} file quét, {tong} chỗ nhận diện.")
    if tong:
        print("KHÔNG NỘP. Chuyển những chỗ trên sang paper/latex/titlepage.tex,")
        print("hoặc bỏ hẳn. Guide: bản thảo và mọi tài liệu bổ sung phải sạch.")
        return 1
    print("SẠCH.")
    return 0


def quet_pdf(p: Path) -> int:
    if not p.exists():
        print(f"\n[pdf] KHÔNG THẤY {p}", file=sys.stderr)
        return 1
    text = ""
    try:
        import subprocess
        r = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True)
        if r.returncode == 0:
            text = r.stdout
    except FileNotFoundError:
        pass
    if not text:
        try:
            from pypdf import PdfReader
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
        except Exception:
            print(f"\n[pdf] KHÔNG ĐỌC ĐƯỢC {p.name} — cần pdftotext hoặc pypdf.")
            print("      Đây là CHƯA KIỂM, không phải ĐẠT.")
            return 1
    n = 0
    for rx, ly_do in MAU:
        for m in re.finditer(rx, text):
            n += 1
            print(f"\n[pdf] {p.name}: {ly_do}")
            print(f"    | ...{text[max(0, m.start() - 40):m.end() + 40]!r}...")
            break
    return n


if __name__ == "__main__":
    sys.exit(main())
