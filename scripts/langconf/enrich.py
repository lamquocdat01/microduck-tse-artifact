r"""BƯỚC 3a — làm giàu jsonl thô thành jsonl ĐÃ CHẤM. Không gọi API.

    ..\..\desktop\.venv\Scripts\python.exe scripts\enrich.py results\main_gemini.jsonl

Sinh ra `<tên>_scored.jsonl`: mỗi dòng một lượt, mang **đủ trường để tính lại cả bốn
thước mà không cần chạy lại bộ nhận dạng ngôn ngữ** —

    1. label obedience             reply_lang == label_lang
    2. speaker-language accuracy   reply_lang == spoken_lang
    3. LPR / WPR (Cohere)          từ cờ dòng/từ, cho cả hai chuẩn ở trên
    4. LCE (Chen et al.)           mức câu và mức từ, cho cả hai chuẩn

Vì sao tách khỏi `runner.py`: chủ nhân dặn **không chấm điểm trong lúc gọi API**.
Vì sao tách khỏi `analyze.py`: `analyze` gom nhóm và bootstrap, mỗi lần đổi cách gom
là chạy lại nhận dạng ngôn ngữ cho cả 61 200 lượt. Làm giàu MỘT lần, rồi mọi bảng
đọc từ file đã giàu.

File thô (`messages`, `reply_text`) vẫn là nguồn sự thật và không bị đụng tới.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import lce as lce_mod                       # noqa: E402
from langconf.cohere_metrics import WPR_LANGS, CohereScorer   # noqa: E402
from langconf.langid import DualLangID                    # noqa: E402

DATA = ROOT / "data"

# Trường của dòng thô cần chép sang dòng đã chấm. `messages` KHÔNG chép — nó chiếm
# phần lớn dung lượng và đã nằm nguyên trong file thô; ghép lại bằng `trial_key`.
CARRY = (
    "trial_key", "ts", "label_condition", "asr_backend", "model", "target_lang",
    "confuse_lang", "depth", "label_position", "inject_source", "history_kind",
    "probe_id", "spoken_lang", "label_lang", "probe_source", "gold_text",
    "asr_text", "asr_lang", "asr_lang_p", "asr_model", "asr_low_confidence",
    "asr_fell_back", "asr_backend_used", "asr_tier", "reply_text", "latency_ms", "model_error",
    "in_tokens", "out_tokens", "finish_reason",
)


def verdict_fields(scorer: CohereScorer, reply: str, ref_lang: str, prefix: str) -> dict:
    """Cờ LPR/WPR theo một ngôn ngữ chuẩn. `ref_lang = None` -> mọi ô là None."""
    if ref_lang is None:
        return {f"{prefix}_{k}": None for k in
                ("ref_lang", "skipped", "n_lines", "line_errors", "line_error",
                 "word_error", "wpr_applies", "line_langs")}
    v = scorer.judge(reply, ref_lang)
    return {
        f"{prefix}_ref_lang": ref_lang,
        f"{prefix}_skipped": v.skipped,
        f"{prefix}_n_lines": v.n_lines,
        f"{prefix}_line_errors": v.line_errors,
        f"{prefix}_line_error": v.has_line_error,
        f"{prefix}_word_error": v.has_word_error,
        # WPR chỉ có nghĩa với ngôn ngữ không dùng chữ Latin (Cohere). Ghi cờ ra đây
        # để bảng sau không phải nhớ luật ấy — và để không ai lỡ tính WPR cho vi/id.
        f"{prefix}_wpr_applies": ref_lang in WPR_LANGS,
        f"{prefix}_line_langs": list(v.line_langs),
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-lce-word", action="store_true",
                        help="bỏ LCE mức từ (nhanh hơn; mức từ vốn nhiều nhiễu)")
    args = parser.parse_args()

    out_path = args.out or args.jsonl.with_name(args.jsonl.stem + "_scored.jsonl")
    scorer = CohereScorer(DATA / "lid" / "lid.176.bin", DATA / "lid" / "words")
    detector = DualLangID(DATA / "lid" / "lid.176.bin")
    # CHỈ fastText: LCE gọi nhận dạng ~40 lần mỗi lượt (một lần mỗi từ), và
    # `detect()` chạy kèm lingua nên đắt gấp 33 lần mà không dùng tới kết quả.
    detect_ft = detector.detect_fasttext

    started = time.perf_counter()
    n = skipped_errors = 0
    with open(args.jsonl, encoding="utf-8") as source, \
            open(out_path, "w", encoding="utf-8") as sink:
        for line in source:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("model_error"):
                # Lượt gọi model hỏng: chép sang để đếm được, nhưng KHÔNG chấm —
                # chấm một câu trả lời rỗng sẽ tính là "sai ngôn ngữ" và bơm lỗi
                # hạ tầng vào bảng kết quả.
                sink.write(json.dumps({k: row.get(k) for k in CARRY},
                                      ensure_ascii=False) + "\n")
                skipped_errors += 1
                continue

            reply = row.get("reply_text") or ""
            spoken, label = row["spoken_lang"], row.get("label_lang")
            whole = detector.detect(reply, record=False)

            enriched = {k: row.get(k) for k in CARRY}
            enriched.update({
                "reply_lang_fasttext": whole.fasttext,
                "reply_lang_fasttext_p": round(whole.fasttext_p, 4),
                "reply_lang_lingua": whole.lingua,
                "reply_lang_lingua_p": round(whole.lingua_p, 4),
                "reply_lang_agree": whole.agree,
                # Hai thước "khớp hay không" — tên theo docs/, không dùng
                # "language adherence" (đã bị DeepMind chiếm, xem scoring.py).
                "speaker_language_accuracy": whole.fasttext == spoken,
                "label_obedience": (whole.fasttext == label) if label else None,
                "lce_sentence_speaker": lce_mod.lce_sentence(reply, spoken, detect_ft).as_dict(),
                "lce_sentence_label": (lce_mod.lce_sentence(reply, label, detect_ft).as_dict()
                                       if label else None),
            })
            if not args.no_lce_word:
                enriched["lce_word_speaker"] = lce_mod.lce_word(reply, spoken, detect_ft).as_dict()
                enriched["lce_word_label"] = (lce_mod.lce_word(reply, label, detect_ft).as_dict()
                                              if label else None)
            enriched.update(verdict_fields(scorer, reply, spoken, "spk"))
            enriched.update(verdict_fields(scorer, reply, label, "lbl"))

            sink.write(json.dumps(enriched, ensure_ascii=False) + "\n")
            n += 1
            if n % 5000 == 0:
                print(f"  {n:,} lượt  ({n / (time.perf_counter() - started):.0f}/s)")

    print(f"{n:,} lượt đã chấm (+{skipped_errors:,} lượt model hỏng, chép nguyên) "
          f"-> {out_path}")
    print(f"  {time.perf_counter() - started:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
