r"""Chấm M6 (RQ5) và M7 (RQ6) — ĐÚNG luật AMENDMENT 04 §A04.3–A04.5, commit TRƯỚC khi chạy trên dữ liệu thật.

    python scripts\cham_m6_m7.py --moc-commit 015c0e7 --out docs\benchmark\M6_M7_cham_<ngày>.json
    python scripts\cham_m6_m7.py --root <thư mục giả> --moc-ts 2026-09-17T07:48:33+07:00   # cổng kiểm

A06 (17/09): M6 báo BIÊN art−dec, không chấm đúng/sai; M7 loại ô suy máy móc (9, 11, 13) và nguồn có pilot
(M2 hosted, M3), thêm S2, chấm thêm (c) depth. Không có tham số nào để "chỉnh" kết quả: luật chấm, danh sách ô, khoảng cách chấm và phép so đều là
hằng số dưới đây, chép từ A04.

## So "đổi" (M7) — theo thân v1
- text/transcript: byte-identical sau `strip()`, KHÔNG chuẩn hoá (thân v1 §0). Chuẩn hoá chỉ dùng
  cho bộ oracle artefact của M6 (A04.3), không dùng cho M7.
- quyết định: bằng nhau đúng giá trị. domain-set (M3): tập tên miền.
- M3 text (art B) = trường `answer` (text model trả), không phải `reply` (đã qua xử lý hậu kỳ).

## Mù (A04.5)
Một cặp được TÍNH ĐIỂM khi bản ghi của mốc chấm (lượt sau) có `ts` SAU timestamp commit A04.
Cặp còn lại in ở `khong_mu`, không vào tổng.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
Z = 1.959963984540054

# ---------------------------------------------------------------------------
# thống kê


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Hiệu p1 − p2, khoảng hybrid score (Newcombe 1998, phương pháp 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return (d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


# ---------------------------------------------------------------------------
# luật chấm M7 (A04.4, A04.5)
ON, KHONG = "ổn định", "không"
NGUONG_ON, NGUONG_KHONG, RANH_GIOI, TREN_ON, N_LUC = 0.05, 0.20, 0.125, 0.10, 35


def phan_quyet(du_doan: str, k: int, n: int) -> dict:
    p = k / n
    lo, hi = wilson(k, n)
    if du_doan == ON:
        if p <= NGUONG_ON and hi <= TREN_ON:
            v = "đúng"
        elif p >= NGUONG_KHONG or p > RANH_GIOI:
            v = "sai"
        else:
            v = "không phân định"
        thieu_luc = n < N_LUC
    else:
        if p >= NGUONG_KHONG:
            v = "đúng"
        elif p <= NGUONG_ON or p < RANH_GIOI:
            v = "sai"
        else:
            v = "không phân định"
        thieu_luc = False
    return {"k": k, "n": n, "ty_le": round(p, 4), "wilson": [round(lo, 4), round(hi, 4)], "phan_quyet": v,
            "thieu_luc": thieu_luc,
            "vao_mau_so": (not thieu_luc) or v == "sai"}


# ô: (#, stage, observable, pinnability, dự đoán, [nguồn])
O = [
    (1, "STT", "nhãn ngôn ngữ", "delegated", ON, ["S1", "S2", "S3"]),
    (2, "STT", "transcript", "delegated", KHONG, ["S1", "S2", "S3"]),
    (3, "STT", "nhãn ngôn ngữ", "pinnable", ON, ["S1", "S2", "S3"]),
    (4, "STT", "transcript", "pinnable", ON, ["S1", "S2", "S3"]),
    (5, "routing", "lookup", "delegated t=0.8", ON, ["M2", "M6"]),
    (6, "routing", "text thô", "delegated t=0.8", KHONG, ["M2", "M6"]),
    (7, "routing", "lookup", "delegated t=0.0", ON, ["M2"]),
    (8, "routing", "text thô", "delegated t=0.0", KHONG, ["M2"]),
    (9, "routing", "lookup", "pinnable qwen 7b", ON, ["M2", "M6"]),
    (10, "routing", "text thô", "pinnable qwen 7b", ON, ["M2", "M6"]),
    (11, "ngôn ngữ trả lời", "nhãn", "pinnable 7b", ON, ["M4"]),
    (12, "ngôn ngữ trả lời", "reply_text", "pinnable 7b", ON, ["M4"]),
    (13, "ngôn ngữ trả lời", "nhãn", "pinnable 3b", ON, ["M4"]),
    (14, "ngôn ngữ trả lời", "reply_text", "pinnable 3b", ON, ["M4"]),
    (15, "grounding", "lookup", "delegated", ON, ["M3"]),
    (16, "grounding", "domain-set", "delegated", KHONG, ["M3"]),
    (17, "grounding", "text", "delegated", KHONG, ["M3"]),
]


# ---------------------------------------------------------------------------
# đọc


def doc_ok(path: Path) -> dict[str, dict]:
    ra: dict[str, dict] = {}
    if not path.exists():
        return ra
    for line in path.read_bytes().splitlines():
        try:
            r = json.loads(line.decode("utf-8"))
        except Exception:
            continue                                   # dòng hỏng: bỏ qua như core.Store
        if isinstance(r, dict) and r.get("status") == "ok" and r["task_id"] not in ra:
            ra[r["task_id"]] = r
    return ra


def ts(r: dict) -> float:
    return datetime.fromisoformat(r["ts"]).timestamp()


def txt(x) -> str:
    return (x or "").strip()


# (#ô, nguồn) -> list[(bản ghi trước, bản ghi sau, hàm lấy giá trị)]
def cap_m7(root: Path, plan: dict) -> dict[tuple[int, str], list[tuple[dict, dict, callable]]]:
    res = {m: doc_ok(root / p) for m, p in plan["results"].items()}
    cap: dict[tuple[int, str], list] = {}

    def them(o: int, nguon: str, a: dict | None, b: dict | None, f) -> None:
        if a is not None and b is not None:
            cap.setdefault((o, nguon), []).append((a, b, f))

    # M1: M1|<utt>|<gemini|whisper>|t0|1 → t24h|1 ; S1 = rv1_*, S3 = s3_*
    m1 = res.get("M1", {})
    for tid, a in m1.items():
        p = tid.split("|")
        if len(p) != 5 or p[3] != "t0" or p[2] not in ("gemini", "whisper"):
            continue
        tang = ("S1" if p[1].startswith("rv1_") else "S3" if p[1].startswith("s3_")
                else "S2" if p[1].startswith("wild_") else None)          # S2: A06.3
        if tang is None:
            continue
        b = m1.get(f"M1|{p[1]}|{p[2]}|t24h|1")
        dec, art = (1, 2) if p[2] == "gemini" else (3, 4)
        them(dec, tang, a, b, lambda r: r["payload"].get("language"))
        them(art, tang, a, b, lambda r: txt(r["payload"].get("hypothesis")))
    # M2: M2|<qid>|<arm>|t0 → t24h
    m2 = res.get("M2", {})
    arm_o = {"gemini-t08": (5, 6), "gemini-t0": (7, 8), "qwen2.5:7b": (9, 10)}
    for tid, a in m2.items():
        p = tid.split("|")
        if len(p) != 4 or p[3] != "t0" or p[2] not in arm_o:
            continue
        b = m2.get(f"M2|{p[1]}|{p[2]}|t24h")
        dec, art = arm_o[p[2]]
        them(dec, "M2", a, b, lambda r: r["payload"].get("lookup"))
        them(art, "M2", a, b, lambda r: txt(r["payload"].get("raw_text")))
    # M4: M4|<pid>|<model>|t0|1 → t24h|1
    m4 = res.get("M4", {})
    mod_o = {"qwen2.5:7b": (11, 12), "qwen2.5:3b": (13, 14)}
    for tid, a in m4.items():
        p = tid.split("|")
        if len(p) != 5 or p[3] != "t0" or p[2] not in mod_o:
            continue
        b = m4.get(f"M4|{p[1]}|{p[2]}|t24h|1")
        dec, art = mod_o[p[2]]
        them(dec, "M4", a, b, lambda r: r["payload"].get("lang_label"))
        them(art, "M4", a, b, lambda r: txt(r["payload"].get("reply_text")))
    # M3: mốc 14 so mốc 1
    lich = plan.get("m3_lich") or []
    if len(lich) >= 14:
        m3 = res.get("M3", {})
        d1 = datetime.fromisoformat(lich[0]).isoformat(timespec="minutes")
        d14 = datetime.fromisoformat(lich[13]).isoformat(timespec="minutes")
        for tid, a in m3.items():
            p = tid.split("|")
            if len(p) != 3 or p[1] != d1:
                continue
            b = m3.get(f"M3|{d14}|{p[2]}")
            them(15, "M3", a, b, lambda r: r["payload"].get("lookup"))
            them(16, "M3", a, b, lambda r: sorted(set(r["payload"].get("domains") or [])))
            them(17, "M3", a, b, lambda r: txt(r["payload"].get("answer")))
    # M6: lần 20 so lần 1, từ obs
    m6 = res.get("M6", {})
    a6, b6 = m6.get("M6|lan01"), m6.get("M6|lan20")
    if a6 and b6:
        for be, (dec, art) in (("hosted", (5, 6)), ("local", (9, 10))):
            for iid in sorted(a6["payload"]["obs"]["routing"][be]):
                them(dec, "M6", a6, b6, lambda r, i=iid, e=be: (r["payload"]["obs"]["routing"][e].get(i) or {}).get("lookup"))
                them(art, "M6", a6, b6, lambda r, i=iid, e=be: txt((r["payload"]["obs"]["routing"][e].get(i) or {}).get("raw_text")))
    return cap


def cham_m7(root: Path, plan: dict, moc: float) -> dict:
    cap = cap_m7(root, plan)
    don_vi, khong_mu = [], []
    for so, stage, obs, pin, du, nguon in O:
        for ng in nguon:
            ds = cap.get((so, ng), [])
            mu = [(a, b, f) for a, b, f in ds if ts(b) > moc]
            cu = [(a, b, f) for a, b, f in ds if ts(b) <= moc]
            base = {"o": so, "stage": stage, "observable": obs, "pinnability": pin, "du_doan": du, "nguon": ng}
            if cu:
                k = sum(f(a) != f(b) for a, b, f in cu)
                khong_mu.append({**base, "k": k, "n": len(cu), "ty_le": round(k / len(cu), 4),
                                 "wilson": [round(x, 4) for x in wilson(k, len(cu))],
                                 "nhan": "không mù — không tính điểm"})
            if not mu:
                don_vi.append({**base, "phan_quyet": "chưa có cặp mù", "n": 0, "vao_mau_so": False,
                               "thieu_luc": False})
                continue
            k = sum(f(a) != f(b) for a, b, f in mu)
            # A05.5: chỉ IN số cặp có lượt trước chưa offline (thiếu trường ⇒ false) mà lượt sau offline
            vat = sum(1 for a, b, _ in mu if a.get("hf_offline") is not True and b.get("hf_offline") is True)
            pq = phan_quyet(du, k, len(mu))
            ly_do_loai = LOAI_A06.get((so, ng))
            if ly_do_loai:                                     # A06.3: in, không vào mẫu số
                pq = {**pq, "vao_mau_so": False, "loai_a06": ly_do_loai}
            don_vi.append({**base, **pq, "cap_vat_qua_offline": vat})
    vao = [d for d in don_vi if d["vao_mau_so"]]
    return {"don_vi": don_vi, "khong_mu": khong_mu, "depth": cham_depth(don_vi),
            "tong_ket": {"dung": sum(d["phan_quyet"] == "đúng" for d in vao),
                         "sai": sum(d["phan_quyet"] == "sai" for d in vao),
                         "khong_phan_dinh": sum(d["phan_quyet"] == "không phân định" for d in vao),
                         "mau_so": len(vao),
                         "loai_a06": sum(1 for d in don_vi if d.get("loai_a06")),
                         "thieu_luc_khong_tinh": sum(d["thieu_luc"] and not d["vao_mau_so"]
                                                     and not d.get("loai_a06") for d in don_vi),
                         "chua_co_cap_mu": sum(d["phan_quyet"] == "chưa có cặp mù" for d in don_vi)}}


# A06.3 — đơn vị in ra nhưng KHÔNG vào mẫu số, và lý do.
_SUY = "suy máy móc từ ô artefact cùng nguồn (A06.1): decision tính từ artefact"
_PILOT_M2 = "cấu hình M2 hosted đã có số pilot dựng mô hình (A06.3)"
_PILOT_M3 = "cấu hình M3 đã có số pilot dựng mô hình (A06.3)"
LOAI_A06: dict[tuple[int, str], str] = {
    **{(9, ng): _SUY for ng in ("M2", "M6")}, (11, "M4"): _SUY, (13, "M4"): _SUY,
    (5, "M2"): _PILOT_M2, (6, "M2"): _PILOT_M2, (7, "M2"): _PILOT_M2, (8, "M2"): _PILOT_M2,
    (15, "M3"): _PILOT_M3, (16, "M3"): _PILOT_M3, (17, "M3"): _PILOT_M3,
}

# A06.4 — nhóm depth: (tên, [(ô, độ sâu)])
NHOM_DEPTH = [("delegated × decision", [(1, 1), (5, 2)]),
              ("delegated × artefact", [(2, 1), (6, 2)]),
              ("caller-pinnable × artefact", [(4, 1), (10, 2), (12, 4), (14, 4)])]


def cham_depth(don_vi: list[dict]) -> dict:
    """A06.4: đơn vị TÍNH ĐIỂM (vao_mau_so hoặc thiếu lực nhưng có số) xếp ổn định ≤ 5 %, không ≥ 20 %."""
    ra = []
    for ten, o_sau in NHOM_DEPTH:
        sau = dict(o_sau)
        xep = []
        for d in don_vi:
            if d["o"] not in sau or d.get("loai_a06") or not d.get("n"):
                continue
            p = d["k"] / d["n"]
            loai = "ổn định" if p <= NGUONG_ON else "không ổn định" if p >= NGUONG_KHONG else None
            if loai:
                xep.append({"o": d["o"], "nguon": d["nguon"], "do_sau": sau[d["o"]], "loai": loai,
                            "k": d["k"], "n": d["n"]})
        cac_loai = {x["loai"] for x in xep}
        if len(xep) < 2:
            kq = "không phân định"
        elif len(cac_loai) == 1:
            kq = "hỗ trợ (c)"
        elif any(a["loai"] != b["loai"] and a["do_sau"] != b["do_sau"] for a in xep for b in xep):
            kq = "bác (c)"
        else:
            kq = "không phân định"
        ra.append({"nhom": ten, "don_vi": xep, "ket_qua": kq})
    return {"nhom": ra, "ho_tro": sum(x["ket_qua"] == "hỗ trợ (c)" for x in ra),
            "bac": sum(x["ket_qua"] == "bác (c)" for x in ra),
            "khong_phan_dinh": sum(x["ket_qua"] == "không phân định" for x in ra)}


# ---------------------------------------------------------------------------
# M6 (A04.3)


def cham_m6(root: Path, plan: dict) -> dict:
    if "M6" not in plan["results"]:
        return {"loi": "plan không có M6"}
    ok = sorted(doc_ok(root / plan["results"]["M6"]).values(), key=lambda r: r["payload"]["lan"])
    if len(ok) < 2:
        return {"so_lan_hop_le": len(ok), "loi": "cần ≥ 2 lần chạy ok"}
    sau = ok[1:]
    # test -> (bộ, ô) ; tên: "<bộ>::test_<bộ>[<stage>-<backend>-<iid>]"
    fail: dict[tuple[str, str, str], list[bool]] = {}
    for r in sau:
        for ten, kq in r["payload"]["tests"].items():
            bo, rest = ten.split("::", 1)
            stage, be, iid = rest[rest.index("[") + 1:-1].split("-", 2)
            fail.setdefault((bo, f"{stage}-{be}", iid), []).append(kq != "passed")
    o_ra = {}
    for o in sorted({c for _, c, _ in fail}):
        be = o.split("-")[1]
        loai = "delegated" if be == "hosted" else "pinnable"
        bo_kq = {}
        for bo in ("decision", "artefact"):
            tests = {iid: v for (b, c, iid), v in fail.items() if b == bo and c == o}
            k = sum(any(v) for v in tests.values())
            n = len(tests)
            ke, ne = sum(sum(v) for v in tests.values()), sum(len(v) for v in tests.values())
            bo_kq[bo] = {"flaky_tests": k, "n_tests": n, "flake": round(k / n, 4) if n else None,
                         "wilson": [round(x, 4) for x in wilson(k, n)],
                         "fail_lan_chay": ke, "n_lan_chay": ne,
                         "ty_le_lan_chay_khong_doc_lap": round(ke / ne, 4) if ne else None}
        dk, dn = bo_kq["decision"]["flaky_tests"], bo_kq["decision"]["n_tests"]
        ak, an = bo_kq["artefact"]["flaky_tests"], bo_kq["artefact"]["n_tests"]
        d, lo, hi = newcombe(dk, dn, ak, an)
        vi_pham = sum(1 for (b, c, iid), v in fail.items() if b == "decision" and c == o and any(v)
                      and not any(fail.get(("artefact", o, iid), [])))
        # A06.1: KHÔNG chấm đúng/sai. Nội dung thực nghiệm = BIÊN flake(artefact) − flake(decision) + khoảng.
        # Newcombe(art, dec) = −Newcombe(dec, art): đổi dấu và đổi đầu mút.
        o_ra[o] = {"loai": loai, **bo_kq,
                   "bien_art_tru_dec": round(-d, 4), "newcombe_bien": [round(-hi, 4), round(-lo, 4)],
                   "kiem_nhat_quan_decision_flaky_ma_artefact_khong": vi_pham,
                   "kiem_nhat_quan_nghia": ("routing: > 0 = lỗi trích xuất (A06.1)" if o.startswith("routing")
                                            else "recognition: quan sát exploratory (A06.1)")}
    return {"so_lan_hop_le": len(ok), "lan": [r["payload"]["lan"] for r in ok],
            "golden": ok[0]["task_id"], "o": o_ra}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--plan", default=None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--moc-commit", help="commit chứa AMENDMENT 04 (015c0e7)")
    g.add_argument("--moc-ts", help="chỉ cho cổng kiểm với dữ liệu giả")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.root)
    plan = json.loads(Path(a.plan or root / "docs/benchmark/runner/plan.json").read_text(encoding="utf-8"))
    if a.moc_commit:
        moc_iso = subprocess.run(["git", "show", "-s", "--format=%cI", a.moc_commit], cwd=REPO, capture_output=True,
                                 text=True, check=True).stdout.strip()
    else:
        moc_iso = a.moc_ts
    moc = datetime.fromisoformat(moc_iso).timestamp()
    ra = {"luat": "docs/benchmark/PREREG_M1-M4_20260916.md §A04.3–A04.5 + A06", "moc_mu": moc_iso,
          "moc_commit": a.moc_commit, "cham_luc": datetime.now().astimezone().isoformat(timespec="seconds"),
          "M6": cham_m6(root, plan), "M7": cham_m7(root, plan, moc)}
    if a.out:
        Path(a.out).write_text(json.dumps(ra, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    t = ra["M7"]["tong_ket"]
    print(f"M7: đúng {t['dung']}/{t['mau_so']} · sai {t['sai']} · không phân định {t['khong_phan_dinh']} · "
          f"thiếu lực (không tính) {t['thieu_luc_khong_tinh']} · chưa có cặp mù {t['chua_co_cap_mu']}")
    for d in ra["M7"]["don_vi"]:
        print(f"  ô {d['o']:2d} {d['nguon']:3s} {d['du_doan']:9s} {d.get('k', '-')}/{d['n']} → {d['phan_quyet']}"
              f"{' (thiếu lực)' if d['thieu_luc'] else ''}")
    m6 = ra["M6"]
    print(f"M6: {m6.get('so_lan_hop_le')} lần hợp lệ {m6.get('loi', '')}")
    for o, v in (m6.get("o") or {}).items():
        print(f"  {o:16s} dec {v['decision']['flaky_tests']}/{v['decision']['n_tests']} · "
              f"art {v['artefact']['flaky_tests']}/{v['artefact']['n_tests']} · biên art−dec "
              f"{v['bien_art_tru_dec']} {v['newcombe_bien']}")
    dp = ra["M7"]["depth"]
    print(f"M7 (c) depth: hỗ trợ {dp['ho_tro']} · bác {dp['bac']} · không phân định {dp['khong_phan_dinh']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
