r"""Backend hosted có tất định TRONG MỘT BUỔI không? (đợt 12, việc 38b)

    python scripts\bench_hosted_repeat.py --passes 2 --gap-s 120

## Câu hỏi

Hai mẻ chấm điểm 06/09 và 07/09 cho **5/31 transcript khác nhau** trên **cùng 31 file
audio** và **cùng reference** (0/31 khác). Nhưng hai mẻ ấy cách nhau **một ngày**, nên
hai lời giải thích chưa tách được:

- **lấy mẫu** — model sinh khác nhau giữa hai lời gọi bất kể thời điểm;
- **nhà cung cấp đổi model** — `gemini-2.5-flash` là một **alias**, không phải version
  ghim được, nên bản sau alias có thể đã khác bản trước.

Không mẻ nào ghi lại `model_version` (việc 38a: đã kiểm, cả hai file chỉ có chuỗi alias
`gemini-audio/gemini-2.5-flash`). Từ đợt 12 `stt_gemini.py` ghi lại
`response.model_version` và `response.response_id`; script này là chỗ đầu tiên dùng nó.

## Phép thử

Chạy **cùng 31 WAV** qua backend hosted **nhiều lượt trong CÙNG MỘT BUỔI**, cách nhau
vài phút. Khoảng cách vài phút thì "nhà cung cấp đổi model" gần như loại được, còn
"lấy mẫu" thì không.

| kết quả | đọc là |
|---|---|
| vẫn ~5/31 đổi | bất định **trong một buổi** ⇒ nghiêng về lấy mẫu |
| 0/31 đổi | khoảng cách một ngày đang làm việc ⇒ nghiêng về version drift |
| 1–2/31 đổi | **nằm giữa — DỪNG, BÁO.** Không tự chọn cách đọc |

⚠ Đây là phép đo **MỚI**, không phải tái lập của mẻ 5/31. Nó vào sổ như một dòng riêng
với ngày riêng, **không ghi đè** 5/31. Giữ cả hai.

## Quy ước so sánh — ghi ở đây để bài trích được

- So trường **`hypothesis`** (transcript nguyên văn model trả về), **không** chuẩn hoá
  gì trước khi so. Hai chuỗi khác nhau dù chỉ một dấu câu là "đổi".
  Lý do không chuẩn hoá: câu hỏi là *cùng đầu vào có cho cùng đầu ra không*, không phải
  *hai đầu ra có cùng nghĩa không*. Chuẩn hoá trước khi so là trả lời câu khác.
- Lát cắt: trọn bộ 31 lượt, không loại lượt nào.
- Lượt lỗi mạng (transcript rỗng) **được đếm** và báo riêng — bỏ nó đi là chọn mẫu theo
  kết quả.

Không gọi board, không phát tiếng. Không ghi vào `logs/latency.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audio_wav import read_wav  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
UTT_DIR = Path(__file__).resolve().parents[1] / "logs" / "utts"
REFS = BENCH_DIR / "stt_rescore_20260906_v3_fixed.json"


def doc_bo() -> list[dict[str, Any]]:
    """Đúng 31 lượt của mẻ v3_fixed, giữ nguyên thứ tự."""
    data = json.loads(REFS.read_text(encoding="utf-8"))
    ra = []
    for u in data["gemini-audio"]["utterances"]:
        wav = UTT_DIR / u["wav"]
        if not wav.exists():
            raise SystemExit(f"Thiếu {wav} — bộ 31 WAV không đủ, dừng chứ không đo thiếu.")
        ra.append({"wav": wav, "name": u["wav"], "reference": u["reference"],
                   "reference_lang": u["reference_lang"]})
    return ra


def main() -> int:
    enable_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--passes", type=int, default=2, help="số lượt chạy trong cùng buổi")
    ap.add_argument("--gap-s", type=float, default=120.0, help="nghỉ giữa hai lượt, giây")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY.")
        return 1

    from handlers.stt_gemini import GeminiAudioSTT

    bo = doc_bo()
    stt = GeminiAudioSTT(api_key=cfg.gemini_api_key, model=cfg.gemini_model)
    print(f"Backend hosted, {len(bo)} WAV × {args.passes} lượt, nghỉ {args.gap_s:.0f} s giữa các lượt.")
    print(f"Model gọi theo alias: {cfg.gemini_model}\n")

    rows: list[dict[str, Any]] = []
    for luot in range(1, args.passes + 1):
        if luot > 1:
            print(f"  nghỉ {args.gap_s:.0f} s...")
            time.sleep(args.gap_s)
        bat_dau = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
        print(f"=== lượt {luot}/{args.passes}  ({bat_dau}) ===")
        for i, r in enumerate(bo, 1):
            audio = read_wav(r["wav"])
            t0 = time.perf_counter()
            text, lang = stt.transcribe(audio)
            ms = (time.perf_counter() - t0) * 1000
            rows.append({
                "luot": luot, "ran_at": bat_dau, "index": i, "wav": r["name"],
                "reference": r["reference"], "reference_lang": r["reference_lang"],
                "hypothesis": text, "language": lang,
                "model_alias": cfg.gemini_model,
                "model_version": getattr(stt, "last_model_version", None),
                "response_id": getattr(stt, "last_response_id", None),
                "error": getattr(stt, "last_error", None),
                "stt_ms": round(ms, 1),
            })
            if i % 10 == 0 or i == len(bo):
                print(f"    {i}/{len(bo)}")

    out = Path(args.out) if args.out else BENCH_DIR / f"stt_hosted_repeat_{date.today():%Y%m%d}_v1.jsonl"
    with out.open("w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nGhi {len(rows)} bản ghi vào {out}")

    # ---- kết quả ----------------------------------------------------------
    print("\n" + "=" * 78)
    print("KẾT QUẢ — so trường `hypothesis` NGUYÊN VĂN, không chuẩn hoá; lát cắt trọn 31 lượt")
    print("=" * 78)

    # `None` KHÔNG phải một version — nó là lượt gọi hỏng (timeout/lỗi mạng), và đếm nó
    # như một version thứ hai thì báo động giả. Bản đầu của script này làm đúng thế:
    # mẻ 10/09 có 2 lượt timeout, script kêu "NHIỀU HƠN MỘT VERSION" trong khi cả 60
    # lượt thành công đều trả về cùng một chuỗi.
    ver = Counter(r["model_version"] for r in rows if r["model_version"] is not None)
    thieu = sum(1 for r in rows if r["model_version"] is None)
    print("")
    thong_bao = "model_version ghi duoc: " + str(dict(ver))
    if thieu:
        thong_bao += "   (+" + str(thieu) + " luot khong co — luot goi HONG,"
        thong_bao += " khong phai version khac)"
    print(thong_bao)
    if len(ver) > 1:
        print("  ⚠ NHIỀU HƠN MỘT VERSION trong cùng một buổi — báo chủ nhân.")
    elif len(ver) == 1 and next(iter(ver)) == cfg.gemini_model:
        print("  ⚠ API trả về ĐÚNG CHUỖI ALIAS làm `model_version`, không phải một build id.")
        print("     Ghi lại trường này KHÔNG làm version ghim được — alias vẫn là alias.")

    loi = [r for r in rows if r["error"] or not r["hypothesis"]]
    if loi:
        print(f"\n⚠ {len(loi)}/{len(rows)} lượt lỗi hoặc transcript rỗng — ĐẾM VÀO, không loại.")

    theo_wav: dict[str, list[str]] = {}
    for r in rows:
        theo_wav.setdefault(r["wav"], []).append(r["hypothesis"])
    doi = [w for w, v in theo_wav.items() if len(set(v)) > 1]
    n = len(theo_wav)

    import math
    def wilson(k: int, m: int, z: float = 1.96) -> tuple[float, float]:
        p = k / m; d = 1 + z * z / m; c = p + z * z / (2 * m)
        s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m))
        return ((c - s) / d, (c + s) / d)

    lo, hi = wilson(len(doi), n)
    print(f"\n  transcript đổi giữa {args.passes} lượt CÙNG BUỔI: "
          f"**{len(doi)}/{n}** = {len(doi)/n:.3f}   Wilson 95 % [{lo:.3f}, {hi:.3f}]")
    print(f"  (so với 5/31 = 0,161 của hai mẻ cách nhau MỘT NGÀY)")

    if len(doi) >= 4:
        print("\n  ĐỌC LÀ: bất định TRONG MỘT BUỔI ⇒ nghiêng về lấy mẫu, không phải version drift.")
    elif len(doi) == 0:
        print("\n  ĐỌC LÀ: trong một buổi thì ổn định ⇒ khoảng cách MỘT NGÀY đang làm việc,")
        print("           nghiêng về version drift phía nhà cung cấp.")
    else:
        print(f"\n  ⚠ NẰM GIỮA ({len(doi)}/{n}) — DỪNG, BÁO CHỦ NHÂN. Không tự chọn cách đọc.")

    if doi:
        print("\n  vài lượt đổi:")
        for w in doi[:3]:
            v = theo_wav[w]
            print(f"    {w}")
            for i, t in enumerate(v, 1):
                print(f"      lượt {i}: {t[:88]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
