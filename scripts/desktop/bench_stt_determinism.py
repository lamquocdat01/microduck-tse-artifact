r"""Tái lập phép A/B của ADR-007: `temperature=0` đổi gì ở tầng STT (việc 33).

    python scripts\bench_stt_determinism.py --rounds 3

ADR-007 báo `base` p95 **3 063 → 1 780 ms (−42 %)** khi ghim `temperature=0`. Mẻ sinh
ra con số ấy **không còn file nào** (việc 29b đã soi hết `desktop/logs/`), nên số ấy
đang mang nhãn `[ĐO LẠI ĐƯỢC]` chứ chưa được coi là số của bài. Script này chạy lại
đúng thiết kế cũ trên **đúng bộ audio cũ**, nên nó là **tái lập**, không phải phép đo
mới — 10 WAV của `realvoice_20260904` còn nguyên ở `docs/benchmark/realvoice_20260904/`.

## Thiết kế, giữ đúng ba điểm của ADR-007

1. **Cùng một tiến trình, xen kẽ cũ/mới.** Tranh chấp CPU phạt Whisper tới 5,4×
   (ADR-005), nên chạy hai điều kiện ở hai tiến trình khác nhau là mời trạng thái máy
   dồn hết vào một bên. Xen kẽ trong một tiến trình thì cái phạt ấy rơi đều.
2. **Ba vòng**, để p95 có đủ điểm: 10 WAV × 3 vòng = **n = 30** mỗi ô.
3. **Hai backend** (`base`, `phowhisper-reread`) × **hai điều kiện** (cũ = dải fallback
   0→1 của faster-whisper; mới = ghim `temperature=0`).

`gemini-audio` KHÔNG tham gia: nó vốn đã đặt `temperature=0` nên không có nhánh "cũ",
và bỏ nó ra thì mẻ này chạy **hoàn toàn ngoại tuyến, không tốn hạn mức API**.

## Cái bẫy mẻ đầu vấp phải — và vì sao phải ghi temperature tường minh cho CẢ HAI nhánh

ADR-007 đã được **thi hành**: `DuckSTTHandler.setup` nay đặt sẵn `"temperature": 0.0`
trong `gen_kwargs` mặc định. Nên `deterministic=False` của `rescore_utts.py`
**không còn dựng lại hành vi cũ** — nó cũng là nhánh mới. Mẻ đầu chạy đúng như thế và
đo **cùng một điều kiện hai lần**: transcript trùng khít từng chữ, WER bằng nhau tuyệt
đối ở cả hai nhánh, còn p95 lệch −9,0 % và +10,7 %.

Mẻ ấy **giữ lại làm đối chứng rỗng** (`stt_determinism_20260910_v2_doichung_rong.jsonl`):
nó đo **sàn nhiễu p95 giữa hai lần chạy cùng điều kiện** trên máy này, và đó đúng là
thước cần có để biết một chênh lệch p95 thật thì phải lớn cỡ nào mới đáng tin.

Bài học: **đừng suy ra điều kiện từ việc KHÔNG truyền tham số.** Ghi thẳng
`temperature` cho cả hai nhánh, và in ra lúc chạy.

## Ba thứ bắt buộc ghi cạnh mỗi con số (luật của PAPER-NUMBERS.md)

- **quy ước phân vị**: `sorted(v)[round(q·(n−1))]` — phân vị gần nhất, KHÔNG nội suy,
  giống `bench_latency.py::_pct`. Chú ý `rescore_utts.py` báo `stt_p50` bằng
  `statistics.median` (có nội suy khi n chẵn) — ở đây **không** dùng cách đó.
- **lát cắt hàng**: mọi lượt của cả 3 vòng, không bỏ lượt nào, n = 30 mỗi ô.
- **thước WER**: báo cả ba thước O/N/D của `docs/benchmark/PROTOCOL.md`.

## Thứ ADR-007 khẳng định mà chưa từng đo thẳng

Cột "tất định" của ADR-007 là **có/không**, không có số. Ở đây đo thẳng: mỗi câu chép
3 lần, đếm số câu cho ra **≥ 2 transcript khác nhau**. Đó mới là định nghĩa "tất định =
cùng đầu vào cho cùng đầu ra", và nó là con số nói đúng điều tầng STT cần nói trong
Bảng 1.

KHÔNG ghi vào `logs/latency.jsonl`, KHÔNG đụng `docs/baseline/`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, enable_utf8_console  # noqa: E402
from scoring import corpus_score  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rescore_utts import WER_VARIANTS, build_stt, run  # noqa: E402

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
WAV_DIR = BENCH_DIR / "realvoice_20260904"
REFS = BENCH_DIR / "stt_realvoice_20260904_scored.json"

BACKENDS = ("base", "phowhisper-reread")
# Dải fallback mặc định của faster-whisper. PHẢI ghi tường minh: từ khi ADR-007 được
# thi hành, `DuckSTTHandler.setup` đặt sẵn `temperature: 0.0`, nên `gen_kwargs=None`
# KHÔNG còn nghĩa là "như cũ" — nó đã là nhánh mới. Mẻ đầu của việc 33 vấp đúng chỗ này
# và đo cùng một điều kiện hai lần (giữ lại làm đối chứng rỗng, xem docstring).
LADDER = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

# (nhãn, gen_kwargs) — ghi thẳng temperature cho CẢ HAI nhánh, không dựa vào mặc định.
DIEU_KIEN = (("cu", {"temperature": LADDER}), ("moi", {"temperature": 0.0}))


def pxx(values: list[float], q: float) -> float:
    """Phân vị gần nhất, KHÔNG nội suy — quy ước dùng cho cả bài."""
    xep = sorted(values)
    return xep[min(len(xep) - 1, max(0, round(q * (len(xep) - 1))))]


def doc_refs() -> list[dict[str, Any]]:
    wavs = sorted(WAV_DIR.glob("*.wav"))
    if not wavs:
        raise SystemExit(f"Không có WAV nào trong {WAV_DIR}")
    data = json.loads(REFS.read_text(encoding="utf-8"))
    rows = next(iter(data["backends"].values()))["utterances"]
    theo_index = {r["index"]: r for r in rows}
    ra = []
    for index, wav in enumerate(wavs, start=1):
        row = theo_index.get(index)
        if row is None:
            raise SystemExit(f"{REFS.name} không có câu số {index} cho {wav.name}")
        ra.append({"wav": wav, "text": row["reference"], "lang": row["reference_lang"]})
    return ra


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rounds", type=int, default=3, help="số vòng (ADR-007 dùng 3)")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cfg = Config.load()
    refs = doc_refs()
    tong_s = sum(0 for _ in refs)  # giữ chỗ, độ dài in ở dưới
    print(f"Tái lập A/B của ADR-007: {len(refs)} WAV × {len(BACKENDS)} backend"
          f" × {len(DIEU_KIEN)} điều kiện × {args.rounds} vòng"
          f" = {len(refs) * len(BACKENDS) * len(DIEU_KIEN) * args.rounds} lượt chép")
    print(f"Audio: {WAV_DIR}   ground truth: {REFS.name}")
    print("Không gọi API — chỉ Whisper cục bộ.\n")

    print("Đang nạp model (hai handler: cũ và mới)...")
    handlers = {}
    for ten, gk in DIEU_KIEN:
        stt = build_stt(cfg, with_gemini=False, deterministic=False)
        stt.gen_kwargs = {**stt.gen_kwargs, **gk}     # ghi đè tường minh, không tin mặc định
        handlers[ten] = stt
        print(f"  {ten}: temperature = {stt.gen_kwargs['temperature']}")

    rows: list[dict[str, Any]] = []
    for vong in range(1, args.rounds + 1):
        # Xen kẽ cũ/mới NGAY TRONG một vòng: trạng thái máy trôi thì nó trôi đều
        # cho cả hai điều kiện chứ không dồn vào một bên (ADR-005).
        for ten, _gk in DIEU_KIEN:
            for backend in BACKENDS:
                nhan = f"vòng {vong} · {ten} · {backend}"
                ket = run(handlers[ten], refs, nhan, backend, "auto")
                for r in ket["utterances"]:
                    rows.append({"vong": vong, "dieu_kien": ten, "backend": backend, **r})

    out = Path(args.out) if args.out else BENCH_DIR / f"stt_determinism_{date.today():%Y%m%d}_v2.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nGhi {len(rows)} bản ghi vào {out}")

    # ---- tổng kết ----------------------------------------------------------
    print("\n" + "=" * 100)
    print("KẾT QUẢ — phân vị: gần nhất, không nội suy · lát cắt: mọi lượt của cả"
          f" {args.rounds} vòng, n = {len(refs) * args.rounds} mỗi ô")
    print("=" * 100)
    print(f"\n{'backend':<20}{'điều kiện':<12}{'n':<5}{'t_stt p50':>11}{'p95':>11}"
          f"{'max':>11}   {'WER-D':>7}{'WER-N':>7}{'WER-O':>7}")
    tom: dict[tuple[str, str], dict[str, Any]] = {}
    for backend in BACKENDS:
        for ten, _gk in DIEU_KIEN:
            con = [r for r in rows if r["backend"] == backend and r["dieu_kien"] == ten]
            ms = [r["stt_ms"] for r in con]
            cap = [(r["reference"], r["hypothesis"]) for r in con]
            wer = {tag: round(corpus_score(cap, fn).wer, 4) for tag, fn in WER_VARIANTS}
            tom[(backend, ten)] = {"n": len(con), "p50": pxx(ms, 0.5), "p95": pxx(ms, 0.95),
                                   "max": max(ms), **{f"wer_{k}": v for k, v in wer.items()}}
            print(f"{backend:<20}{ten:<12}{len(con):<5}{pxx(ms, 0.5):>11.1f}{pxx(ms, 0.95):>11.1f}"
                  f"{max(ms):>11.1f}   {wer['d']:>7.3f}{wer['n']:>7.3f}{wer['o']:>7.3f}")

    print("\n--- ADR-007 báo gì, mẻ này báo gì ---")
    print(f"  {'ô':<34}{'ADR-007':>12}{'đo lại':>12}{'lệch':>12}")
    ADR = {("base", "cu", "p95"): 3063.0, ("base", "moi", "p95"): 1780.0,
           ("phowhisper-reread", "cu", "p95"): 3133.0, ("phowhisper-reread", "moi", "p95"): 2590.0,
           ("base", "cu", "p50"): 1758.0, ("base", "moi", "p50"): 1596.0,
           ("phowhisper-reread", "cu", "p50"): 2501.0, ("phowhisper-reread", "moi", "p50"): 2042.0}
    for (backend, ten, moc), cu in sorted(ADR.items()):
        moi = tom[(backend, ten)][moc]
        print(f"  {backend + ' · ' + ten + ' · ' + moc:<34}{cu:>12.0f}{moi:>12.1f}{moi - cu:>+12.1f}")

    print("\n--- Con số của Bảng 1: p95 giảm bao nhiêu khi ghim temperature=0 ---")
    for backend in BACKENDS:
        cu, moi = tom[(backend, "cu")]["p95"], tom[(backend, "moi")]["p95"]
        print(f"  {backend:<20}{cu:>9.1f} → {moi:>9.1f} ms   = {(moi - cu) / cu:+7.1%}"
              f"      (ADR-007: {'−42 %' if backend == 'base' else '−17 %'})")

    print("\n--- TẤT ĐỊNH đo thẳng: câu nào cho ≥2 transcript khác nhau qua"
          f" {args.rounds} vòng ---")
    for backend in BACKENDS:
        for ten, _gk in DIEU_KIEN:
            theo_wav: dict[str, set] = defaultdict(set)
            for r in rows:
                if r["backend"] == backend and r["dieu_kien"] == ten:
                    theo_wav[r["wav"]].add(r["hypothesis"])
            lech = [w for w, v in theo_wav.items() if len(v) > 1]
            print(f"  {backend:<20}{ten:<8}{len(lech)}/{len(theo_wav)} câu bất ổn"
                  f"{'   ' + ', '.join(sorted(lech)) if lech else ''}")
    print("\nSố này ADR-007 chỉ ghi có/không, chưa bao giờ có số.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
