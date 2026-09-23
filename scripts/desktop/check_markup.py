r"""Đếm dấu Markdown RÒ RA BẢN RENDER — luật C2 của chủ nhân, đóng thành mã thoát.

    python scripts\check_markup.py                      # kiểm paper/latex/sections/*.tex
    python scripts\check_markup.py --pdf bai.pdf        # kiểm trên BẢN PDF ĐÃ RENDER
    python scripts\check_markup.py --pdf bai.pdf --tex  # cả hai, một mã thoát

## Vì sao có script này

Đợt 19 mở ra với **90 dấu `**` in nguyên văn** trên `sections/*.tex`, tức ~48 dấu đi thẳng
ra trang PDF. Người phản biện thấy chúng ở trang đầu, và nó đọc như bài làm ẩu — ở một bài
mà toàn bộ luận điểm là *"chúng tôi đo cẩn thận"*, đó là thiệt hại không tỉ lệ với nguyên
nhân.

Nguyên nhân là một dòng: `chuyen()` chạy **theo từng dòng**, nên `**` mở ở dòng này và đóng
ở dòng sau thì không dòng nào khớp. 50 chỗ trong 11 chương.

## Hậu quả thứ hai mới là lý do cổng này quét BẢN RENDER chứ không quét nguồn

Dấu `**` bị bỏ lại trên dòng sau **đi tìm bạn mới**: nó khớp với `**` kế tiếp trong cùng
dòng, nên phần in đậm bao đúng đoạn **SAI**. Mục 3 in ra

    ...budget can afford\textbf{, and }whether the layer is reproducible**

— chữ được tô đậm là ", and". Mục 5 và Mục 6 mỗi chỗ một lần nữa.

Ba chỗ ấy **không có dấu hiệu nào trên nguồn markdown**: nguồn đúng, chỉ bản dựng ghép
lệch. `grep '\*\*' paper/*.md` ra sạch. Chúng chỉ thấy được trên **bản dựng** và trên
**trang render** — nên đó là hai chỗ cổng này đứng.

## Vì sao KHÔNG gộp vào check_refs.py

`check_refs.py` trả lời một câu hỏi của nhà xuất bản (*"thư mục có resolve được không"*).
Cái này trả lời một câu hỏi của người đọc (*"trang có sạch không"*). Một cổng hai mục tiêu
thì khi một mục tiêu chưa về 0 được, người ta tắt cả cổng — và đó là cách `doc_muc_pdf()`
đã suýt chết ở đợt 18.

Mã thoát: 0 = sạch, 1 = còn dấu rò, 2 = lỗi dùng sai.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
GOC_MAC_DINH = REPO / "paper" / "latex"

# Mỗi mẫu là một dấu Markdown mà LaTeX KHÔNG có nghĩa nào cho nó, nên mọi lần xuất hiện
# là một lần rò. Giữ danh sách này HẸP có chủ ý: một cổng báo động giả là một cổng sẽ bị
# tắt, và cổng này chặn thứ người phản biện thấy đầu tiên.
#
# Đã cân nhắc và CỐ Ý bỏ ra ngoài:
#   - `*` đơn: `table*`, `figure*`, `\section*` đều hợp lệ và rất nhiều;
#   - backtick: `` `` `` là dấu mở ngoặc kép hợp lệ của LaTeX;
#   - hàng `|`: `tabular` dùng `|` trong spec cột một cách hợp lệ.
# Ba thứ ấy cần ngữ cảnh mới phân biệt được, và đoán sai thì cổng mất tin.
#
# Cột `tren`: mẫu nào đúng ở NGUỒN NÀO. Không phải mẫu nào cũng đọc được ở cả hai, và
# lần chạy đầu của cổng này đã chứng minh đúng chỗ ấy: mẫu đề mục `#` bắn một báo động
# giả ở trang 17, trên một bảng có CỘT TÊN LÀ "#" (cột đánh số hàng). Lý do là cấu trúc,
# không phải mẫu viết rộng: trên .tex thì đầu dòng là đầu dòng thật, còn trên text trích
# từ PDF thì ngắt dòng do BỘ TRÍCH đặt, nên một ô giữa bảng rơi vào đầu một dòng trích
# và `^#` khớp. Một cổng báo động giả là một cổng sẽ bị tắt trong một buổi chiều, nên
# mẫu nào không đọc được trên PDF thì KHÔNG chạy trên PDF — chứ không phải miễn trừ
# riêng cái bảng ấy, vì miễn trừ thì lần sau có đề mục rò thật cũng lọt.
#
# `**` thì đọc được ở cả hai: LaTeX không có nghĩa nào cho nó, và bộ trích không sinh
# ra nó. Đó là mẫu chính của cổng này, và là 90 chỗ của đợt 19.
# Đợt 27h việc D — hai nhãn đơn vị hợp lệ của M6, và định nghĩa "một câu".
# `_CAU` coi dấu chấm KHÔNG có khoảng trắng sau là chữ, nên 0.750 không cắt câu làm đôi.
_NHAN_M6 = r"tests flaky across|tests failing in run|test flaky /|test hỏng /"
_CAU = r"(?:[^.]|\.(?!\s))"

MAU: list[tuple[str, re.Pattern, str, tuple[str, ...], bool]] = [
    ("**", re.compile(r"\*\*"),
     "in đậm Markdown chưa chuyển — và dấu lẻ còn ghép SAI đoạn với dấu kế tiếp",
     ("tex", "pdf"), False),
    ("#", re.compile(r"^\s{0,3}#{1,6}[ \t]", re.M),
     "đề mục Markdown chưa chuyển thành \\section/\\subsection",
     ("tex",), False),
    # NGÔN NGỮ NHÁP + ĐƯỜNG DẪN NỘI BỘ rò ra bản nộp. Đây không phải lỗi định dạng,
    # nó là GIÀN GIÁO LÀM VIỆC in trong một bài nộp tạp chí — và người phản biện đọc
    # nó như bằng chứng bài chưa xong.
    #
    # Đợt 19 tìm thấy trên bản --final: "format-neutral draft, written to be
    # overwritten." đứng ĐẦU TÁM chương (đuôi của dấu [[VENUE]] đã bị bỏ, xem
    # build_tex.py), một đoạn "Citation discipline for this draft" in nguyên trong
    # Mục 9, và hai đường dẫn nội bộ "paper/REFERENCES.md", "paper/00-title-page.md".
    #
    # Quét cả .tex lẫn .pdf: .tex bắt sớm, .pdf là bằng chứng cuối vì nó là cái người
    # phản biện thật sự cầm.
    ("nháp", re.compile(r"written to be overwritten|format-neutral"
                        r"|for this draft|this draft\b", re.I),
     "ngôn ngữ NHÁP in ra bản nộp — giàn giáo làm việc, không phải nội dung bài",
     ("tex", "pdf"), True),
    ("đường-dẫn", re.compile(r"\b(?:paper|docs|desktop|shared|web|firmware)/"
                             r"[A-Za-z0-9_.\-]+\.(?:md|py|json|tex|bib|csv|jsonl)"),
     "đường dẫn file NỘI BỘ của repo in ra bản nộp",
     ("tex", "pdf"), True),
    # Dấu [[...]] còn sót trên BẢN NỘP. --final hứa bỏ hết; nếu còn thì lời hứa ấy
    # đã hỏng ở một nhánh nào đó (ví dụ dấu nằm trong code span, đúng ca đợt 19).
    ("[[", re.compile(r"\[\[|\]\]"),
     "dấu [[...]] chưa bị --final tước — lời hứa của --final đã hỏng ở đâu đó",
     ("tex", "pdf"), True),
    # TỬ SỐ MƠ HỒ (đợt 27, việc 110; luật CLAIM-EVIDENCE §D3). Bản nộp IP&M in
    # "byte-identical transcript on 0/31 repeats" và "decision was unchanged on 0/30"
    # — đọc nguyên văn là KHÔNG LẦN NÀO giống, trong khi ý là không lần nào ĐỔI, và
    # Highlights cùng gói viết 31/31. Bài tự mâu thuẫn ngay trên trang render.
    #
    # Khoảng giữa chữ và số được phép qua dòng mới và `\textbf{`: câu thật bị ngắt
    # đúng chỗ ấy ("byte-identical\ntranscript on \textbf{0/31}"), nên mẫu dính liền
    # sẽ im lặng trên đúng những câu cần bắt. Khoảng ấy KHÔNG được chứa
    # "changed/differ": "given identical audio, the decision changed on 0/30" là câu
    # ĐÚNG, và cổng bắt oan câu đúng thì sẽ bị tắt. Chạy trên mọi bản, không chỉ --nop.
    ("0/n-mơ-hồ", re.compile(
        r"\b(?:unchanged|identical|held|stable)\b"
        r"(?:(?!\b(?:changed|differ\w*)\b)[^.;|]){0,50}?"
        r"\bon[\s~]+(?:only[\s~]+)?(?:\\textbf\{|\*\*)?\s*(?<![\d.,])0(?:\s*/\s*|[\s~]+of[\s~]+)\d+",
        re.I),
     "tử số 0 đi với chữ ỔN ĐỊNH đọc thành 'không lần nào giống' — viết 'changed on k/n (n−k/n identical)'",
     ("tex", "goc", "pdf"), False),
    # TOÁN RÒ (đợt 27d): `$...$` trong md bị bước thoát nuốt thành chữ — PDF in "$R^{dec}_i$" nguyên
    # văn, xelatex vẫn rc 0. Trên .tex: `\$` rồi dấu mũ/gạch dưới đã thoát trước `\$` kế tiếp; trên PDF:
    # cặp `$` bao ký hiệu có `^`/`_`.
    ("toán-rò", re.compile(r"\\\$[^\n$]{0,60}?(?:\\textasciicircum|\\_)[^\n$]{0,60}?\\\$"),
     "ký hiệu toán rò ra trang — build_tex phải cất `$...$` trước bước thoát",
     ("tex",), False),
    ("toán-rò-pdf", re.compile(r"\$[^\s$\d][^$\n]{0,60}?[\^_][^$\n]{0,60}?\$"),
     "ký hiệu toán in nguyên văn trên PDF (cặp $ bao ^ hoặc _)",
     ("pdf",), False),
    # GHI CHÚ ĐẦU CHƯƠNG RÒ (đợt 27e, I-11): các cụm chỉ có trong phần đầu chương md — đã in trên bản IP&M
    # đã nộp. Chạy trên MỌI bản (không chỉ --nop): ghi chú làm việc không thuộc bản nháp đọc nội bộ nào cả.
    ("ghi-chú-đầu-chương", re.compile(r"Anonymised(?: as in Section|: no project name)|Numbered [IVXL]+ in the assembled"
                                      r"|Placement: after Related|Written \*{0,2}after\*{0,2} Sections"),
     "ghi chú làm việc ở đầu chương md rò ra trang", ("tex", "pdf"), False),
    # CAPTION THIẾU (đợt 27e việc 142, I-15): bảng không có khoá trong captions.json in chữ đỏ
    # "[thieu caption cho tab:…]" lên trang; xelatex rc 0, mọi cổng khác xanh — 3 bảng thân bài TSE tới 17/09.
    ("caption-thiếu", re.compile(r"thieu caption cho tab:"),
     "bảng thiếu caption — thêm khoá tab:<chương>-<n> vào captions.json", ("tex", "pdf"), False),
    # SỐ LẦN / SỐ NGÀY M6 GÕ TAY (duyệt 142, 17/09): dùng \numMSixRuns / \numMSixRunsDigit / \numMSixDays
    # (build_numbers.py, từ plan.json + M6 jsonl). "four days later" của pilot (16/23) không bị bắt: chỉ "over … days".
    ("m6-gõ-tay", re.compile(r"\b(?:twenty|20)\s+(?:times|runs)\b|\bover\s+(?:four|4)\s+days\b", re.I),
     "số lần/ngày M6 gõ tay — dùng \\numMSixRuns / \\numMSixRunsDigit / \\numMSixDays (sinh từ plan)",
     ("tex", "goc", "md"), False),
    # THAM CHIẾU MỤC GÕ TAY (đợt 27e việc 140). "§3.4" trong bài là số mục md thời IP&M; bản IEEE đánh số
    # khác và dời cấu trúc SE làm nó sai im lặng. Dùng {{sec:3.4}} → Section~\ref{sub:3.4}.
    ("section-gõ-tay", re.compile(r"\bSections?(?:~|\s)+(?!~?\\ref)(?:[IVXL]+\b|\d+(?:\.\d+)?\b)"),
     "\"Section N\" gõ tay — số chương đổi khi dời cấu trúc; dùng {{sec:N}}", ("tex",), False),
    ("§-gõ-tay", re.compile(r"(?:§|\\S\{\}|\\S\s)\s*\d"),
     "tham chiếu mục gõ tay — dùng {{sec:N.M}} (\\ref)", ("tex", "goc"), False),
    # CỠ TẦNG GÕ TAY (đợt 27e việc 140): số đứng trước "utterances" là cỡ tầng S1/S2/S3 → \numSOne/…
    # Không bắt ký hiệu pilot "n = 31 utterances", "6/31 utterances" (đứng sau = hoặc /).
    ("cỡ-tầng-gõ-tay", re.compile(r"(?<![/=\d.,])(?<!=\s)(?<!=~)\b\d{2,3}\s+(?:\*\*)?(?:[A-Za-z-]+\s+){0,2}utterances\b"),
     "cỡ tầng M1 gõ tay — dùng \\numSOne / \\numSTwo / \\numSThree (sinh từ plan + manifest)",
     ("tex", "goc", "md"), False),
    # SỐ CA HỎNG ÂM THẦM GÕ TAY (đợt 27d). Số ca sinh từ catalogue §9 bằng build_numbers.py thành
    # \numSilentFailures (md: {{numSilentFailures}}). Catalogue đã đổi từ sáu lên bảy ca trong một buổi
    # và năm chỗ trong bài phải sửa tay theo — chính kiểu trôi mà numbers.json tồn tại để chặn.
    # Bắt chữ số đếm đứng trong 5 từ quanh "silent"/"boundary", hai chiều, và bản tiếng Việt
    # "sáu/bảy ca|chỗ". Không chạy trên PDF: ở đó macro đã thành chữ.
    ("so-ca-go-tay", re.compile(
        r"\b(?:six|seven|eight)\b(?:\W+\w+){0,5}?\W+(?:silent|boundary)\b"
        r"|\b(?:silent|boundary)\b(?:\W+\w+){0,5}?\W+(?:six|seven|eight)\b"
        r"|\b(?:sáu|bảy|tám)\s+(?:ca|chỗ)\b", re.I),
     "số ca hỏng âm thầm gõ tay — dùng \\numSilentFailures / {{numSilentFailures}} (sinh từ catalogue)",
     ("tex", "goc", "md"), False),
    # M6 THIẾU NHÃN ĐƠN VỊ (đợt 27h việc D). M6 có HAI mẫu số khác nhau đứng cạnh nhau:
    #   10/40  = test flaky GỘP QUA 19 lần chạy  -> "k of n tests flaky across 19 runs"
    #   31/252 = test hỏng TRONG MỘT lần chạy    -> "k of n tests failing in run r"
    # Đọc lẫn hai cái đúng là bẫy tử số/mẫu số mà dự án đã ăn một lần. Luật: câu nào có từ khoá
    # flake của M6 và một phân số mà KHÔNG mang một trong hai nhãn -> đỏ.
    ("m6-thiếu-nhãn", re.compile(
        r"(?:flak(?:e|y)|decision suite|artefact suite)"
        r"(?:(?!" + _NHAN_M6 + r")" + _CAU + r"){0,400}?"
        r"(?<![\w./])\d+\s*/\s*\d+(?![\w./])"
        r"(?:(?!" + _NHAN_M6 + r")" + _CAU + r"){0,400}?\.(?=\s|$)", re.I),
     "số M6 dạng k/n thiếu nhãn đơn vị — thêm 'tests flaky across N runs' hoặc 'tests failing in run r'",
     ("tex", "goc", "md"), False),
]

# MARKDOWN RÒ (đợt 27e việc 140). `*nghiêng*` / `_nghiêng_` còn nguyên trong .tex = in nguyên văn trên
# PDF. Ca thật: đoạn 1 của §I vắt `*…*` qua hai dòng md (bộ chuyển inline từng dòng nên không ghép),
# và RQ5 có `*` bên trong cờ M-PENDING phá cặp. Mẫu `**` không thấy cả hai (sao ĐƠN). Quét trên ĐOẠN VĂN
# đã gộp dòng — mẫu theo dòng im lặng đúng trên ca vắt dòng — sau khi bỏ toán, verbatim, chú thích.
MD_RO = [re.compile(r"(?<!\\)\*[^*\n]+\*"), re.compile(r"(?<![\w\\])_[^_\n]+_")]


def quet_markdown_ro(ten: str, tex: str) -> list[tuple[str, str, int, str]]:
    t = re.sub(r"(?m)(?<!\\)%.*$", "", tex)
    t = re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", lambda m: "\n" * m.group(0).count("\n"), t, flags=re.S)
    t = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)\$.*?(?<!\\)\$|\\\[.*?\\\]",
               lambda m: " " * len(m.group(0)), t, flags=re.S)
    # env có dấu sao hợp lệ: \section*, table*, \\*
    t = re.sub(r"\\[A-Za-z]+\*|\{[A-Za-z]+\*\}|\\\\\*", lambda m: " " * len(m.group(0)), t)
    ra = []
    vi_tri = 0
    for doan in re.split(r"(\n\s*\n)", t):
        gop = doan.replace("\n", " ")
        for rx in MD_RO:
            for m in rx.finditer(gop):
                dong = t.count("\n", 0, vi_tri + m.start()) + 1
                ra.append((ten, "markdown-rò", dong, " ".join(gop[max(0, m.start() - 30):m.end() + 20].split())))
        vi_tri += len(doan)
    return ra


# Nguồn markdown của bài mà cổng `md` quét (bản gốc; .tex là bản dựng từ chúng).
MD_BAI = ["01-introduction.md", "01b-study-design.md", "03-stt-layer.md", "09b-silent-failures.md", "10-conclusion.md", "abstract.md",
          "CLAIM-EVIDENCE.md", "08-limitations.md", "09-related-work.md", "HIGHLIGHTS.md"]

# ⚠ CỐ Ý KHÔNG chặn chuỗi "draft" trần, dù prompt đợt 20 nêu nó.
#
# Lý do là dữ kiện, không phải ý thích: bản --final chứa chữ "draft" ĐÚNG BA LẦN, và
# HAI trong ba nằm trong mục KHAI BÁO AI mà chính sách Elsevier BẮT phải có, gần như
# nguyên văn mẫu của họ:
#
#     "...used Claude (Anthropic) in order to produce FIRST-DRAFT prose..."
#     "The tool was used at the level of DRAFTing and organisation, not analysis."
#
# Chặn "draft" trần ⇒ cổng đỏ vĩnh viễn trên một đoạn KHÔNG ĐƯỢC PHÉP sửa. Một cổng
# không thể về 0 là một cổng sẽ bị tắt trong một buổi chiều — cùng bài học với
# doc_muc_pdf() ở đợt 18 và với mẫu `#` ở đợt 19. Nên chặn đúng các CỤM chỉ xuất hiện
# trong giàn giáo ("for this draft", "format-neutral", "written to be overwritten"),
# và để chữ "draft" của mục khai báo AI đi qua.


def quet(ten: str, text: str, loai: str, nop: bool) -> list[tuple[str, str, int, str]]:
    """Trả về [(nguồn, nhãn mẫu, số dòng, đoạn trích)] cho mọi chỗ rò.

    `loai` là "tex" hoặc "pdf" — nó chọn tập mẫu, xem ghi chú ở MAU.
    """
    ra = []
    for nhan, rx, _ly_do, tren, chi_nop in MAU:
        if loai not in tren or (chi_nop and not nop):
            continue
        for m in rx.finditer(text):
            dong = text.count("\n", 0, m.start()) + 1
            d = text[max(0, m.start() - 45):m.start() + 55].replace("\n", " ")
            ra.append((ten, nhan, dong, " ".join(d.split())))
    return ra


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", help="quét bản PDF đã render")
    ap.add_argument("--tex", action="store_true",
                    help="quét cả sections/*.tex (mặc định khi không có --pdf)")
    ap.add_argument("--log", help="quét .log của XeLaTeX tìm glyph bị RƠI KHỎI TRANG")
    ap.add_argument("--nop", action="store_true",
                    help="đây là BẢN NỘP (dựng bằng --final): bật thêm các mẫu chỉ "
                         "đúng với bản nộp — ngôn ngữ nháp, đường dẫn nội bộ. "
                         "Trên bản NHÁP những thứ ấy PHẢI có, nên mặc định tắt.")
    ap.add_argument("--goc", help="thư mục latex cần kiểm (mặc định paper/latex). "
                                  "Gói TSE truyền 'Submission TSE/latex'.")
    ap.add_argument("--kytu", action="store_true",
                    help="cổng KÝ TỰ: đối chiếu sections/*.tex đã dựng với text trích từ PDF. "
                         "Cần --pdf. Mọi ký tự ngoài ASCII trong .tex phải hoặc đã "
                         "KHAI trong anh_xa.json, hoặc CÓ MẶT trong PDF.")
    enable_utf8_console()   # console Windows mac dinh la cp1258, in tieng Viet la vo
    args = ap.parse_args()
    goc = Path(args.goc).resolve() if args.goc else GOC_MAC_DINH
    SECTIONS = goc / "sections"

    quet_tex = args.tex or not args.pdf
    hong: list[tuple[str, str, int, str]] = []
    n_nguon = 0

    if quet_tex:
        if not SECTIONS.exists():
            print(f"Chưa có {SECTIONS}. Chạy build_tex.py trước.")
            return 2
        tep = sorted(SECTIONS.glob("*.tex"))
        if not tep:
            print(f"{SECTIONS} không có file .tex nào. Chạy build_tex.py trước.")
            return 2
        for f in tep:
            n_nguon += 1
            hong += quet(f.name, f.read_text(encoding="utf-8"), "tex", args.nop)
            hong += quet_markdown_ro(f.name, f.read_text(encoding="utf-8"))
        # abstract và cover letter viết TAY ở gốc latex, không qua build_tex — và đó là
        # hai chỗ tử số mơ hồ in đậm nhất. Chỉ mẫu có "goc" chạy trên chúng: các mẫu
        # khác (ngôn ngữ nháp, đường dẫn) chưa bao giờ được hiệu chỉnh cho văn thư.
        for ten in ("abstract.tex", "cover-letter.tex"):
            f = goc / ten
            if f.exists():
                n_nguon += 1
                hong += quet(f.name, f.read_text(encoding="utf-8"), "goc", args.nop)
        for ten in MD_BAI:
            f = REPO / "paper" / ten
            if f.exists():
                n_nguon += 1
                hong += quet(f"paper/{ten}", f.read_text(encoding="utf-8"), "md", args.nop)

    if args.pdf:
        try:
            from pypdf import PdfReader
        except ImportError:
            print("Cần `pypdf` để đọc PDF: pip install pypdf")
            return 2
        p = Path(args.pdf)
        if not p.exists():
            print(f"Không có {p}.")
            return 2
        n_nguon += 1
        # Quét TỪNG TRANG và báo số trang, không quét một khối gộp: "dấu ** ở dòng 812"
        # không tra được trên một bản PDF, còn "trang 7" thì mở ra xem được ngay.
        for i, pg in enumerate(PdfReader(str(p)).pages, 1):
            hong += [(f"{p.name} trang {i}", nhan, 0, d)
                     for _n, nhan, _dg, d in quet("", pg.extract_text() or "", "pdf", args.nop)]

    # Glyph THIẾU FONT: XeLaTeX bỏ hẳn ký tự khỏi trang và chỉ ghi một dòng
    # "Missing character" vào .log. Không lỗi, không cảnh báo trên màn hình, PDF vẫn
    # ra đủ trang — nên cách duy nhất thấy được là đọc .log. Đợt 19 mất 13 ký tự
    # theo đúng đường này TRÊN BẢN --final, tức trên bản đem nộp: 7 dấu ↔ ở cột
    # "Boundary" của bảng hỏng-âm-thầm, 4 nhãn hàng ①②③ của bảng điểm hoạt động,
    # một dấu ⚠ mở chú thích công bố bảng không có nửa đối chứng âm, một dấu phẩy trên.
    #
    # Đây là chỗ thứ ba của cùng một câu hỏi: .tex là cái ta dựng, .pdf là cái ta
    # trích được, .log là cái bộ dịch THỪA NHẬN nó đã bỏ đi. Chỗ thứ ba bắt được
    # thứ hai chỗ kia không bắt được — một ký tự đã rơi thì không còn trong PDF để
    # mà tìm, nên quét PDF vĩnh viễn im lặng về nó.
    glyph: list[tuple[str, int]] = []
    if args.log:
        p = Path(args.log)
        if not p.exists():
            print(f"Không có {p}.")
            return 2
        n_nguon += 1
        dem: dict[str, int] = {}
        for m in re.finditer(r"Missing character: There is no (.+?) in font",
                             p.read_text(encoding="utf-8", errors="replace")):
            dem[m.group(1)] = dem.get(m.group(1), 0) + 1
        glyph = sorted(dem.items(), key=lambda kv: -kv[1])

    # ---------------------------------------------------------------------
    # CỔNG KÝ TỰ (việc 81a). Câu hỏi nó trả lời KHÁC câu hỏi của cổng .log:
    #
    #   .log hỏi  "bộ dịch có THỪA NHẬN đã bỏ ký tự nào không?"  -> bắt glyph
    #             thiếu font, nhưng CHỈ khi XeLaTeX chịu ghi ra.
    #   cổng này hỏi "ký tự trong NGUỒN có tới được TRANG không?" -> bắt cả
    #             những đường mất chữ mà .log im lặng: một ký tự bị một bước
    #             xử lý chuỗi nào đó nuốt trước khi tới LaTeX thì .log không
    #             có gì để ghi, vì LaTeX chưa bao giờ nhìn thấy nó.
    #
    # Luật: mỗi ký tự ngoài ASCII trong markdown nguồn phải hoặc (a) đã KHAI
    # trong anh_xa.json — tức builder biết nó và cố ý đổi nó thành lệnh LaTeX —
    # hoặc (b) CÓ MẶT trong text trích từ PDF, tức font in được nó. Ký tự nào
    # không thoả cả hai là ký tự đã rơi âm thầm.
    #
    # Vì sao đối chiếu với anh_xa.json chứ không import bảng: file ấy do CHÍNH
    # lần dựng sinh ra .tex ghi ra, nên cổng không bao giờ so với một bản sao
    # chép tay đã trôi. Cùng lý do `numbers.json` sinh từ sổ chứ không gõ lại.
    thieu_kytu: list[tuple[str, int, str]] = []
    if args.kytu:
        from pypdf import PdfReader
        if not args.pdf:
            print("--kytu cần --pdf (phải có bản render để đối chiếu).")
            return 2
        f_ax = goc / "anh_xa.json"
        if not f_ax.exists():
            print(f"Chưa có {f_ax}. Chạy build_tex.py trước.")
            return 2
        import json
        ax = json.loads(f_ax.read_text(encoding="utf-8"))
        khai = set(ax["anh_xa"])
        pdf_text = "\n".join((pg.extract_text() or "")
                             for pg in PdfReader(str(Path(args.pdf))).pages)

        # Bên "nguồn" của phép đối chiếu là sections/*.tex ĐÃ DỰNG, không phải
        # markdown thô. Đây là một sửa đổi có chủ ý so với mô tả của việc 81a, và
        # lý do là một BÁO ĐỘNG GIẢ THẬT đã xảy ra khi thử theo markdown thô:
        #
        #   trên bản --final, cổng báo 'ố' U+1ED1 x11 "không tới trang". Đúng là nó
        #   không tới trang — vì --final CỐ Ý tước mọi khối nháp tiếng Việt. Không
        #   có gì mất cả; cổng đang đọc một việc làm đúng thành một lỗi.
        #
        # Markdown thô không phân biệt được "bị bỏ có chủ ý" với "rơi âm thầm", nên
        # một cổng đặt ở đó KHÔNG THỂ về 0 trên bản nộp — và cổng không về 0 được thì
        # sẽ bị tắt. Bản dựng .tex thì phân biệt được: nó là thứ builder ĐÃ QUYẾT ĐỊNH
        # đưa cho LaTeX, sau khi đã tước xong. Một ký tự có trong .tex mà không có
        # trong PDF là mất thật, không có cách đọc nào khác.
        #
        # Đây đúng là hình dạng của 13 glyph rơi ở đợt 19: chúng CÓ trong .tex và
        # biến mất khỏi PDF. Cổng này bắt đúng lớp lỗi ấy, không bắt oan lớp kia.
        dem: dict[str, int] = {}
        for f in sorted(SECTIONS.glob("*.tex")):
            for ch in f.read_text(encoding="utf-8"):
                if ord(ch) > 127:
                    dem[ch] = dem.get(ch, 0) + 1
        for ch, n in sorted(dem.items(), key=lambda kv: -kv[1]):
            if ch in khai or ch in pdf_text:
                continue
            thieu_kytu.append((ch, n, f"U+{ord(ch):04X}"))

    print(f"Nguồn quét: {n_nguon}")
    if args.kytu:
        print(f"  ký tự .tex KHÔNG tới trang   {len(thieu_kytu):4d}      <-- mục tiêu 0"
              f"   [tex→pdf]   (chưa khai trong anh_xa.json VÀ không có mặt trong PDF)")
        for ch, n, u in thieu_kytu[:15]:
            print(f"     {ch!r} {u} x{n} trong nguồn")
    if args.log:
        tong_glyph = sum(n for _g, n in glyph)
        print(f"  glyph RƠI khỏi trang  {tong_glyph:4d}      <-- mục tiêu 0   [log]"
              f"   (thiếu font: XeLaTeX bỏ hẳn ký tự, chỉ ghi một dòng vào .log)")
        for g, n in glyph:
            print(f"     {g!r} x{n}")
    da_chay = tuple(x for x, co in (("tex", quet_tex), ("pdf", bool(args.pdf))) if co)
    for nhan, _rx, ly_do, tren, chi_nop in MAU:
        pham_vi = tuple(t for t in tren if t in da_chay)
        if not pham_vi or (chi_nop and not args.nop):
            continue
        n = sum(1 for h in hong if h[1] == nhan)
        print(f"  dấu `{nhan}` còn sót   {n:4d}      <-- mục tiêu 0"
              f"   [{'+'.join(pham_vi)}]   ({ly_do})")
    if quet_tex:
        n = sum(1 for h in hong if h[1] == "markdown-rò")
        print(f"  dấu `markdown-rò` còn sót   {n:4d}      <-- mục tiêu 0   [tex]"
              "   (*…* hoặc _…_ nguyên văn ngoài toán/verbatim, quét trên đoạn đã gộp dòng)")

    if hong:
        print("\n  -- chỗ rò --")
        for nguon, nhan, dong, d in hong[:25]:
            vi_tri = f"{nguon}:{dong}" if dong else nguon
            print(f"     [{nhan}] {vi_tri}: {d[:100]}")
        if len(hong) > 25:
            print(f"     ... và {len(hong) - 25} chỗ nữa")

    rc = 1 if (hong or glyph or thieu_kytu) else 0
    print("\n" + ("ĐẠT: không dấu Markdown rò, không glyph rơi, ký tự nguồn tới đủ trang."
                  if rc == 0 else
                  "CHƯA ĐẠT — vá build_tex.py rồi dựng lại. ĐỪNG sửa tay file .tex:"
                  " nó là bản dựng, sửa tay thì lần dựng sau mất."))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
