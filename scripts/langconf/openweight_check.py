r"""Hai nhánh open-weight có tái lập được hiệu ứng F4×F5 của nhánh hosted không?

    ..\..\desktop\.venv\Scripts\python.exe scripts\openweight_check.py

## Câu hỏi, và vì sao nó hẹp hơn nhánh hosted

`08-limitations` mục 1 khai hạn chế số một: **một họ model API duy nhất**. Muốn hạ nó thì
phải cho thấy phát hiện trung tâm **không phải quirk của một nhà cung cấp**.

Phát hiện trung tâm của lưới ngôn ngữ (§1 RESULTS.md, `gemini-2.5-flash`, n = 400/ô):

    sâu 2, không nhãn        0,2 %   đúng ngôn ngữ người nói
    sâu 2, nhãn ở lượt user 98,2 %
    sâu 8, không nhãn        0,0 %
    sâu 8, nhãn ở lượt user 87,5 %

Hiệu ứng ấy **khổng lồ**. Nên nó phát hiện được ở cỡ mẫu nhỏ hơn nhiều, và đó là điều
kiện cho phép hai nhánh local chạy ở lưới rút gọn mà vẫn trả lời được câu hỏi.

**Cái script này KHÔNG làm:** nó không so độ lớn giữa ba model. Cỡ mẫu ba bên khác nhau
một bậc, và ba model khác nhau ở nhiều thứ ngoài chỗ đặt. Nó chỉ hỏi **CHIỀU** có giống
không — và chỉ chiều mới là thứ hạn chế số một cần.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf.langid import DualLangID, _same_language     # noqa: E402

RESULTS = ROOT / "results"
DATA = ROOT / "data"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cham(duong: Path, lid: DualLangID) -> dict:
    """(depth, label_position) -> (số đúng, tổng). Đúng = trả lời đúng ngôn ngữ NGƯỜI NÓI."""
    o: dict = {}
    for line in duong.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("model_error") or not r.get("reply_text"):
            continue
        noi = r.get("spoken_lang")
        if not noi:
            continue
        got = lid.detect(r["reply_text"]).fasttext
        khoa = (r.get("depth"), r.get("label_position"))
        dung, tong = o.get(khoa, (0, 0))
        o[khoa] = (dung + (1 if _same_language(got, noi) else 0), tong + 1)
    return o


def main() -> int:
    lid = DualLangID(DATA / "lid" / "lid.176.bin")
    nhanh = [("qwen2.5:7b", RESULTS / "main_qwen2.5-7b.jsonl"),
             ("llama3.1:8b", RESULTS / "main_llama3.1-8b.jsonl")]

    bang: dict[str, dict] = {}
    for ten, duong in nhanh:
        if not duong.exists():
            print(f"  ! chưa có {duong.name}")
            continue
        bang[ten] = cham(duong, lid)
        print(f"{ten}: {sum(t for _, t in bang[ten].values())} lượt dùng được")

    # Đối chứng: nhánh hosted, chép từ RESULTS.md §1 (n = 400/ô, đã công bố trong sổ).
    hosted = {(0, "none"): 1.000, (0, "user"): 0.998,
              (2, "none"): 0.002, (2, "user"): 0.982,
              (8, "none"): 0.000, (8, "user"): 0.875}

    print()
    print(f"  {'ô (sâu, vị trí nhãn)':28s} {'hosted':>8s} | "
          f"{'qwen2.5:7b':>22s} | {'llama3.1:8b':>22s}")
    for khoa in [(0, "none"), (0, "user"), (2, "none"), (2, "user"), (8, "none"), (8, "user")]:
        cot = f"  {str(khoa):28s} {hosted.get(khoa, float('nan')):8.3f} |"
        for ten, _ in nhanh:
            o = bang.get(ten, {}).get(khoa)
            if not o:
                cot += f" {'—':>22s} |"
                continue
            d, t = o
            lo, hi = wilson(d, t)
            cot += f" {d:3d}/{t:<3d} {d/t:5.3f} [{lo:.2f},{hi:.2f}] |"
        print(cot)

    print("\n  Câu hỏi: CHIỀU có giống không — nhãn ở lượt user có cứu được ở sâu 2 và 8?")
    for ten, _ in nhanh:
        b = bang.get(ten)
        if not b:
            continue
        print(f"\n  {ten}:")
        for sau in (2, 8):
            kn, ku = b.get((sau, "none")), b.get((sau, "user"))
            if not kn or not ku:
                print(f"    sâu {sau}: thiếu ô")
                continue
            pn, pu = kn[0] / kn[1], ku[0] / ku[1]
            lo_u, _ = wilson(*ku)
            _, hi_n = wilson(*kn)
            tach = lo_u > hi_n
            print(f"    sâu {sau}: không nhãn {pn:.3f} (n={kn[1]})  ->  nhãn ở user "
                  f"{pu:.3f} (n={ku[1]})   KTC {'TÁCH HẲN' if tach else 'CHỒNG NHAU'}")

    ra = {"hosted_tham_chieu": {str(k): v for k, v in hosted.items()},
          "nhanh": {ten: {str(k): {"dung": v[0], "tong": v[1],
                                   "ti_le": round(v[0] / v[1], 4),
                                   "wilson": [round(x, 4) for x in wilson(*v)]}
                          for k, v in b.items()}
                    for ten, b in bang.items()}}
    out = RESULTS / "openweight_check.json"
    out.write_text(json.dumps(ra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
