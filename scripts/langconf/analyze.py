r"""BƯỚC 3 — đọc jsonl, chấm, in bảng. KHÔNG gọi API.

    ..\..\desktop\.venv\Scripts\python.exe scripts\analyze.py results\main.jsonl

Tách hẳn khỏi lúc chạy (chủ nhân dặn): sửa bộ chấm rồi chạy lại script này bao nhiêu
lần cũng được, không tốn một đồng và không đụng vào dữ liệu thô.

Mỗi bảng in HAI thước tách rời khi điều kiện là ASR:

    label obedience            reply_lang == label_lang   (nhãn máy đưa, có thể sai)
    speaker-language accuracy  reply_lang == spoken_lang  (ngôn ngữ người thật sự nói)

Ở F5 = none không có nhãn -> ô "label obedience" để TRỐNG, không điền 0.
Mọi tỉ lệ kèm CI 95 % bootstrap. Không có số trần ở đây.
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

# Cách gom ô cho từng bảng. Khoá là tên bảng, giá trị là các trường của dòng jsonl.
VIEWS = {
    "F4-depth": ("model", "label_condition", "target_lang", "confuse_lang",
                 "label_position", "inject_source", "history_kind", "depth"),
    "F5-label": ("model", "label_condition", "depth", "history_kind", "label_position"),
    "F6-source": ("model", "label_condition", "depth", "history_kind", "inject_source"),
    "F3-pair": ("model", "label_condition", "label_position", "history_kind",
                "target_lang", "confuse_lang"),
    "F1-asr": ("model", "label_position", "history_kind", "label_condition", "asr_backend"),
    "F2-model": ("label_condition", "label_position", "history_kind", "model"),
    # B2 — bất đối xứng chiều ngôn ngữ. Kim et al. (MME @ EACL 2026) thấy EN->X giữ
    # 89-99 % theo ngôn ngữ câu hỏi, còn X->EN thì phân kỳ mạnh giữa các model. Số cũ
    # của repo này khớp: 0/15 lỗi khi nói tiếng Việt, 13/15 khi nói tiếng Anh trong
    # lịch sử tiếng Việt (docs/ADR-008). View này báo theo TỪNG CHIỀU, và giữ
    # `label_condition` trong khoá để trả lời được phần họ KHÔNG có: bất đối xứng
    # còn giữ không khi nhãn đến từ ASR thay vì oracle.
    "asymmetry": ("model", "label_condition", "history_kind", "depth",
                  "target_lang", "confuse_lang"),
}


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="+", type=Path)
    parser.add_argument("--view", choices=sorted(VIEWS), default="F4-depth")
    # 2000 lần lấy mẫu lại, không phải 10 000: khoảng phần trăm đã ổn định ở mức này,
    # còn 10 000 thì một lượt phân tích lưới đầy đủ (>1200 ô × 3 thống kê) mất hàng
    # chục phút. Cần số chốt cho bài báo thì chạy lại với --resamples 10000.
    parser.add_argument("--resamples", type=int, default=2_000)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    rows = load(args.jsonl)
    ok = [r for r in rows if not r.get("model_error")]
    bad = [r for r in rows if r.get("model_error")]
    errors = collections.Counter(
        str(r["model_error"]).split(":")[0] for r in rows if r.get("model_error")
    )
    print(f"{len(rows):,} dòng, {len(ok):,} chấm được, {len(rows) - len(ok):,} lượt model hỏng")
    if errors:
        print(f"  lỗi: {dict(errors)}")

    scorer = CohereScorer(DATA / "lid" / "lid.176.bin", DATA / "lid" / "words")
    detector = DualLangID(DATA / "lid" / "lid.176.bin")

    fields = VIEWS[args.view]
    groups: dict[tuple, dict[str, list]] = collections.defaultdict(
        lambda: {"speaker_language_accuracy": [], "label_obedience": []}
    )
    n_by_group: collections.Counter = collections.Counter()
    # Đếm lượt gọi model HỎNG theo từng ô. Không đếm thì trường `n_model_errors`
    # trong JSON luôn bằng 0 (vì `ok` đã lọc chúng ra) — một con số đúng tên mà luôn
    # nói dối, và người đọc sẽ tưởng ô nào cũng đủ mẫu.
    err_by_group: collections.Counter = collections.Counter()
    for row in bad:
        err_by_group[tuple(row.get(f) for f in fields)] += 1
    # Dòng đã qua `scripts/enrich.py` mang sẵn nhãn ngôn ngữ -> dùng thẳng. Vừa nhanh
    # hơn hai bậc, vừa bảo đảm mọi bảng đọc CÙNG một bộ nhãn.
    scored = bool(ok) and "reply_lang_fasttext" in ok[0]
    print("nguồn nhãn ngôn ngữ:",
          "trường đã chấm sẵn (enrich.py)" if scored else "tính lại tại chỗ")
    lce_by_group: dict[tuple, list[float]] = collections.defaultdict(list)
    for row in ok:
        key = tuple(row.get(f) for f in fields)
        n_by_group[key] += 1
        if scored:
            block = row.get("lce_sentence_speaker") or {}
            if block.get("lce") is not None:
                lce_by_group[key].append(float(block["lce"]))
        for ruler in ("speaker_language_accuracy", "label_obedience"):
            judged = (scoring.judge_from_scored(row, ruler) if scored
                      else scoring.judge(row, ruler, scorer, detector))
            if judged is not None:
                groups[key][ruler].append(judged)

    # Cổng đồng thuận hai thước nhận dạng — chủ nhân đặt ngưỡng 3 %.
    # Ở đường nhanh, detector không được gọi lần nào nên `agreement_report()` sẽ trả
    # 0/0 và cổng im lặng mở toang. Lấy từ trường `reply_lang_agree` đã ghi sẵn.
    if scored:
        from langconf.langid import _same_language

        def same(row) -> bool:
            return _same_language(row.get("reply_lang_fasttext") or "unknown",
                                  row.get("reply_lang_lingua") or "unknown")

        agree = sum(same(r) for r in ok)
        strict = sum(bool(r.get("reply_lang_agree")) for r in ok)
        rate = 1 - agree / len(ok) if ok else 0.0
        examples = [{"len": len(r.get("reply_text") or ""),
                     "fasttext": r.get("reply_lang_fasttext"),
                     "lingua": r.get("reply_lang_lingua")}
                    for r in ok if not same(r)][:20]
        report = {"n": len(ok), "agree": agree, "disagree": len(ok) - agree,
                  "disagree_rate": rate, "disagree_strict": len(ok) - strict,
                  "disagree_rate_strict": 1 - strict / len(ok) if ok else 0.0,
                  "threshold": 0.03, "stop": rate > 0.03, "examples": examples}
    else:
        report = detector.agreement_report()
    print(f"Đồng thuận fastText/lingua: {report['agree']:,}/{report['n']:,} "
          f"(lệch {report['disagree_rate']:.2%}, ngưỡng 3 %)")
    if report.get("disagree_rate_strict") is not None:
        print(f"  lệch theo MÃ (chưa gộp id/ms): {report['disagree_rate_strict']:.2%} "
              f"— chênh giữa hai con số này là cặp Indonesia/Mã Lai, xem langconf/langid.py")
    if report["stop"]:
        print()
        print("  >>> LỆCH QUÁ 3 % — DỪNG. Không đọc bảng dưới đây như số cuối cùng.")
        print("  Vài ca lệch:")
        for example in report["examples"]:
            print(f"    len={example['len']:>4}  fastText={example['fasttext']:<10}"
                  f"lingua={example['lingua']}")

    print()
    header = "  " + "".join(f"{f:<16}" for f in fields)
    print(header + f"{'n':>5}  {'speaker-lang acc':<30}{'label obedience':<30}"
          f"{'LPR (speaker-lang)':<30}{'LCE câu':>9}bỏ")
    print("  " + "-" * (len(header) + 100))

    out_rows = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        truth = groups[key]["speaker_language_accuracy"]
        compliance = groups[key]["label_obedience"]
        summary_t = scoring.summarize_cell(key, truth, ruler="speaker_language_accuracy",
                                           n_errors=err_by_group[key], resamples=args.resamples)
        summary_c = (scoring.summarize_cell(key, compliance, ruler="label_obedience",
                                            n_errors=err_by_group[key],
                                            resamples=args.resamples)
                     if compliance else None)
        print("  " + "".join(f"{str(v):<16}" for v in key)
              + f"{n_by_group[key]:>5}  "
              + f"{str(summary_t.match):<30}"
              + f"{(str(summary_c.match) if summary_c else '—'):<30}"
              + f"{str(summary_t.lpr):<30}"
              + (f"{sum(lce_by_group[key]) / len(lce_by_group[key]):>9.3f}"
                 if lce_by_group.get(key) else f"{'—':>9}")
              + f"{summary_t.skipped:>4}"
              + (f"  HỎNG {err_by_group[key]}" if err_by_group[key] else ""))
        out_rows.append({
            "key": dict(zip(fields, key)),
            "n": n_by_group[key],
            "speaker_language_accuracy": summary_t.as_dict(),
            "label_obedience": summary_c.as_dict() if summary_c else None,
            "lce_sentence_mean": (sum(lce_by_group[key]) / len(lce_by_group[key])
                                  if lce_by_group.get(key) else None),
        })

    if args.json_out:
        args.json_out.write_text(
            json.dumps({"view": args.view, "fields": list(fields),
                        "langid_agreement": report, "rows": out_rows},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"\nGhi {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
