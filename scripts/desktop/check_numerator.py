r"""Cổng tử số (đợt 30 việc 121): mọi phân số k/n trong bài phải là MỘT claim của `paper/numbers.json`
— hoặc chính nó, hoặc phần bù (n−k)/n của nó — và tử số phải đếm đúng tính chất câu đang nói.

    python desktop\scripts\check_numerator.py                       # cây TSE: thân rc, supplement cảnh báo
    python desktop\scripts\check_numerator.py --goc <latex> --moi-la-than   # cây cũ (đối chứng IP&M)

Vì sao cần chiều: lỗi desk-reject 16/09 ("identical transcripts on 0/31") dùng ĐÚNG con số 0/31 có
trong sổ — chỉ sai tính chất: sổ đếm số lần ĐỔI, câu nói số lần GIỐNG. So số trần thì cổng xanh trên
chính lỗi nó sinh ra để bắt. Nên:
  - claim có chiều khai ở `CHIEU` (đổi | giống); câu có chiều nếu có từ chỉ tính chất ngay sau phân số
    (trong cùng cụm, trước dấu ngoặc) hoặc gần nhất phía trước (trong cùng mệnh đề);
  - cùng chiều ⇒ k phải = k của claim; ngược chiều ⇒ k phải = n − k của claim;
  - thiếu chiều ở một phía ⇒ chấp nhận cả k lẫn n − k (quy ước phần bù, CLAIM-EVIDENCE D3-bis).
Một nguồn sự thật: 31/31 không là claim mới, nó là `stt.local.stable` (0/31) nói chiều ngược.

rc=1 khi thân bài (abstract + sections) có phân số không phân giải được hoặc sai chiều.
Supplement: chỉ in danh sách (nợ ghi ở CLAIM-EVIDENCE; trả bằng cách sinh từ numbers.json).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOC = REPO / "Submission TSE" / "latex"
SUPP = REPO / "Submission TSE" / "supplement" / "sections"
NUMBERS = REPO / "paper" / "numbers.json"

# Chiều của tử số trong sổ. Đọc từ `value`/`conv` của từng claim; khai tay ở đây vì numbers.json
# chưa có cột chiều — mỗi dòng có đối chứng trong test (claim phải tồn tại).
CHIEU = {
    "stt.local.stable": "doi",      # 0/31 lượt transcript đổi
    "stt.hosted.day": "doi",        # 5/31 đổi qua một ngày
    "stt.hosted.session": "doi",    # 2/31 đổi ở 180 s
    "stt.det.local": "doi",         # câu bất ổn
    "ow.rerun.text": "giong",       # 7/23 "chữ trùng từng ký tự"
    "ow.rerun.lang": "giong",       # 23/23 "nhãn không đổi"
    "gr.decision": "doi",           # 0/30 quyết định tra đổi
    "gr.domains": "doi",            # 15/21 tập miền đổi
    "gr.neg_control": "doi",        # 7/9 câu nói ra đổi (đối chứng âm)
}

PHAN_SO = re.compile(r"(?<![\d/.,])(\d+)/(\d+)(?![\d/])")
# "unchanged" phải khớp GIỐNG trước; \bchanged không khớp bên trong "unchanged".
GIONG = re.compile(r"\b(?:byte-)?identical\b|\bunchanged\b|\bheld\b|\bstable\b|\breproduced\b|\bthe same\b|\bmatch(?:ed|es)?\b", re.I)
DOI = re.compile(r"\bchang(?:ed|es|e)\b|\bdiffer(?:ed|s)?\b|\bdifferent\b|\bflipped\b|\bdrift(?:ed|s)?\b|\bunstable\b", re.I)
CHAN_SAU = re.compile(r"[(\);,]|\.\s|\$")
CHAN_TRUOC = re.compile(r"[(\);]|\.\s")


def chieu_tu(s: str) -> list[tuple[int, str]]:
    g = [(m.start(), "giong") for m in GIONG.finditer(s)]
    d = [(m.start(), "doi") for m in DOI.finditer(s)]
    return sorted(g + d)


def chieu_cau(dong: str, a: int, b: int) -> str | None:
    """Chiều của phân số dong[a:b]: từ ngay sau (tới dấu chặn, ≤ 30 ký tự), không có thì từ gần nhất
    phía trước trong cùng mệnh đề (≤ 120 ký tự, dừng ở ngoặc / chấm phẩy / hết câu)."""
    sau = dong[b:b + 30]
    m = CHAN_SAU.search(sau)
    sau = sau[:m.start()] if m else sau
    t = chieu_tu(sau)
    if t:
        return t[0][1]
    truoc = dong[max(0, a - 120):a]
    ms = list(CHAN_TRUOC.finditer(truoc))
    if ms:
        truoc = truoc[ms[-1].end():]
    t = chieu_tu(truoc)
    return t[-1][1] if t else None


def claim_phan_so(numbers: dict) -> list[tuple[int, int, str, str | None]]:
    ra = []
    for ten, c in numbers.items():
        for truong in ("value", "probe"):
            for m in PHAN_SO.finditer(str(c.get(truong) or "")):
                k, n = int(m.group(1)), int(m.group(2))
                if (k, n, ten) not in {(x[0], x[1], x[2]) for x in ra}:
                    ra.append((k, n, ten, CHIEU.get(ten)))
    return ra


def phan_giai(k: int, n: int, p: str | None, claims) -> tuple[str, str]:
    """('ok'|'sai-chieu'|'khong-co', lời giải thích)."""
    sai = []
    for kc, nc, ten, pc in claims:
        if nc != n:
            continue
        if p is None or pc is None:
            if k == kc:
                return "ok", ten
            if k == n - kc:
                return "ok", f"{ten} (phần bù)"
        elif p == pc:
            if k == kc:
                return "ok", ten
            if k == n - kc:
                sai.append(f"{ten}: sổ đếm '{pc}' {kc}/{n}, câu nói '{p}' ⇒ phải {kc}/{n}")
        else:
            if k == n - kc:
                return "ok", f"{ten} (phần bù)"
            if k == kc:
                sai.append(f"{ten}: sổ đếm '{pc}' {kc}/{n}, câu nói '{p}' ⇒ phải {n - kc}/{n}")
    if sai:
        return "sai-chieu", "; ".join(sai)
    return "khong-co", "không claim nào (kể cả phần bù) trong numbers.json"


def quet(files: list[Path], claims) -> list[dict]:
    ra = []
    for f in files:
        for i, dong in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if dong.lstrip().startswith("%"):
                continue
            dong = re.sub(r"(?<!\\)%.*$", "", dong)
            for m in PHAN_SO.finditer(dong):
                k, n = int(m.group(1)), int(m.group(2))
                p = chieu_cau(dong, m.start(), m.end())
                kq, ly = phan_giai(k, n, p, claims)
                ra.append({"file": f, "dong": i, "ps": m.group(0), "chieu": p, "kq": kq, "ly": ly,
                           "ngu_canh": dong[max(0, m.start() - 60):m.end() + 30].strip()})
    return ra


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goc", default=str(GOC), help="thư mục latex chứa abstract.tex và sections/")
    ap.add_argument("--supplement", default=str(SUPP), help="thư mục .tex của supplement (chỉ cảnh báo)")
    ap.add_argument("--numbers", default=str(NUMBERS))
    ap.add_argument("--moi-la-than", action="store_true",
                    help="coi mọi sections/*.tex là thân bài (cây IP&M một tài liệu), bỏ supplement")
    a = ap.parse_args(argv)
    numbers = json.loads(Path(a.numbers).read_text(encoding="utf-8"))["numbers"]
    thieu = [k for k in CHIEU if k not in numbers]
    if thieu:
        print(f"check_numerator: CHIEU khai claim không có trong numbers.json: {thieu}")
        return 2
    claims = claim_phan_so(numbers)
    goc = Path(a.goc)
    than = [goc / "abstract.tex"] + sorted((goc / "sections").glob("*.tex"))
    than = [f for f in than if f.exists()]
    supp = [] if a.moi_la_than else sorted(Path(a.supplement).glob("*.tex"))
    kt = quet(than, claims)
    ks = quet(supp, claims)
    do = [x for x in kt if x["kq"] != "ok"]
    canh = [x for x in ks if x["kq"] != "ok"]
    for x in do:
        print(f"ĐỎ  {x['file'].name}:{x['dong']}  {x['ps']}  [{x['kq']}] {x['ly']}\n     … {x['ngu_canh']}")
    if canh:
        print(f"\ncảnh báo supplement: {len(canh)} phân số chưa có claim (nợ, không chặn):")
        for x in canh:
            print(f"    {x['file'].name}:{x['dong']}  {x['ps']}  [{x['kq']}]")
    print(f"\ncheck_numerator: {'CHƯA ĐẠT' if do else 'ĐẠT'} — thân bài {len(kt)} phân số, {len(do)} đỏ · "
          f"supplement {len(ks)} phân số, {len(canh)} cảnh báo")
    return 1 if do else 0


if __name__ == "__main__":
    sys.exit(main())
