r"""Đếm mục tài liệu tham khảo KHÔNG có định danh resolve được — luật C5 của đợt 11.

    python scripts\check_refs.py                     # kiểm paper/REFERENCES.md
    python scripts\check_refs.py --pdf bai.pdf       # kiểm trên BẢN PDF ĐÃ RENDER

## Vì sao có script này

Chủ nhân đã ăn một desk-reject với lý do nguyên văn *"references can not be verified"*.
Cổng nộp chạy máy đối chiếu Crossref **trên file PDF đã render**, và bibliography không in
DOI bị đọc thành dấu hiệu **trích dẫn do AI bịa**. Bài này do AI nháp, nên rủi ro ấy áp
thẳng vào ta.

**Mục tiêu: 0 mục không có định danh, đếm trên bản PDF.** Đếm bằng máy, không đếm bằng mắt —
đếm bằng mắt là đúng cái đã hỏng lần trước.

## Định danh nào được tính

- DOI: `10.xxxx/...` (kể cả `10.48550/arXiv.<id>` cho preprint)
- URL `https://…` cho kỷ yếu/JMLR/PMLR không có DOI
- `arXiv:<id>` — **tính, nhưng bị đếm riêng**: tỉ trọng preprint cao là một tín hiệu xấu,
  và bài nào đã lên bản hội nghị/tạp chí thì phải trích bản archival.

`[[CITE-NEEDED]]` **không** phải định danh — nó là chỗ chưa xác minh, và script đếm riêng
để nó không lẫn vào con số "đạt".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
REFS = REPO / "paper" / "REFERENCES.md"

DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
URL = re.compile(r"https?://[^\s\"'<>,;)\]]+", re.I)
ARXIV = re.compile(r"\barXiv:\s*\d{4}\.\d{4,5}", re.I)
CITE_NEEDED = re.compile(r"\[\[CITE-NEEDED", re.I)


def doc_muc(text: str) -> list[str]:
    """Mỗi mục là một đoạn bắt đầu bằng '- ' hoặc '[n]'. Gộp dòng nối tiếp."""
    muc: list[str] = []
    cur: list[str] = []
    for line in text.split("\n"):
        if re.match(r"^\s*(-\s|\[\d+\])", line):
            if cur:
                muc.append(" ".join(cur))
            cur = [line.strip()]
        elif cur and line.strip():
            cur.append(line.strip())
        elif cur:
            muc.append(" ".join(cur)); cur = []
    if cur:
        muc.append(" ".join(cur))
    return muc


REF_HEAD = re.compile(r"^\s*(REFERENCES|References|TÀI LIỆU THAM KHẢO)\s*$", re.M)
ENTRY = re.compile(r"\[\d{1,3}\]")


def doc_muc_pdf(text: str) -> list[str]:
    """Tách MỤC TÀI LIỆU trên bản PDF — không phải "mọi dòng có năm".

    Bản trước đếm mọi dòng chứa một con số bốn chữ số, và nó KHÔNG THỂ về 0 trên
    một bài IEEE hai cột, vì hai lý do cấu trúc:

      1. Văn xuôi nhắc năm ("Self-RAG (Asai et al., ICLR 2024) fine-tunes…") bị
         đếm như một mục tham khảo thiếu DOI. Nó không phải mục tham khảo.
      2. Một mục tham khảo trong cột hẹp bị ngắt thành ba bốn dòng, nên dòng mang
         năm và dòng mang DOI là HAI dòng khác nhau; mục đúng vẫn bị báo thiếu.

    Một cổng có mục tiêu 0 mà không thể về 0 thì sẽ bị tắt trong một buổi chiều —
    và cổng này là cổng chặn desk-reject, nên để nó chết là đắt nhất trong tất cả.

    Nay: cắt từ tiêu đề REFERENCES trở đi, tách theo dấu "[n]" mà IEEEtran in ra,
    và nối lại mọi dòng của cùng một mục. Đó cũng là cách bộ quét của nhà xuất bản
    nhìn tệp: từng mục thư mục, không phải từng dòng.
    """
    m = None
    for m in REF_HEAD.finditer(text):
        pass                      # lấy lần xuất hiện CUỐI: mục lục có thể nhắc trước
    if m is None:
        return []                 # không có thư mục -> 0 mục, và main() sẽ nói rõ
    than = text[m.end():]

    muc: list[str] = []
    vi_tri = [x.start() for x in ENTRY.finditer(than)]
    for i, b in enumerate(vi_tri):
        e = vi_tri[i + 1] if i + 1 < len(vi_tri) else len(than)
        muc.append(" ".join(than[b:e].split()))
    return muc


BIB = REPO / "paper" / "latex" / "refs.bib"
SECTIONS = REPO / "paper" / "latex" / "sections"


def doi_chieu_cite() -> int:
    """Đối chiếu HAI CHIỀU giữa refs.bib và \\cite trong thân bài.

    Guide bản sống của IP&M nói thẳng cả hai chiều, và hai chiều hỏng theo hai kiểu
    khác nhau nên phải đếm riêng:

      thừa  — mục có trong refs.bib mà KHÔNG có \\cite nào trỏ tới. Đây là ĐỘN:
              thư mục dài ra mà bài không bàn tới nguồn ấy. `elsarticle-num` chỉ in
              những mục ĐƯỢC trích, nên một mục thừa còn KHÔNG XUẤT HIỆN trên
              trang — tức nó vô hình với mọi cổng chỉ đọc PDF, và vẫn là một lời
              khai sai trong file nguồn đem nộp.
      thiếu — có \\cite{khoa} mà refs.bib KHÔNG có `khoa`. bibtex in "[?]" ra trang
              và chỉ ghi một dòng cảnh báo vào .blg. Không lỗi, PDF vẫn đủ trang.

    Luật lọc của đợt 20 (mỗi nguồn thêm phải được BÀN TỚI trong thân bài) chính là
    chiều "thừa", và đây là chỗ nó thành mã thoát thay vì thành lời hứa.
    """
    if not BIB.exists() or not SECTIONS.is_dir():
        print(f"Thiếu {BIB} hoặc {SECTIONS}.")
        return 2
    khoa_bib = set(re.findall(r"^@\w+\{([^,]+),", BIB.read_text(encoding="utf-8"), re.M))
    than = "\n".join(f.read_text(encoding="utf-8") for f in sorted(SECTIONS.glob("*.tex")))
    # \cite{a} và \cite{a,b}
    khoa_cite: set[str] = set()
    for m in re.finditer(r"\\cite\{([^}]*)\}", than):
        khoa_cite |= {k.strip() for k in m.group(1).split(",") if k.strip()}

    thua = sorted(khoa_bib - khoa_cite)
    thieu = sorted(khoa_cite - khoa_bib)
    print(f"  mục trong refs.bib   {len(khoa_bib)}")
    print(f"  khoá được \\cite      {len(khoa_cite)}")
    print(f"  THỪA (bib, không cite) {len(thua)}      <-- mục tiêu 0  (độn)")
    print(f"  THIẾU (cite, không bib) {len(thieu)}      <-- mục tiêu 0  (ra [?] trên trang)")
    for ten, ds in (("THỪA — có trong refs.bib mà không ai trích", thua),
                    ("THIẾU — được trích mà refs.bib không có", thieu)):
        if ds:
            print(f"\n  -- {ten} --")
            for k in ds:
                print(f"     {k}")
    return 1 if (thua or thieu) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cite", action="store_true",
                    help="đối chiếu HAI CHIỀU refs.bib <-> \\cite trong sections/*.tex")
    ap.add_argument("--pdf", help="kiểm trên bản PDF đã render (cần pypdf)")
    enable_utf8_console()   # console Windows mac dinh la cp1258, in tieng Viet la vo
    args = ap.parse_args()

    if args.cite:
        print(r"Đối chiếu HAI CHIỀU refs.bib <-> \cite")
        rc = doi_chieu_cite()
        print("\n" + ("ĐẠT: mọi mục đều được trích, mọi trích dẫn đều có mục."
                      if rc == 0 else "CHƯA ĐẠT — xem danh sách trên."))
        return rc

    if args.pdf:
        try:
            from pypdf import PdfReader
        except ImportError:
            print("Cần `pypdf` để đọc PDF: pip install pypdf")
            return 2
        text = "\n".join((pg.extract_text() or "") for pg in PdfReader(args.pdf).pages)
        nguon = args.pdf
        muc = doc_muc_pdf(text)
    else:
        if not REFS.exists():
            print(f"Chưa có {REFS}. Tạo file rồi chạy lại.")
            return 2
        text = REFS.read_text(encoding="utf-8")
        nguon = str(REFS)
        # Chỉ đọc phần DANH MỤC, bỏ phần hướng dẫn ở đầu và phần trạng thái ở cuối —
        # gạch đầu dòng của phần hướng dẫn không phải mục tham khảo, và đếm nhầm chúng
        # thì con số "chưa có định danh" thành vô nghĩa.
        phan = re.split(r"^---\s*$", text, flags=re.M)
        than = [k for k in phan if "## Đã xác minh" in k or "## CHƯA xác minh" in k]
        if not than:
            print("Không tìm thấy mục '## Đã xác minh' / '## CHƯA xác minh' trong REFERENCES.md")
            return 2
        muc = doc_muc(chr(10).join(than))

    thieu, co_arxiv_thoi, cite_needed, dat = [], [], [], 0
    for m in muc:
        if CITE_NEEDED.search(m):
            cite_needed.append(m); continue
        co_doi = bool(DOI.search(m))
        co_url = bool(URL.search(m))
        co_arxiv = bool(ARXIV.search(m))
        if co_doi or co_url:
            dat += 1
            if not co_doi and co_arxiv:
                co_arxiv_thoi.append(m)
        elif co_arxiv:
            dat += 1; co_arxiv_thoi.append(m)
        else:
            thieu.append(m)

    print(f"Nguồn: {nguon}")
    print(f"  mục xét            {len(muc)}")
    print(f"  có định danh       {dat}")
    print(f"  CHƯA có định danh  {len(thieu)}      <-- mục tiêu 0")
    print(f"  còn [[CITE-NEEDED]] {len(cite_needed)}  (chưa xác minh, KHÔNG tính là đạt)")
    print(f"  chỉ có arXiv        {len(co_arxiv_thoi)}  (hạn chế tỉ trọng; ưu tiên bản archival)")

    for ten, ds in (("CHƯA có định danh", thieu), ("còn [[CITE-NEEDED]]", cite_needed),
                    ("chỉ có arXiv", co_arxiv_thoi)):
        if ds:
            print(f"\n  -- {ten} --")
            for m in ds[:12]:
                print(f"     {m[:120]}")

    rc = 1 if (thieu or cite_needed) else 0
    print("\n" + ("ĐẠT: mọi mục đều có định danh resolve được." if rc == 0
                  else "CHƯA ĐẠT — sửa trước khi render PDF nộp."))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
