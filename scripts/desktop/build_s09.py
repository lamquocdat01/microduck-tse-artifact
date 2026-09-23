# -*- coding: utf-8 -*-
r"""Sinh các khối KẾT QUẢ của `paper/s09-study-records.md` — việc 143 bước 3, đợt 27i.

    python scripts\build_s09.py

Cùng lý do với `build_muc11.py`: S9 là **hồ sơ** của mẻ đăng ký trước, nên mọi ô kết quả phải đọc
thẳng từ file đo chứ không gõ tay. Ba nguồn duy nhất: `M3_20260916_v1.jsonl`,
`M6_M7_cham_20260923.json`, và bảng hằng `O` / `LOAI_A06` của `cham_m6_m7.py`.

Mốc sinh dùng chính cơ chế `[[...]]` của bộ dựng: một dòng `[[SINH …]]` / `[[HẾT …]]` biến mất
hoàn toàn trên bản `--final`, nên chúng không đi ra trang in. Lần chạy đầu chúng thay cờ
`[[M-PENDING: …]]` tương ứng; lần sau thay đúng phần giữa hai mốc, nên chạy bao nhiêu lần cũng ra
một kết quả (`git diff` sạch).
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cham_m6_m7 as C  # noqa: E402

S09 = REPO / "paper" / "s09-study-records.md"
CHAM = REPO / "docs" / "benchmark" / "M6_M7_cham_20260923.json"
PLAN = REPO / "docs" / "benchmark" / "runner" / "plan.json"
NL = chr(10)

# Sổ cái và supplement viết cho hai người đọc khác nhau: sổ tiếng Việt, supplement tiếng Anh.
TANG = {"STT": "recognition", "routing": "retrieval decision",
        "ngôn ngữ trả lời": "response language", "grounding": "grounding"}
QUAN_SAT = {"nhãn ngôn ngữ": "language label", "transcript": "transcript",
            "lookup": "retrieve-or-not", "text thô": "raw text", "nhãn": "language label",
            "reply_text": "reply text", "domain-set": "source domains", "text": "answer text"}
DU_DOAN = {"ổn định": "stable", "không": "not stable"}
PHAN_QUYET = {"đúng": "correct", "sai": "wrong", "không phân định": "undecided"}


def pin(p: str) -> str:
    return p.replace("pinnable", "caller-pinnable").replace("delegated", "delegated")


def ti_le(k: int, n: int) -> str:
    return f"{k}/{n}"


def khoi_m3() -> list[str]:
    """S9.1 — bảng 14 mốc, kèm GIỜ THỰC ĐO cạnh giờ danh nghĩa (I-15, I-19)."""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    moc: dict[str, dict] = OrderedDict()
    for line in (REPO / plan["results"]["M3"]).read_bytes().splitlines():
        if not line.strip():
            continue
        r = json.loads(line.decode("utf-8"))
        if r.get("status") != "ok" or r["task_id"].startswith("M3|probe-nosearch"):
            continue
        moc.setdefault(r["due"], {})[r["task_id"].split("|")[-1]] = r
    keys = sorted(moc)
    g = moc[keys[0]]
    ra = ["| # | milestone (nominal) | actually measured | lateness | decision changed | "
          "source domains changed | answer text changed |",
          "|---|---|---|---|---|---|---|"]
    for j, k in enumerate(keys, 1):
        v = moc[k]
        ids = sorted(set(g) & set(v))
        a = sum(1 for i in ids if bool(v[i]["payload"]["lookup"]) != bool(g[i]["payload"]["lookup"]))
        b = sum(1 for i in ids if set(v[i]["payload"]["domains"]) != set(g[i]["payload"]["domains"]))
        c = sum(1 for i in ids
                if (v[i]["payload"]["answer"] or "").strip() != (g[i]["payload"]["answer"] or "").strip())
        t0 = min(x["ts"] for x in v.values())
        tre = max(x.get("late_by_s") or 0 for x in v.values())
        ra.append("| %d | %s | %s | %s | %s | %s | %s |"
                  % (j, k[:16].replace("T", " "), t0[11:19],
                     ("on time" if tre < 300 else "late by %.0f s" % tre),
                     ti_le(a, len(ids)), ti_le(b, len(ids)), ti_le(c, len(ids))))
    dom = [int(r.split("|")[6].split("/")[0]) for r in ra[3:]]
    txt = [int(r.split("|")[7].split("/")[0]) for r in ra[3:]]
    ra += ["",
           "Milestone 1 against itself is 0/30 in all three columns. **No milestone was missed and none "
           "reached the 7 200 s threshold**; milestones 4 and 5 ran late because the machine slept, so "
           "their numbers are measured at the time in the third column, not at the nominal hour.",
           "",
           "From milestone 2 onward the three columns do not trend: source domains change on "
           f"{min(dom)}–{max(dom)}/30 and answer text on {min(txt)}–{max(txt)}/30 across thirteen "
           "milestones spanning six and a half days. The curve is reported as a description and is not "
           "fitted to a decay model."]
    return ra


def khoi_o() -> list[str]:
    """S9.2 — bảng 17 ô, cột Result sinh từ bản chấm; Status sinh từ LOAI_A06."""
    cham = json.loads(CHAM.read_text(encoding="utf-8"))
    theo_o: dict[int, list[dict]] = {}
    for u in cham["M7"]["don_vi"]:
        theo_o.setdefault(u["o"], []).append(u)
    ra = ["| Cell | Stage | Observable | Pinnability | Prediction | Source | Status | Result |",
          "|---|---|---|---|---|---|---|---|"]
    for so, stage, qs, pnb, dd, nguon in C.O:
        us = theo_o.get(so, [])
        tt, kq = [], []
        for ng in nguon:
            u = next((x for x in us if x["nguon"] == ng), None)
            ly = C.LOAI_A06.get((so, ng))
            loai = "excluded (%s)" % ("derived" if ly and "suy máy móc" in ly else "pilot-informed") if ly else "scored"
            tt.append((ng, loai))
            if u is None:
                kq.append(f"{ng} —")
                continue
            # Đơn vị bị A06 loại vẫn IN số (không xoá dấu vết) nhưng phán quyết của nó KHÔNG vào
            # mẫu số — nếu in trần như các ô được chấm thì người đọc cộng nhầm thành 26 đơn vị.
            v = PHAN_QUYET[u["phan_quyet"]] + (", underpowered" if u["thieu_luc"] else "")
            if not u["vao_mau_so"]:
                v += " (not counted)"
            kq.append(f"{ng} {ti_le(u['k'], u['n'])} → {v}")
        # Mọi nguồn cùng trạng thái thì in MỘT lần ("scored"), khác nhau mới gắn tên nguồn.
        tt = ([tt[0][1]] if len({l for _, l in tt}) == 1
              else [f"{ng} {l}" for ng, l in tt])
        ra.append("| %d | %s | %s | %s | %s | %s | %s | %s |"
                  % (so, TANG[stage], QUAN_SAT[qs], pin(pnb), DU_DOAN[dd],
                     ", ".join(nguon), "; ".join(tt), "; ".join(kq)))
    t = cham["M7"]["tong_ket"]
    ra += ["",
           f"**Scored units: {t['dung']} correct, {t['sai']} wrong, {t['khong_phan_dinh']} undecided, "
           f"out of {t['mau_so']}.** A further {t['loai_a06']} units are printed and excluded under "
           f"Amendment 06, and {t['thieu_luc_khong_tinh']} carry the underpowered label of A04.5 "
           "(n < 35 cannot reach a Wilson upper bound of 10 % on 0/n), which the amendment named in "
           "advance — S1 cells 1, 3, 4 and M3 cell 15. Underpowered is an entry condition on the "
           "denominator, not a fourth verdict: such a unit is still scored *wrong* if it falls in the "
           "wrong region, and none of the three did."]
    return ra


def khoi_depth() -> list[str]:
    cham = json.loads(CHAM.read_text(encoding="utf-8"))
    d = cham["M7"]["depth"]
    ra = ["| Group | Units | Result |", "|---|---|---|"]
    for nh in d["nhom"]:
        don = ", ".join("cell %d/%s %s" % (x["o"], x["nguon"], ti_le(x["k"], x["n"])) for x in nh["don_vi"])
        ra.append("| %s | %s | %s |" % (nh["nhom"].replace("×", "x"), don,
                                        nh["ket_qua"].replace("hỗ trợ", "supports").replace("bác", "refutes")))
    ra += ["",
           f"Depth test: **{d['ho_tro']} groups support the depth reading, {d['bac']} refutes it, "
           f"{d['khong_phan_dinh']} undecided.**"]
    return ra


def khoi_m6() -> list[str]:
    cham = json.loads(CHAM.read_text(encoding="utf-8"))
    ra = ["Unit label, because this section carries two different denominators: every number in the "
          "table below is *k of n tests flaky across 19 runs*. The paragraph after it uses *k of n "
          "tests failing in run r*, which counts tests inside a single run and is not comparable.",
          "",
          "| Cell | Kind | decision flaky | artefact flaky | margin artefact − decision | 95 % CI (Newcombe) |",
          "|---|---|---|---|---|---|"]
    for ten in sorted(cham["M6"]["o"]):
        o = cham["M6"]["o"][ten]
        ra.append("| `%s` | %s | %s | %s | %.3f | %.3f to %.3f |"
                  % (ten, "delegated" if o["loai"] == "delegated" else "caller-pinnable",
                     ti_le(o["decision"]["flaky_tests"], o["decision"]["n_tests"]),
                     ti_le(o["artefact"]["flaky_tests"], o["artefact"]["n_tests"]),
                     o["bien_art_tru_dec"], o["newcombe_bien"][0], o["newcombe_bien"][1]))
    rh = cham["M6"]["o"]["routing-hosted"]
    ra += ["",
           "Read the first row precisely: the decision suite **also flakes**, on "
           f"{ti_le(rh['decision']['flaky_tests'], rh['decision']['n_tests'])} tests flaky across 19 runs. "
           f"The result is the **margin**, {rh['bien_art_tru_dec']:.3f} with a Newcombe interval of "
           f"{rh['newcombe_bien'][0]:.3f} to {rh['newcombe_bien'][1]:.3f} — decision-level assertions "
           "flake *less*, not *not at all*. On the two caller-pinnable cells both suites are at 0 and "
           "the interval spans zero, so M6 does not separate them there, and that is printed too."]
    return ra


def khoi_m1() -> list[str]:
    """S9.1b — M1 theo tầng × backend × KHOẢNG CÁCH (tức thì, 180 s, 24 h).

    Bảng này trả lời RQ2 và đồng thời là nguồn thứ ba cho quan sát xuyên suốt: hosted đổi transcript
    ngay ở lượt lặp TỨC THÌ, nên khoảng cách thời gian không phải thứ sinh ra bất ổn.
    """
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    g: dict[tuple[str, str], dict] = {}
    for line in (REPO / plan["results"]["M1"]).read_bytes().splitlines():
        if not line.strip():
            continue
        r = json.loads(line.decode("utf-8"))
        p = r["task_id"].split("|")
        if len(p) < 4 or p[3] == "probe" or "@" in p[2] or r.get("status") != "ok":
            continue
        g.setdefault((p[1], p[2]), {})[p[3]] = r
    dele: list[int] = []
    def tang(i: str) -> str:
        return "S1" if i.startswith("rv1_") else "S2" if i.startswith("wild_") else "S3"
    ra = ["## S9.1b Recognition across three separations (M1)", "",
          "Same audio, same client-settable parameters, three separations from the first run: an "
          "immediate repeat, 180 seconds, and 24 hours. *Transcript* is the artefact, *language label* "
          "the decision computed from it.", "",
          "| Tier | Backend | transcript changed (imm / 180 s / 24 h) | language label changed (imm / 180 s / 24 h) |",
          "|---|---|---|---|"]
    for t in ("S1", "S2", "S3"):
        for be, ten in (("whisper", "caller-pinnable (local)"), ("gemini", "delegated (hosted)")):
            tx, lb = [], []
            for moc in ("t0p", "t180", "t24h"):
                ks = [k for k in g if tang(k[0]) == t and k[1] == be and "t0" in g[k] and moc in g[k]]
                tx.append(ti_le(sum(1 for k in ks if (g[k][moc]["payload"].get("hypothesis") or "").strip()
                                    != (g[k]["t0"]["payload"].get("hypothesis") or "").strip()), len(ks)))
                lb.append(ti_le(sum(1 for k in ks if g[k][moc]["payload"].get("language")
                                    != g[k]["t0"]["payload"].get("language")), len(ks)))
            ra.append("| %s | %s | %s | %s |" % (t, ten, " / ".join(tx), " / ".join(lb)))
            if be == "gemini":
                dele += [int(x.split("/")[0]) for x in tx]
    # Đối chứng âm cho chính bộ sinh (27j việc 2). Lần tính đầu của bảng này ra TOÀN SỐ 0 vì đọc
    # `payload.text` / `payload.language`, trong khi trường thật là `payload.hypothesis`. Toàn số 0
    # trông y hệt "dữ liệu sạch", nên phải có thứ phân biệt: backend delegated ĐÃ BIẾT là đổi
    # (bản chấm ô 2: 3/31, 13/110, 9/205 ở 24 h). Nếu mọi ô delegated bằng 0 thì gần như chắc chắn
    # lát cắt hoặc tên trường sai, không phải hệ đột nhiên tất định.
    if not any(dele):
        raise SystemExit(
            "build_s09: MỌI ô delegated trong S9.1b bằng 0 — gần như chắc chắn đọc sai trường.\n"
            "  đang đọc: payload['hypothesis'] (artefact) và payload['language'] (decision).\n"
            "  Đã biết từ bản chấm ô 2: delegated đổi 3/31, 13/110, 9/205 ở mốc 24 h.\n"
            "  Kiểm tên trường trong M1_*.jsonl trước khi tin kết quả này.")
    ra += ["",
           "Two readings, both flat in separation. The caller-pinnable backend is byte-identical in "
           "every cell, at every separation. The delegated backend changes its transcript **already on "
           "the immediate repeat** and does not change more at 24 hours than it does at zero: whatever "
           "makes it move is not elapsed time. The decision computed from those transcripts is "
           "unchanged everywhere, on both backends and at every separation."]
    return ra


KHOI = [("s09.m1", "bảng M1 theo khoảng cách", khoi_m1),
        ("s09.m3", "bảng 14 mốc", khoi_m3),
        ("s09.cells", "bảng 17 ô", khoi_o),
        ("s09.depth", "kết quả depth", khoi_depth),
        ("s09.m6", "bảng flake M6", khoi_m6)]

# Cờ M-PENDING mà mỗi khối thay thế ở LẦN CHẠY ĐẦU (sau đó thay giữa hai mốc SINH).
CO_CU = {"s09.m1": None,           # chèn mục mới ngay TRƯỚC S9.2
         "s09.m3": "[[M-PENDING: bảng 14 mốc",
         "s09.cells": None,          # thay cả bảng, xem dưới
         "s09.depth": "[[M-PENDING: kết quả depth",
         "s09.m6": "[[M-PENDING: tỉ lệ flaky theo stage"}


def thay(text: str, ma: str, than: list[str]) -> str:
    mo = f"`[[SINH {ma} — sinh bằng scripts/build_s09.py, đừng sửa tay]]`"
    dong = f"`[[HẾT {ma}]]`"
    moi = NL.join([mo] + than + [dong])
    lines = text.split(NL)
    # Dòng mốc phải MỞ ĐẦU một đoạn. Bộ dựng gộp các dòng văn xuôi liền nhau, và chỉ giữ riêng
    # dòng mở bằng `[[` khi nó là dòng ĐẦU đoạn (luật I-12); nếu nó dính ngay dưới một câu thì
    # trên bản --final, chỗ dấu bị bỏ thành một LỖ GIỮA CÂU và bộ dựng từ chối bản nộp.
    def dat(truoc: list[str], than_moi: list[str], sau: list[str]) -> str:
        if truoc and truoc[-1].strip():
            truoc = truoc + [""]
        return NL.join(truoc + than_moi + sau)

    if mo in text:                                   # lần sau: thay giữa hai mốc
        i = lines.index(mo)
        j = lines.index(dong)
        return dat(lines[:i], moi.split(NL), lines[j + 1:])
    if ma == "s09.m1":                               # lần đầu: chèn mục mới trước S9.2
        i = next(k for k, l in enumerate(lines) if l.startswith("## S9.2"))
        return dat(lines[:i], moi.split(NL) + [""], lines[i:])
    if ma == "s09.cells":                            # lần đầu: thay cả bảng cũ
        i = next(k for k, l in enumerate(lines) if l.startswith("| Cell | Stage |"))
        j = next(k for k in range(i, len(lines)) if not lines[k].startswith("|"))
        return dat(lines[:i], moi.split(NL), lines[j:])
    co = CO_CU[ma]
    i = next(k for k, l in enumerate(lines) if co in l)
    return dat(lines[:i], moi.split(NL), lines[i + 1:])


def main() -> int:
    text = S09.read_text(encoding="utf-8")
    crlf = chr(13) + NL in text
    text = text.replace(chr(13) + NL, NL)
    for ma, ten, ham in KHOI:
        text = thay(text, ma, ham())
        print(f"   {ma:<12} {ten}")
    S09.write_text(text.replace(NL, chr(13) + NL) if crlf else text, encoding="utf-8", newline="")
    con = text.count("[[M-PENDING")
    print(f"paper/s09-study-records.md: {len(KHOI)} khối đã sinh · còn {con} cờ M-PENDING trong file này")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
