r"""BƯỚC 3b — hai bảng chính của bài. Đọc jsonl, không gọi API.

    ..\..\desktop\.venv\Scripts\python.exe scripts\contrasts.py results\main_gemini.jsonl

**Bảng 1 — hiệu số nhiễm − sạch.** Ở mỗi độ sâu, cùng model / cùng hướng / cùng vị trí
nhãn / cùng nguồn, hai ô chỉ khác nhau đúng MỘT biến: ngôn ngữ của lượt trợ lý trong
lịch sử. Hiệu số giữa chúng là hiệu ứng nhiễm, và nó được bootstrap **ghép cặp theo
câu thăm dò** — hai ô dùng đúng cùng 50 câu FLoRes, nên lấy mẫu lại phải lấy theo câu.
Đây là con số trả lời trực tiếp chỗ Cohere tự khai chưa làm.

**Bảng 2 — nhãn ASR sai bao nhiêu.** Tầng thứ nhất của lỗi cộng dồn, đo riêng, không
dính gì tới LLM: `asr_lang != spoken_lang`. Không có bảng này thì bảng "label obedience"
và bảng "speaker-language accuracy" ở `analyze.py` treo lơ lửng, người đọc không biết
khoảng cách giữa chúng đến từ đâu.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import scoring                              # noqa: E402
from langconf.cohere_metrics import CohereScorer          # noqa: E402
from langconf.langid import DualLangID                    # noqa: E402

DATA = ROOT / "data"

# Mọi trường trừ `history_kind` — đó là biến duy nhất được phép khác giữa hai ô.
PAIR_FIELDS = ("model", "label_condition", "asr_backend", "target_lang", "confuse_lang",
               "label_position", "inject_source", "depth")


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return [r for r in rows if not r.get("model_error")]


def table_contrast(rows: list[dict], scorer, detector, ruler: str, resamples: int) -> list[dict]:
    # Dòng đã qua `scripts/enrich.py` mang sẵn nhãn ngôn ngữ -> dùng thẳng, và quan
    # trọng hơn: bảng này đọc CÙNG bộ nhãn với `analyze.py`, không thể lệch nhau vì
    # detector chạy hai lần.
    scored = bool(rows) and "reply_lang_fasttext" in rows[0]
    buckets: dict[tuple, dict[str, dict[str, object]]] = collections.defaultdict(dict)
    for row in rows:
        if not row.get("depth"):
            continue                       # sâu 0 không có "sạch/nhiễm" để so
        judged = (scoring.judge_from_scored(row, ruler) if scored
                  else scoring.judge(row, ruler, scorer, detector))
        if judged is None:
            continue
        key = tuple(row.get(f) for f in PAIR_FIELDS)
        buckets[key].setdefault(row["history_kind"], {})[row["probe_id"]] = judged

    out = []
    for key in sorted(buckets, key=lambda k: tuple(str(x) for x in k)):
        sides = buckets[key]
        if "contaminated" not in sides or "clean" not in sides:
            continue                       # thiếu một bên thì không có hiệu số
        diff = scoring.paired_difference_by_probe(
            sides["contaminated"], sides["clean"], resamples=resamples
        )
        dirty, _, _ = scoring._match_statistic(list(sides["contaminated"].values()))
        clean, _, _ = scoring._match_statistic(list(sides["clean"].values()))
        out.append({"key": dict(zip(PAIR_FIELDS, key)), "n_paired": diff.n,
                    "contaminated": dirty, "clean": clean, "diff": diff})
    return out


def table_asr_label_errors(rows: list[dict]) -> list[dict]:
    """Tầng 1: ASR gán nhãn sai bao nhiêu phần trăm. Chỉ đếm mỗi (audio, backend) MỘT lần.

    Một câu thăm dò xuất hiện ở hàng chục ô với cùng bản chép (bộ đệm ASR đóng băng),
    nên đếm theo dòng jsonl sẽ thổi phồng mẫu lên hàng chục lần và CI hẹp giả tạo.
    """
    seen: dict[tuple, dict] = {}
    for row in rows:
        if row.get("label_condition") != "asr":
            continue
        # `asr_backend_used` là backend THỰC SỰ chép; `asr_backend` là ô thiết kế.
        # File cũ (trước 07/09) chỉ có cái sau — nhận cả hai để chấm lại được.
        used = row.get("asr_backend_used") or row.get("asr_backend")
        key = (row.get("asr_tier"), used, row["spoken_lang"], row["probe_id"])
        seen.setdefault(key, row)

    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for (tier, backend, spoken, _), row in seen.items():
        groups[(tier, backend, spoken)].append(row)

    out = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        items = groups[key]
        wrong = [r for r in items if r.get("asr_lang") != r["spoken_lang"]]
        stat = lambda xs: ((sum(x["asr_lang"] == x["spoken_lang"] for x in xs) / len(xs),
                            len(xs),
                            sum(x["asr_lang"] == x["spoken_lang"] for x in xs))
                           if xs else (float("nan"), 0, 0.0))
        rate = scoring.bootstrap_rate(items, stat, resamples=2_000)
        heard = collections.Counter(r.get("asr_lang") for r in wrong)
        out.append({"tier": key[0], "backend": key[1], "spoken": key[2],
                    "rate": rate, "n_wrong": len(wrong), "heard_as": dict(heard),
                    "low_conf": sum(bool(r.get("asr_low_confidence")) for r in items)})
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="+", type=Path)
    parser.add_argument("--ruler", choices=["speaker_language_accuracy", "label_obedience"], default="speaker_language_accuracy")
    parser.add_argument("--resamples", type=int, default=2_000)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    rows = load(args.jsonl)
    print(f"{len(rows):,} lượt chấm được\n")

    print("=" * 110)
    print("BẢNG 2 — tầng 1 của lỗi cộng dồn: ASR gán nhãn ĐÚNG bao nhiêu")
    print("=" * 110)
    asr = table_asr_label_errors(rows)
    if not asr:
        print("  (không có lượt nào ở điều kiện F1 = ASR trong dữ liệu này)")
    else:
        print(f"  {'hạng':<12}{'backend':<20}{'nói':<5}{'nhãn đúng':<30}"
              f"{'nghe nhầm thành':<24}tin cậy thấp")
        for row in asr:
            print(f"  {str(row['tier']):<12}{str(row['backend']):<20}{row['spoken']:<5}"
                  f"{str(row['rate']):<30}{str(row['heard_as'] or '—'):<24}{row['low_conf']}")

    print()
    print("=" * 110)
    print(f"BẢNG 1 — hiệu số (lịch sử NHIỄM − lịch sử SẠCH), thước '{args.ruler}',")
    print("         bootstrap ghép cặp theo câu thăm dò. Âm = nhiễm làm tụt.")
    print("  Đọc cột label_position như sau:")
    print("    none    = không can thiệp, đường cơ sở")
    print("    system  = TÁI LẬP kết quả âm của Kim et al. (MME @ EACL 2026): họ thử")
    print("              'a simple explicit system prompt' và báo 'limited effectiveness'")
    print("    user    = biện pháp của bài này, đặt cạnh để so trực tiếp")
    print("=" * 110)
    scorer = CohereScorer(DATA / "lid" / "lid.176.bin", DATA / "lid" / "words")
    detector = DualLangID(DATA / "lid" / "lid.176.bin")
    contrasts = table_contrast(rows, scorer, detector, args.ruler, args.resamples)
    if not contrasts:
        print("  (chưa có cặp sạch/nhiễm nào đủ hai bên)")
    else:
        header = "  " + "".join(f"{f:<15}" for f in PAIR_FIELDS)
        print(header + f"{'n':>4}  {'nhiễm':>8}{'sạch':>8}   hiệu số [CI 95 %]")
        for row in contrasts:
            key = row["key"]
            print("  " + "".join(f"{str(key[f]):<15}" for f in PAIR_FIELDS)
                  + f"{row['n_paired']:>4}  {row['contaminated']:>7.1%}{row['clean']:>8.1%}"
                  + f"   {row['diff'].value:+.1%} "
                  + f"[{row['diff'].lo:+.1%}, {row['diff'].hi:+.1%}]")

    if args.json_out:
        payload = {
            "ruler": args.ruler,
            "asr_label_accuracy": [
                {**{k: v for k, v in r.items() if k != "rate"}, "rate": r["rate"].as_dict()}
                for r in asr
            ],
            "contrasts": [
                {**{k: v for k, v in r.items() if k != "diff"}, "diff": r["diff"].as_dict()}
                for r in contrasts
            ],
        }
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        print(f"\nGhi {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
