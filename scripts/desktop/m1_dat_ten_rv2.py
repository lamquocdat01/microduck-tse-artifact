r"""Đặt tên WAV phiên thu M1 tầng chính: `logs/utts/<stamp>_NNN.wav` → `logs/utts_rv2/rv2_sNN_rK.wav`.

    python scripts\m1_dat_ten_rv2.py --stamp 20260917_101500                  # xem trước, KHÔNG chép
    python scripts\m1_dat_ten_rv2.py --stamp 20260917_101500 --bo 5,18 --chep # bỏ lượt hỏng 5 và 18

App lưu mỗi utterance theo thứ tự nói. Đọc theo khối (câu 1 × 3, câu 2 × 3, …), nên sau khi
bỏ các lượt hỏng (vấp, VAD cắt đôi — ghi trong protocol), file thứ i ứng với câu ⌈i/3⌉, lần
đọc ((i−1) mod 3) + 1. Nhiều `--stamp` (app khởi động lại giữa chừng) nối theo thứ tự đưa vào.

CHÉP, không di chuyển; không bao giờ ghi đè file rv2 đã có. Số file sau khi bỏ ≠ 69 ⇒ dừng.
Bảng xem trước in câu chuẩn cạnh tên gốc để soát lệch khối bằng mắt TRƯỚC khi `--chep`.
Ghi `docs/benchmark/M1_rv2_manifest.json`: nguồn → đích, SHA-256, lượt bị bỏ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UTTS = REPO / "desktop/logs/utts"
DICH = REPO / "desktop/logs/utts_rv2"
CAU = REPO / "docs/benchmark/M1_rv2_sentences.json"
MAN = REPO / "docs/benchmark/M1_rv2_manifest.json"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stamp", action="append", required=True)
    ap.add_argument("--bo", default="", help="số thứ tự (1-based, trên danh sách nối) các lượt hỏng")
    ap.add_argument("--chep", action="store_true")
    args = ap.parse_args()

    bo = json.loads(CAU.read_text(encoding="utf-8"))
    nguon = [f for st in args.stamp for f in sorted(UTTS.glob(f"{st}_*.wav"))]
    hong = {int(x) for x in args.bo.split(",") if x.strip()}
    giu = [f for i, f in enumerate(nguon, 1) if i not in hong]
    can = len(bo["cau"]) * int(bo["lan_doc"])
    print(f"{len(nguon)} file từ {args.stamp}; bỏ {sorted(hong)}; còn {len(giu)} (cần {can})")
    if len(giu) != can:
        print("SỐ FILE KHÔNG KHỚP — không chép. Soát lại --bo theo ghi chép phiên.")
        return 1
    cap = []
    for i, f in enumerate(giu):
        c = bo["cau"][i // int(bo["lan_doc"])]
        ten = f"rv2_s{c['so']:02d}_r{i % int(bo['lan_doc']) + 1}.wav"
        cap.append((f, DICH / ten, c))
        print(f"  {f.name:28s} → {ten:18s} {c['text']}")
    if not args.chep:
        print("\nXem trước. Đúng khối thì chạy lại với --chep.")
        return 0
    trung = [d for _, d, _ in cap if d.exists()]
    if trung:
        print(f"ĐÃ CÓ {len(trung)} file đích (vd {trung[0].name}) — không ghi đè. Dừng.")
        return 1
    DICH.mkdir(parents=True, exist_ok=True)
    muc = []
    for f, d, c in cap:
        shutil.copy2(f, d)
        muc.append({"dich": d.relative_to(REPO).as_posix(), "nguon": f.relative_to(REPO).as_posix(),
                    "sha256": hashlib.sha256(d.read_bytes()).hexdigest(),
                    "reference": c["text"], "reference_lang": c["lang"]})
    MAN.write_text(json.dumps({"stamp": args.stamp, "bo_luot_hong": sorted(hong), "file": muc},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nChép {len(muc)} file → {DICH}; manifest {MAN.relative_to(REPO)}. Runner tự nhận trong ≤ 30 s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
