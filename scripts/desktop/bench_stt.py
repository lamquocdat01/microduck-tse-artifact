"""So ba backend STT trên cùng một bộ audio — không cần micro (docs/ADR-004).

    python scripts\\bench_stt.py                       # giọng tổng hợp, cả 3 backend
    python scripts\\bench_stt.py --backends base gemini-audio
    python scripts\\bench_stt.py --from logs\\realvoice_20260904_101500   # chấm lại WAV giọng thật

Micro giả: 10 câu của `realvoice.SENTENCES` được chính TTS trong pipeline đọc ra
(VieNeu cho tiếng Việt, Kokoro cho tiếng Anh) rồi cho cả ba backend chép lại.

**Số ở đây LẠC QUAN.** Giọng TTS phát âm chuẩn, đều tiếng, không có tiếng ồn
phòng, không nuốt chữ — dễ hơn giọng người thật nhiều. Dùng nó để so THỨ HẠNG
giữa các backend, còn con số tuyệt đối phải lấy từ console web với giọng thật
(`realvoice_*.json`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import realvoice  # noqa: E402
from config import LOGS_DIR, Config, enable_utf8_console  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backends", nargs="+", default=list(realvoice.BACKENDS))
    parser.add_argument("--from", dest="source", default=None,
                        help="thư mục realvoice_* có sẵn WAV giọng thật, thay cho giọng tổng hợp")
    parser.add_argument("--vieneu-precision", choices=["fp32", "int8"], default="fp32")
    return parser.parse_args()


def synthesize(session: realvoice.TestSession, tts: object) -> None:
    """Đọc 10 câu bằng chính TTS của pipeline rồi lưu thành WAV."""
    for sentence in realvoice.SENTENCES:
        if sentence["lang"] == "vi":
            chunks = list(tts.vieneu.stream(sentence["text"]))
        else:
            chunks = list(tts._process_kokoro(sentence["text"], "en"))
        audio = np.concatenate(chunks).astype(np.int16)
        session.capture(audio, {"text": "", "language": sentence["lang"], "backend": "synth"})


def load_existing(session: realvoice.TestSession, source: Path) -> None:
    files = sorted(source.glob("utt_*.wav"))
    if not files:
        raise SystemExit(f"Không thấy utt_*.wav trong {source}")
    for path in files:
        index = int(path.stem.split("_")[1]) - 1
        expected = realvoice.SENTENCES[index]
        session.utterances.append(realvoice.Utterance(
            index=index,
            reference=expected["text"],
            reference_lang=expected["lang"],
            wav_path=path,
            audio_s=round(len(realvoice.read_wav(path)) / realvoice.SAMPLE_RATE, 2),
        ))


def print_table(report: dict) -> None:
    print(f"\n{'backend':<20}{'WER':>8}{'CER':>8}{'ngôn ngữ':>10}{'STT p50':>10}{'STT tb':>9}   (ms)")
    for name, summary in report["backends"].items():
        print(
            f"{name:<20}{summary['wer'] * 100:>7.1f}%{summary['cer'] * 100:>7.1f}%"
            f"{summary['language_accuracy'] * 100:>9.0f}%{summary['median_stt_ms']:>10.0f}{summary['mean_stt_ms']:>9.0f}"
        )
    if report["skipped_backends"]:
        print(f"\nBỏ qua (model chưa nạp): {', '.join(report['skipped_backends'])}")

    print("\nCâu nào sai ở đâu:")
    for name, summary in report["backends"].items():
        wrong = [row for row in summary["utterances"] if row["wer"] > 0 or not row["language_ok"]]
        print(f"\n  {name}: {len(wrong)}/{len(summary['utterances'])} câu có lỗi")
        for row in wrong:
            flag = "" if row["language_ok"] else f"  [ngôn ngữ {row['language']} != {row['reference_lang']}]"
            print(f"    {row['index']:>2}. WER {row['wer'] * 100:>5.1f}%{flag}")
            print(f"        gốc : {row['reference']}")
            print(f"        nghe: {row['hypothesis']}")


def main() -> int:
    enable_utf8_console()
    args = parse_args()
    cfg = Config.load()
    if problems := cfg.problems():
        for problem in problems:
            print(f"  - {problem}")
        return 1

    from pipeline import build_pipeline

    print("Đang nạp model (cả ba backend)...")
    duck = build_pipeline(
        cfg,
        vieneu_precision=args.vieneu_precision,
        with_brain=False,
        log_latency=False,
        with_bus=False,
        preload_all_stt=True,
    )

    session = realvoice.TestSession.create(LOGS_DIR)
    if args.source:
        load_existing(session, Path(args.source))
        print(f"Chấm lại {len(session.utterances)} WAV giọng thật từ {args.source}")
    else:
        print("Tổng hợp 10 câu bằng chính TTS của pipeline (micro giả)...")
        synthesize(session, duck.tts)

    report = realvoice.score_session(
        session,
        duck.stt,
        backends=tuple(args.backends),
        on_progress=lambda backend, i, n: print(f"  {backend}: {i}/{n}", end="\r"),
    )
    report["source"] = args.source or "giọng tổng hợp (VieNeu + Kokoro)"
    path = realvoice.write_report(report, LOGS_DIR)
    print_table(report)
    print(f"\nĐã ghi {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
