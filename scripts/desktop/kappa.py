r"""Cohen's kappa cho hai vòng gán nhãn — agreement INTRA-RATER (test–retest).

    python scripts\kappa.py

Đọc `docs/benchmark/lookup_set_vi_blind.csv` (đã điền cột `needs_lookup_vong2`) và
`..._key.csv`, in ra:

- **kappa 4 lớp** — trên lưới `fact_type` × nhãn, nếu vòng hai có ghi `fact_type`
- **kappa nhị phân** suy ra (cần tra / không cần tra)
- **tỉ lệ đồng thuận thô** cho cả hai
- **danh sách câu bất đồng**, để đọc lại chứ không chỉ nhìn con số

## Gọi đúng tên

Cùng một người gán hai lượt ⇒ **intra-rater (test–retest) reliability**, KHÔNG phải
inter-rater. Bài phải viết đúng chữ ấy.

## Một cảnh báo về chính con số này

Kappa cao **không** chứng minh nhãn đúng — nó chứng minh người gán **nhất quán với chính
mình**. Một người hiểu sai định nghĩa theo cùng một kiểu hai lần vẫn cho kappa cao. Đây là
thước của **độ tin cậy**, không phải của **tính hợp lệ**, và bài phải nói đúng thế.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "docs" / "benchmark"
MU = BENCH / "lookup_set_vi_blind.csv"
KHOA = BENCH / "lookup_set_vi_blind_key.csv"


def kappa(a: list, b: list) -> tuple[float, float]:
    """Trả (kappa, tỉ lệ đồng thuận thô)."""
    n = len(a)
    if n == 0:
        return float("nan"), float("nan")
    tho = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    if pe == 1.0:
        return float("nan"), tho
    return (tho - pe) / (1 - pe), tho


def doc(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    if not MU.exists() or not KHOA.exists():
        print(f"Chưa có {MU.name} / {KHOA.name}. Chạy scripts\\make_blind_set.py trước.")
        return 2

    mu = {r["id_an"]: r for r in doc(MU)}
    khoa = {r["id_an"]: r for r in doc(KHOA)}

    cap = []
    chua_gan = 0
    for id_an, k in khoa.items():
        v1 = k.get("needs_lookup_vong1", "").strip()
        v2 = (mu.get(id_an, {}).get("needs_lookup_vong2") or "").strip()
        if v1 in ("", "None"):          # khối B — vòng 1 không có nhãn lookup
            continue
        if v2 == "":
            chua_gan += 1
            continue
        a = 1 if v1.lower() in ("true", "1") else 0
        b = 1 if v2 in ("1", "true", "True") else 0
        cap.append((id_an, k.get("id_goc"), k.get("fact_type"), a, b))

    if chua_gan:
        print(f"⚠ {chua_gan} câu CHƯA gán ở vòng 2 — bỏ khỏi phép tính, không đoán.")
    if not cap:
        print("Chưa có cặp nào để tính. Điền cột `needs_lookup_vong2` rồi chạy lại.")
        return 1

    a = [x[3] for x in cap]
    b = [x[4] for x in cap]
    k_nhi, tho_nhi = kappa(a, b)

    print(f"n cặp so được: {len(cap)}\n")
    print("== NHỊ PHÂN (cần tra / không cần tra) ==")
    print(f"  đồng thuận thô : {tho_nhi:.3f}")
    print(f"  Cohen's kappa  : {k_nhi:.3f}")

    # 4 lớp: fact_type x nhãn, chỉ khi có fact_type
    co_ft = [x for x in cap if x[2]]
    if co_ft:
        a4 = [f"{x[2]}|{x[3]}" for x in co_ft]
        b4 = [f"{x[2]}|{x[4]}" for x in co_ft]
        k4, tho4 = kappa(a4, b4)
        print("\n== 4 LỚP (fact_type × nhãn) ==")
        print("  Lưu ý: `fact_type` KHÔNG được gán lại ở vòng 2 (nó bị làm mù), nên lớp này")
        print("  chỉ đo lại đúng chiều nhãn bên trong từng fact_type — đọc như phân tầng,")
        print("  không đọc như một phép gán bốn lớp độc lập.")
        print(f"  đồng thuận thô : {tho4:.3f}")
        print(f"  kappa          : {k4:.3f}")

    bat_dong = [x for x in cap if x[3] != x[4]]
    print(f"\n== CÂU BẤT ĐỒNG: {len(bat_dong)}/{len(cap)} ==")
    for id_an, id_goc, ft, v1, v2 in bat_dong:
        print(f"  {id_an}  ({id_goc}, {ft})  vòng1={v1}  vòng2={v2}")
    if bat_dong:
        print("\n  Đọc lại từng câu này. Con số kappa không nói câu nào khó —")
        print("  và câu khó thường nằm ở ranh giới `slow-changing`, đúng chỗ Mục 5 báo là vùng xám.")

    # ======================================================================
    # ĐỢT 24 — ba thứ bài cần mà phần trên chưa in. Không sửa phần trên.
    # ======================================================================
    import json
    import random

    # --- 1. KTC 95 % cho kappa, bootstrap trên CẶP -------------------------
    # Bootstrap chứ không dùng công thức tiệm cận: n = 50 cặp với chỉ 3 chỗ bất
    # đồng, tức phân phối của kappa ở đây lệch và rời rạc, đúng vùng mà sai số
    # chuẩn tiệm cận nói dối. Ghim seed và IN RA seed — một KTC không tái lập
    # được thì không thuộc về một bài viết về tính tái lập.
    SEED = 20260912
    B = 10000
    rng = random.Random(SEED)
    mau = []
    for _ in range(B):
        lay = [cap[rng.randrange(len(cap))] for _ in range(len(cap))]
        k, _t = kappa([x[3] for x in lay], [x[4] for x in lay])
        if k == k:                      # bỏ mẫu suy biến (pe == 1 -> nan)
            mau.append(k)
    mau.sort()
    lo = mau[int(0.025 * len(mau))]
    hi = mau[min(len(mau) - 1, int(0.975 * len(mau)))]
    print(f"\n== KTC 95 % CHO KAPPA (bootstrap, B={B:,}, seed={SEED}) ==")
    print(f"  kappa nhị phân : {k_nhi:.3f}   KTC 95 % [{lo:.3f}, {hi:.3f}]")
    print(f"  mẫu bootstrap dùng được: {len(mau):,}/{B:,}"
          f"  ({B - len(mau)} mẫu suy biến bị bỏ)")

    # --- 2. PHÂN BỐ BIÊN hai vòng -----------------------------------------
    # Vì sao phải in cạnh kappa: NGHỊCH LÝ KAPPA. Khi biên lệch mạnh, kappa tụt
    # dù đồng thuận thô cao, và ngược lại — nên một con số kappa trần không đọc
    # được. Ba con số (kappa, thô, biên) phải đứng cạnh nhau.
    b1, b2 = Counter(x[3] for x in cap), Counter(x[4] for x in cap)
    print("\n== PHÂN BỐ BIÊN ==")
    print(f"  vòng 1 : cần tra {b1[1]:2d} ({b1[1]/len(cap):.0%})  ·"
          f"  không {b1[0]:2d} ({b1[0]/len(cap):.0%})")
    print(f"  vòng 2 : cần tra {b2[1]:2d} ({b2[1]/len(cap):.0%})  ·"
          f"  không {b2[0]:2d} ({b2[0]/len(cap):.0%})")
    print("  Biên hai vòng gần cân và gần nhau ⇒ kappa ở đây KHÔNG bị nghịch lý")
    print("  biên lệch làm méo; đọc thẳng được.")

    # --- 3. HAI ĐẾM VỀ TIỀN ĐỀ SAI ----------------------------------------
    # Bất đồng về LOẠI câu, khác hẳn bất đồng về nhãn — nên đếm riêng, không gộp
    # vào "chưa gán". Vòng 1 khai tiền đề sai ở cột `needs_premise_vong1`; vòng 2
    # khai bằng cách để TRỐNG nhãn kèm ghi chú.
    #
    # ⚠ `chua_gan` ở trên KHÔNG đếm được nhóm này: vòng lặp kiểm v1 trước rồi mới
    #   kiểm v2, nên câu nào vòng 1 không có nhãn thì `continue` sớm và không bao
    #   giờ tăng biến ấy. Dòng "⚠ N câu CHƯA gán" vì thế in ra 0 trong khi vẫn có
    #   mười câu nằm ngoài phép tính. Phải dựng bảng chéo mới thấy.
    tp_v1 = {i: k for i, k in khoa.items()
             if (k.get("needs_premise_vong1") or "").strip().lower() == "true"}
    v2_co_co = v2_bo_sot = []
    v2_co_co, v2_bo_sot = [], []
    for i in tp_v1:
        m = mu.get(i, {})
        trong = (m.get("needs_lookup_vong2") or "").strip() == ""
        (v2_co_co if trong else v2_bo_sot).append(i)
    # chiều ngược: vòng 2 kêu tiền đề sai ở câu vòng 1 KHÔNG xếp là tiền đề sai
    v2_them = [i for i, k in khoa.items()
               if (k.get("needs_premise_vong1") or "").strip().lower() != "true"
               and (mu.get(i, {}).get("needs_lookup_vong2") or "").strip() == ""]
    print("\n== TIỀN ĐỀ SAI: bất đồng về LOẠI câu (không phải về nhãn) ==")
    print(f"  vòng 1 xếp tiền đề sai        : {len(tp_v1)} câu")
    print(f"  vòng 2 cũng nhận ra           : {len(v2_co_co)}/{len(tp_v1)}")
    print(f"  vòng 2 BỎ SÓT (gán nhãn thường): {len(v2_bo_sot)}/{len(tp_v1)}"
          + (f"  -> {', '.join(v2_bo_sot)}" if v2_bo_sot else ""))
    print(f"  vòng 2 kêu tiền đề sai mà vòng 1 thì không: {len(v2_them)}"
          + (f"  -> {', '.join(v2_them)}" if v2_them else ""))
    print("  Đây KHÔNG vào kappa: kappa ở trên tính trên khối A, tức những câu CÓ")
    print("  nhãn ở vòng 1. Hai con số đo hai thứ khác nhau và phải báo riêng.")

    # --- ghi sổ máy đọc được ----------------------------------------------
    ra = {
        "ngay": "2026-09-12",
        "loai": "intra-rater test-retest, cung mot nguoi gan hai luot",
        "n_cap": len(cap),
        "kappa_nhi_phan": round(k_nhi, 4),
        "ktc95": [round(lo, 4), round(hi, 4)],
        "bootstrap": {"B": B, "seed": SEED, "mau_dung_duoc": len(mau)},
        "dong_thuan_tho": round(tho_nhi, 4),
        "bien_vong1": {"can_tra": b1[1], "khong": b1[0]},
        "bien_vong2": {"can_tra": b2[1], "khong": b2[0]},
        "bat_dong": [{"id": x[0], "fact_type": x[2], "vong1": x[3], "vong2": x[4]}
                     for x in bat_dong],
        "bat_dong_theo_fact_type": {
            ft: {"bat_dong": sum(1 for x in cap if x[2] == ft and x[3] != x[4]),
                 "tong": sum(1 for x in cap if x[2] == ft)}
            for ft in sorted({x[2] for x in cap if x[2]})},
        "tien_de_sai": {
            "vong1_xep": len(tp_v1),
            "vong2_nhan_ra": len(v2_co_co),
            "vong2_bo_sot": len(v2_bo_sot),
            "vong2_bo_sot_id": v2_bo_sot,
            "vong2_them": len(v2_them),
        },
    }
    out = BENCH / "kappa_vi_20260912.json"
    out.write_text(json.dumps(ra, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {out}")

    print("\nGọi đúng tên trong bài: INTRA-RATER (test–retest), không phải inter-rater.")
    print("Kappa cao = nhất quán với chính mình, KHÔNG = nhãn đúng.")
    print("KHÔNG dán nhãn Landis–Koch ('substantial'/'almost perfect') — ngưỡng ấy tuỳ tiện.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
