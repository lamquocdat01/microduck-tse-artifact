r"""Kiểm bộ câu thu âm M1 tầng chính so với 31 utterance pilot — TRƯỚC khi thu (AMENDMENT 02).

    python scripts\m1_kiem_bo_cau.py                                  # bộ đang dùng
    python scripts\m1_kiem_bo_cau.py --bo <file.json>                 # bộ khác
    python scripts\m1_kiem_bo_cau.py --doi-chung                      # đối chứng dương: kiểm chính bộ pilot

Ba kiểm tra của chủ nhân, mỗi cái một ngưỡng máy đọc được. So ở mức UTTERANCE (pilot đọc
câu 6 bốn lần, nên trọng số là số lần đọc, không phải số câu):

(a) tỉ lệ vi/en lệch ≤ 10 điểm %; số từ trung bình lệch ≤ 1,0; tỉ lệ câu rất ngắn (≤ 2 từ)
    lệch ≤ 10 điểm %.
(b) không câu nào trùng/gần trùng câu pilot: difflib ratio < 0,6 VÀ Jaccard từ < 0,5.
    Gần trùng NGHĨA (dịch sang tiếng kia) máy không bắt được — bảng in cặp gần nhất để
    người đọc soát.
(c) câu có "từ khó cho ASR" ≥ 1/3, và không thấp hơn pilot quá 15 điểm % (để tầng chính
    không dễ hơn pilot). "Khó" nhận bằng LUẬT, áp y hệt cho cả hai bộ: chữ số; số đếm/thứ
    trong tuần viết bằng chữ; từ viết hoa không đứng đầu câu (tên riêng); từ có hoa ở giữa
    hoặc toàn hoa (PhD, MySQL, SAP).

rc = 0 khi cả ba đạt; 1 khi không.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "docs/baseline/realvoice_2026-09-06_v2_refs.json"
BO = REPO / "docs/benchmark/M1_rv2_sentences.json"

SO_CHU = set("""một hai ba bốn năm lăm sáu bảy tám chín mười mươi mốt tư trăm nghìn ngàn triệu rưỡi
one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand
monday tuesday wednesday thursday friday saturday sunday nhật""".split())


def tu(cau: str) -> list[str]:
    return re.findall(r"[\w'’]+", cau)


def tu_kho(cau: str) -> list[str]:
    ra = []
    for i, w in enumerate(tu(cau)):
        if any(c.isdigit() for c in w) or w.lower() in SO_CHU:
            ra.append(w)
        elif i > 0 and w[0].isupper() and w != "I":
            ra.append(w)
        elif len(w) > 1 and any(c.isupper() for c in w[1:]):
            ra.append(w)
    return ra


def thong_ke(utts: list[dict]) -> dict:
    n = len(utts)
    sotu = [len(tu(u["text"])) for u in utts]
    return {"n": n, "vi": sum(u["lang"] == "vi" for u in utts) / n,
            "tu_tb": statistics.mean(sotu), "tu_trung_vi": statistics.median(sotu),
            "ngan": sum(s <= 2 for s in sotu) / n,
            "kho": sum(bool(tu_kho(u["text"])) for u in utts) / n}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bo", default=str(BO))
    ap.add_argument("--doi-chung", action="store_true")
    args = ap.parse_args()

    pilot = list(json.loads(PILOT.read_text(encoding="utf-8")).values())
    pilot_cau = list(dict.fromkeys(u["text"] for u in pilot))
    if args.doi_chung:
        bo = [{"text": t, "lang": next(u["lang"] for u in pilot if u["text"] == t)} for t in pilot_cau]
        lan_doc = 3
    else:
        d = json.loads(Path(args.bo).read_text(encoding="utf-8"))
        bo, lan_doc = d["cau"], int(d["lan_doc"])
    moi = [c for c in bo for _ in range(lan_doc)]
    a, b = thong_ke(pilot), thong_ke(moi)

    print(f"(a) phân bố — mức utterance: pilot n={a['n']}, bộ mới n={b['n']} ({len(bo)} câu × {lan_doc})")
    print(f"    {'':22s} {'pilot':>8s} {'bộ mới':>8s} {'lệch':>8s} {'ngưỡng':>8s}")
    loi = []
    for k, ten, nguong, pct in (("vi", "tỉ lệ tiếng Việt", 0.10, True), ("tu_tb", "số từ trung bình", 1.0, False),
                                ("tu_trung_vi", "số từ trung vị", None, False),
                                ("ngan", "câu ≤ 2 từ", 0.10, True), ("kho", "có từ khó ASR", None, True)):
        lech = b[k] - a[k]
        f = (lambda x: f"{x:.1%}") if pct else (lambda x: f"{x:.2f}")
        ok = nguong is None or abs(lech) <= nguong
        if not ok:
            loi.append(f"(a) {ten} lệch {f(abs(lech))} > {f(nguong)}")
        print(f"    {ten:22s} {f(a[k]):>8s} {f(b[k]):>8s} {('+' if lech >= 0 else '') + f(lech):>8s} "
              f"{(f(nguong) if nguong is not None else '—'):>8s} {'' if ok else '❌'}")

    print("\n(b) trùng / gần trùng với câu pilot (cặp gần nhất của từng câu mới)")
    for c in bo:
        s = c["text"].lower()
        best = max(pilot_cau, key=lambda p: difflib.SequenceMatcher(None, s, p.lower()).ratio())
        r = difflib.SequenceMatcher(None, s, best.lower()).ratio()
        A, B = set(w.lower() for w in tu(c["text"])), set(w.lower() for w in tu(best))
        j = len(A & B) / len(A | B) if A | B else 0
        xau = r >= 0.6 or j >= 0.5
        if xau:
            loi.append(f"(b) gần trùng: {c['text']!r} ~ {best!r} (ratio {r:.2f}, Jaccard {j:.2f})")
        print(f"    {'❌' if xau else '  '} {r:.2f} {j:.2f}  {c['text'][:44]:44s} ~ {best[:40]}")

    kho_cau = [c for c in bo if tu_kho(c["text"])]
    print(f"\n(c) câu có từ khó ASR: {len(kho_cau)}/{len(bo)} = {len(kho_cau)/len(bo):.0%} "
          f"(pilot {a['kho']:.0%} theo utterance; sàn 1/3 và ≥ pilot − 15 điểm)")
    for c in bo:
        print(f"    {'✓' if tu_kho(c['text']) else '·'} {c['text'][:52]:52s} {', '.join(tu_kho(c['text']))}")
    if b["kho"] < 1 / 3:
        loi.append(f"(c) từ khó {b['kho']:.0%} < 1/3")
    if b["kho"] < a["kho"] - 0.15:
        loi.append(f"(c) từ khó {b['kho']:.0%} thấp hơn pilot {a['kho']:.0%} quá 15 điểm")

    print("\n" + ("ĐẠT cả ba kiểm tra." if not loi else "CHƯA ĐẠT:\n  " + "\n  ".join(loi)))
    return 0 if not loi else 1


if __name__ == "__main__":
    raise SystemExit(main())
