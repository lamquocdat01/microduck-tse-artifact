r"""Chấm lại một thư mục WAV bằng cả ba backend STT + biến thể `vi+en`.

    python scripts\rescore_utts.py logs\utts --prompts --repeat 3
    python scripts\rescore_utts.py logs\realvoice_20260904_142650 --refs logs\realvoice_20260904_142650.json
    python scripts\rescore_utts.py logs\utts --refs refs.json --no-gemini

Vì sao có script này: ADR-004 tắc vì phiên giọng thật 06/09 nói xong là mất audio.
Nay `handlers/stt_whisper.py` lưu mọi lượt vào `logs/utts/`, và đây là chỗ đọc lại
CÙNG những file đó bằng từng backend — chỉ khi cùng một audio thì WER mới so được.

**KHÔNG đọc, không sửa `.env`.** `language_mode` đổi bằng thuộc tính của handler
đang sống trong tiến trình này, nên chạy script không làm lệch cấu hình đang dùng.

Ground truth lấy theo một trong ba cách:

    --prompts [--repeat N] [--order block|round]
                            `realvoice.SENTENCES` ghép theo thứ tự tên file.
                            block (mặc định) = đọc mỗi câu N lần LIÊN TIẾP: S1 S1 S1 S2 S2 S2...
                            round            = đọc hết một vòng rồi lặp:     S1 S2 ... S10 S1 S2...
                            Phiên 06/09 đọc theo `block`; bản đầu của script chỉ có `round`
                            nên ghép sai thứ tự. Số WAV lệch với N×10 thì báo lỗi chứ không đoán.
    --refs <report.json>    báo cáo của bài test 10 câu (`logs/realvoice_<ts>.json`).
    --refs <refs.json>      {"<tên file>.wav": {"text": ..., "lang": "vi"}, ...}

Nhớ tắt console trước khi chạy: hai tiến trình cùng nạp model thì số t_stt vô
nghĩa, và tranh CPU phạt Whisper 5,4× (ADR-005).

## `--deterministic`: vì sao chạy hai lần ra hai số khác nhau

Pipeline không ghim `temperature`, nên faster-whisper dùng dải fallback mặc định
(0,0 → 1,0): decode tham lam nào không qua ngưỡng compression-ratio/logprob thì
nó **chép lại với temperature > 0**, tức là ngẫu nhiên. Câu rất ngắn rơi vào đó
gần như chắc chắn — "Dừng." (0,8 s) đo bốn lần ra "You" / "I'm sorry." /
"It's all right." / "Thank you very much.", làm WER toàn bộ 10 câu nhảy ±0,04.
`gemini-audio` không dính vì nó đặt `temperature=0`.

Mặc định script chạy **đúng như pipeline thật** (có fallback), để số đo tả đúng
cái người dùng gặp. Cần so backend với backend thì bật `--deterministic` để ghim
`temperature=0` — lúc đó số lặp lại được, nhưng nhớ là nó lạc quan hơn thực tế.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audio_wav import read_wav  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402
from scoring import (  # noqa: E402
    corpus_score, normalize_nwer, normalize_ower, score,
)

# Ba thước chạy SONG SONG trên cùng một transcript. Không cái nào thay cái nào.
#
#   O-WER  chữ thô, giữ hoa/thường và dấu câu       (Vu et al., EACL 2026, §5.1)
#   N-WER  chữ thường + bỏ toàn bộ dấu câu           (cùng nguồn)
#   D-WER  N-WER + quy số-chữ về chữ số + biến thể   (thước cũ của repo này)
#          tên riêng -- tức là thước LỎNG NHẤT
#
# Vì sao phải có cả ba: bài trên cho thấy cùng audio cùng model, PhoWhisper-small
# ra O-WER 33,90 nhưng N-WER 8,97, và THỨ HẠNG ĐỔI giữa hai thước trong chính
# bảng của họ. Nếu thứ hạng backend của ta cũng đổi thì ADR-004 phải xem lại.
# Chi tiết giao thức + trích dẫn: docs/benchmark/PROTOCOL.md
# Hai backend cách nhau dưới ngưỡng này ở một thước thì coi như HOÀ: thứ tự giữa
# chúng là ngẫu nhiên, và "đổi thứ hạng" ở đó không nói lên điều gì. 0,02 WER trên
# 31 câu ≈ vài từ — dưới mức phân giải của mẫu này.
TIE = 0.02

WER_VARIANTS: tuple[tuple[str, Any], ...] = (
    ("o", normalize_ower),
    ("n", normalize_nwer),
    ("d", None),          # None = normalize() mặc định của scoring.py
)

# (nhãn, backend, language_mode)
CONDITIONS: tuple[tuple[str, str, str], ...] = (
    ("base", "base", "auto"),
    ("phowhisper-reread", "phowhisper-reread", "auto"),
    ("gemini-audio", "gemini-audio", "auto"),
    ("phowhisper + vi+en", "phowhisper-reread", "vi+en"),
)

# Ứng viên local nặng hơn, chỉ chạy khi có `--local-candidates`: mỗi cái phải nạp
# thêm một model vào RAM nên không đáng trả giá ở lần chấm thường. Dùng để bài báo
# có cột local-vs-cloud tử tế.
#
#   phowhisper-small : ĐÚNG kiến trúc mặc định hiện nay (base nhận diện + PhoWhisper
#                      đọc lại câu tiếng Việt), chỉ thay model đọc lại base -> small.
#                      Đây là bản nâng cấp thả-vào-chỗ-cũ, không đổi cách chạy.
#   large-v3-turbo   : một model đa ngôn ngữ lo cả hai thứ tiếng, KHÔNG đọc lại.
#                      ADR-002 từng loại nó vì chậm, nhưng số đó đo trước ADR-007.
LOCAL_CANDIDATES: tuple[dict[str, Any], ...] = (
    {"label": "phowhisper-small (reread)", "model": None,
     "vi_model": "models/phowhisper-small-ct2", "backend": "phowhisper-reread"},
    {"label": "large-v3-turbo", "model": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
     "vi_model": None, "backend": "base"},
)


def _rss_mb() -> float:
    import psutil

    return psutil.Process().memory_info().rss / 1024 / 1024


def _pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def load_refs(wavs: list[Path], args: argparse.Namespace) -> list[dict[str, Any]]:
    """Ghép mỗi WAV với (câu mẫu, ngôn ngữ người nói). Thiếu thì báo, không đoán."""
    if args.prompts:
        from realvoice import SENTENCES

        if args.order == "block":
            expected = [s for s in SENTENCES for _ in range(args.repeat)]
        else:
            expected = [s for _ in range(args.repeat) for s in SENTENCES]
        if len(expected) != len(wavs):
            raise SystemExit(
                f"--prompts --repeat {args.repeat} --order {args.order} cho {len(expected)} "
                f"câu nhưng có {len(wavs)} file WAV. Đọc thừa/thiếu một lượt là đủ lệch cả "
                f"bảng, nên dùng --refs để ghép tường minh thay vì đoán."
            )
        return [{"wav": w, "text": e["text"], "lang": e["lang"]} for w, e in zip(wavs, expected)]

    data = json.loads(Path(args.refs).read_text(encoding="utf-8"))
    if "backends" in data:                      # báo cáo của bài test 10 câu
        rows = next(iter(data["backends"].values()))["utterances"]
        by_index = {r["index"]: r for r in rows}
        out = []
        for index, wav in enumerate(wavs, start=1):
            row = by_index.get(index)
            if row is None:
                raise SystemExit(f"Báo cáo không có câu số {index} cho {wav.name}")
            out.append({"wav": wav, "text": row["reference"], "lang": row["reference_lang"]})
        return out

    out = []                                    # {"<file>.wav": {"text", "lang"}}
    for wav in wavs:
        row = data.get(wav.name)
        if row is None:
            raise SystemExit(f"refs không có mục cho {wav.name}")
        out.append({"wav": wav, "text": row["text"], "lang": row["lang"]})
    return out


def build_stt(cfg: Config, with_gemini: bool, deterministic: bool = False) -> Any:
    """Dựng đúng handler của pipeline nhưng không chạy pipeline: chỉ cần chép."""
    from handlers.stt_whisper import DuckSTTHandler
    from pipeline import build_language_detector

    gemini_stt = None
    if with_gemini and cfg.gemini_api_key:
        from handlers.stt_gemini import GeminiAudioSTT

        gemini_stt = GeminiAudioSTT(api_key=cfg.gemini_api_key, model=cfg.gemini_model)

    stt = DuckSTTHandler.__new__(DuckSTTHandler)     # bỏ qua vòng đời thread
    stt.setup(
        model_name=cfg.stt_model,
        device="cpu",
        compute_type="int8",
        language=None,
        language_mode="auto",
        tracker=None,
        detect_language=build_language_detector(),
        vi_model_path=cfg.stt_model_vi,
        backend="phowhisper-reread",
        gemini_stt=gemini_stt,
        utt_dir=None,                                 # chấm lại thì đừng ghi thêm WAV
        # temperature=0 tắt dải fallback ngẫu nhiên của faster-whisper.
        gen_kwargs={"temperature": 0.0} if deterministic else None,
    )
    return stt


def build_candidate(cfg: Config, spec: dict[str, Any], deterministic: bool) -> tuple[Any, float]:
    """Handler riêng cho một ứng viên local. Trả (handler, RAM tăng thêm MB)."""
    from handlers.stt_whisper import DuckSTTHandler
    from pipeline import build_language_detector

    before = _rss_mb()
    stt = DuckSTTHandler.__new__(DuckSTTHandler)
    stt.setup(
        model_name=spec["model"] or cfg.stt_model,
        device="cpu",
        compute_type="int8",
        language=None,
        language_mode="auto",
        tracker=None,
        detect_language=build_language_detector(),
        vi_model_path=spec["vi_model"],
        backend=spec["backend"],
        gemini_stt=None,
        utt_dir=None,
        gen_kwargs={"temperature": 0.0} if deterministic else None,
    )
    return stt, round(_rss_mb() - before, 1)


def run(stt: Any, refs: list[dict[str, Any]], label: str, backend: str, mode: str) -> dict[str, Any]:
    stt.language_mode = mode
    # Lượt trước là nước cuối của _clean_language(); reset để điều kiện trước
    # không rò kết quả sang điều kiện sau.
    stt.last_language = None
    rows: list[dict[str, Any]] = []
    print(f"\n=== {label}  (backend={backend}, language_mode={mode}) ===")
    for index, ref in enumerate(refs, start=1):
        audio = read_wav(ref["wav"])
        started = time.perf_counter()
        heard = stt.transcribe_audio(audio, backend=backend)
        elapsed_ms = (time.perf_counter() - started) * 1000
        one = score(ref["text"], heard["text"])
        variants = {
            f"wer_{tag}": round(score(ref["text"], heard["text"], fn).wer, 4)
            for tag, fn in WER_VARIANTS
        }
        language_ok = heard["language"] == ref["lang"]
        rows.append({
            "index": index, "wav": ref["wav"].name,
            "reference": ref["text"], "reference_lang": ref["lang"],
            "hypothesis": heard["text"], "language": heard["language"],
            "language_p": heard.get("language_p"), "language_ok": language_ok,
            "model": heard["model"], "audio_s": round(len(audio) / 16000, 2),
            # `stt_fallback` = xin gemini-audio nhưng quá hạn 4 s nên Whisper chép thay.
            # Không ghi lại thì một dòng "gemini-audio" có thể thực ra là Whisper, và
            # cả bảng so backend lẫn lượt của backend kia mà không ai thấy.
            "stt_fallback": bool(heard.get("stt_fallback")),
            "stt_ms": round(elapsed_ms, 1), **one.as_dict(), **variants,
        })
        print(f"  {index:>3} [{ref['lang']}->{heard['language']}{'' if language_ok else ' SAI'}]"
              f" {elapsed_ms:>7.0f}ms  O={variants['wer_o']:>5.2f} N={variants['wer_n']:>5.2f}"
              f" D={variants['wer_d']:>5.2f}  {heard['text'][:44]}")

    all_pairs = [(r["reference"], r["hypothesis"]) for r in rows]
    by_lang: dict[str, Any] = {}
    for lang in ("vi", "en"):
        pairs = [(r["reference"], r["hypothesis"]) for r in rows if r["reference_lang"] == lang]
        if pairs:
            total = corpus_score(pairs)
            by_lang[lang] = {
                "wer": round(total.wer, 4), "cer": round(total.cer, 4), "n": len(pairs),
                **{f"wer_{tag}": round(corpus_score(pairs, fn).wer, 4)
                   for tag, fn in WER_VARIANTS},
            }
    total = corpus_score(all_pairs)
    # WER gộp toàn bộ: cộng dồn lỗi rồi chia tổng độ dài tham chiếu, KHÔNG lấy
    # trung bình WER từng câu (xem corpus_score) -- nên phải tính lại cho từng thước
    # chứ không lấy trung bình cột wer_o/wer_n/wer_d của các dòng.
    corpus_variants = {f"wer_{tag}": round(corpus_score(all_pairs, fn).wer, 4)
                       for tag, fn in WER_VARIANTS}
    ms = [r["stt_ms"] for r in rows]
    return {
        "backend": backend, "language_mode": mode,
        "wer": round(total.wer, 4), "cer": round(total.cer, 4), **corpus_variants,
        "by_lang": by_lang,
        "language_accuracy": round(sum(r["language_ok"] for r in rows) / len(rows), 3),
        "stt_p50": round(statistics.median(ms), 1), "stt_p95": round(_pct(ms, 0.95), 1),
        "utterances": rows,
    }


def _rank(results, key):
    """Thứ hạng backend theo một thước WER, thấp hơn = tốt hơn."""
    return [label for label, _ in sorted(results.items(), key=lambda kv: kv[1][key])]


def check_rank_change(results):
    """So thứ hạng giữa ba thước. Trả về danh sách cảnh báo (rỗng = không đổi).

    Đây là câu hỏi chặn của ADR-004. Vu et al. (EACL 2026) cho thấy thứ hạng ĐỔI
    ĐƯỢC giữa O-WER và N-WER trong chính bảng của họ: ChunkFormer thua
    PhoASR-3100h ở O-WER (32,43 vs 11,70) nhưng THẮNG ở N-WER (6,89 vs 8,20).
    Nếu thứ hạng backend của ta cũng đổi thì quyết định chọn `gemini-audio` phải
    xem lại.
    """
    tags = [tag for tag, _ in WER_VARIANTS]
    labels = list(results)
    warnings = []
    for i, a in enumerate(tags):
        for b in tags[i + 1:]:
            for x, y in itertools.combinations(labels, 2):
                wax, way = results[x][f"wer_{a}"], results[y][f"wer_{a}"]
                wbx, wby = results[x][f"wer_{b}"], results[y][f"wer_{b}"]
                if (wax < way) == (wbx < wby):
                    continue
                # HOÀ không phải hoán vị. Hai backend cách nhau dưới `TIE` ở thước
                # nguồn thì thứ tự giữa chúng vốn đã là ngẫu nhiên; báo nó như "đổi
                # thứ hạng" sẽ chôn ca thật giữa một đống báo động giả.
                kind = "HOÀ rồi tách" if abs(wax - way) < TIE else "HOÁN VỊ THẬT"
                warnings.append([
                    f"{kind} — {x}  vs  {y}   ({a.upper()}-WER -> {b.upper()}-WER)",
                    f"    {a.upper()}: {wax:.3f} vs {way:.3f}   (lệch {abs(wax - way):.3f})",
                    f"    {b.upper()}: {wbx:.3f} vs {wby:.3f}   (lệch {abs(wbx - wby):.3f})",
                ])
    return warnings


def report(results: dict[str, Any]) -> None:
    print()
    print()
    print("================ BẢNG TỔNG KẾT ================")
    print("O = O-WER (chữ thô)   N = N-WER (thường + bỏ dấu câu)   "
          "D = thước cũ của repo (N + số/tên)")
    print("Giao thức: Vu, Nguyen & Nguyen, Findings of ACL: EACL 2026, §5.1 — "
          "docs/benchmark/PROTOCOL.md")
    print()
    print(f"{'điều kiện':<26}{'đúng ngôn ngữ':>14}{'O-WER':>8}{'N-WER':>8}{'D-WER':>8}"
          f"{'O-N':>7}{'O/N':>6}{'CER':>7}{'t_stt p50':>11}{'RAM MB':>9}")
    for label, r in results.items():
        ram = f"{r['ram_mb']:>9.0f}" if r.get("ram_mb") else f"{'-':>9}"
        ratio = (r["wer_o"] / r["wer_n"]) if r["wer_n"] else float("inf")
        print(f"{label:<26}{r['language_accuracy'] * 100:>13.0f}%"
              f"{r['wer_o']:>8.3f}{r['wer_n']:>8.3f}{r['wer_d']:>8.3f}"
              f"{r['wer_o'] - r['wer_n']:>7.3f}{ratio:>6.1f}{r['cer']:>7.3f}"
              f"{r['stt_p50']:>11.0f}{ram}")

    print()
    print(f"{'điều kiện':<26}{'vi: O':>8}{'N':>8}{'D':>8}   {'en: O':>8}{'N':>8}{'D':>8}")
    for label, r in results.items():
        vi, en = r["by_lang"].get("vi", {}), r["by_lang"].get("en", {})
        cell = lambda d, k: f"{d[k]:>8.3f}" if k in d else f"{'-':>8}"  # noqa: E731
        print(f"{label:<26}{cell(vi, 'wer_o')}{cell(vi, 'wer_n')}{cell(vi, 'wer_d')}   "
              f"{cell(en, 'wer_o')}{cell(en, 'wer_n')}{cell(en, 'wer_d')}")

    print()
    print("---- Kiểm thứ hạng backend giữa ba thước ----")
    warnings = check_rank_change(results)
    print(f"  O-WER: {' < '.join(_rank(results, 'wer_o'))}")
    print(f"  N-WER: {' < '.join(_rank(results, 'wer_n'))}")
    print(f"  D-WER: {' < '.join(_rank(results, 'wer_d'))}")
    print()
    real = [w for w in warnings if w[0].startswith("HOÁN VỊ THẬT")]
    if not warnings:
        print("  Thứ hạng GIỮ NGUYÊN ở cả ba thước.")
        print("  -> khoảng cách giữa các backend KHÔNG quy về chuẩn hoá văn bản được.")
    else:
        if real:
            print("  >>> DỪNG VÀ BÁO CHỦ NHÂN — có hoán vị thật, ADR-004 phải xem lại.")
        else:
            print("  Chỉ có cặp HOÀ rồi tách, không có hoán vị thật. Vẫn đọc kỹ:")
        for warning in warnings:
            for line in warning:
                print(f"  {line}")

    print("\nCâu sai ngôn ngữ ở từng điều kiện:")
    for label, r in results.items():
        bad = [f"#{u['index']}({u['reference_lang']}->{u['language']})"
               for u in r["utterances"] if not u["language_ok"]]
        print(f"  {label:<26} {' '.join(bad) if bad else 'không có'}")

    print("\nCâu nào backend nào cứu được (WER = 0 ở đâu):")
    labels = list(results)
    for i in range(len(next(iter(results.values()))["utterances"])):
        cells = []
        for label in labels:
            u = results[label]["utterances"][i]
            cells.append(f"{label.split()[0][:9]:>10}={u['wer']:.2f}")
        first = results[labels[0]]["utterances"][i]
        print(f"  #{first['index']:>3} [{first['reference_lang']}] {' '.join(cells)}   {first['reference'][:34]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wav_dir", help="thư mục chứa các file .wav")
    parser.add_argument("--refs", default=None, help="báo cáo bài test 10 câu, hoặc {tên file: {text, lang}}")
    parser.add_argument("--prompts", action="store_true", help="ground truth = realvoice.SENTENCES")
    parser.add_argument("--repeat", type=int, default=1, help="số lần đọc mỗi câu khi --prompts")
    parser.add_argument("--order", choices=["block", "round"], default="block",
                        help="block (mặc định): mỗi câu N lần liên tiếp; round: lặp cả vòng")
    parser.add_argument("--no-gemini", action="store_true", help="bỏ gemini-audio (khỏi gọi API)")
    parser.add_argument("--local-candidates", action="store_true",
                        help="đo thêm PhoWhisper-small và large-v3-turbo (nạp thêm model)")
    parser.add_argument("--deterministic", action="store_true",
                        help="ghim temperature=0 để chạy lại ra đúng số cũ (xem docstring)")
    parser.add_argument("--out", default=None, help="ghi kết quả chi tiết ra JSON")
    args = parser.parse_args()

    enable_utf8_console()
    if not args.prompts and not args.refs:
        raise SystemExit("Cần --prompts hoặc --refs để biết người nói đã nói gì.")

    wavs = sorted(Path(args.wav_dir).glob("*.wav"))
    if not wavs:
        raise SystemExit(f"Không có file .wav nào trong {args.wav_dir}")
    refs = load_refs(wavs, args)
    print(f"{len(refs)} câu từ {args.wav_dir}")

    cfg = Config.load()
    conditions = [c for c in CONDITIONS if not (args.no_gemini and c[1] == "gemini-audio")]
    stt = build_stt(cfg, with_gemini=any(c[1] == "gemini-audio" for c in conditions),
                    deterministic=args.deterministic)
    if not args.deterministic:
        print("(temperature fallback ĐANG BẬT như pipeline thật — chạy lại có thể lệch ở "
              "câu quá ngắn; dùng --deterministic nếu cần số lặp lại được)")
    available = set(stt.available_backends())
    print("backend đã nạp:", sorted(available))

    results: dict[str, Any] = {}
    for label, backend, mode in conditions:
        if backend not in available:
            print(f"\n(bỏ qua {label}: backend '{backend}' chưa nạp được)")
            continue
        results[label] = run(stt, refs, label, backend, mode)

    if args.local_candidates:
        for spec in LOCAL_CANDIDATES:
            print(f"\n(đang nạp {spec['label']}...)")
            try:
                candidate, ram = build_candidate(cfg, spec, args.deterministic)
            except Exception as exc:
                print(f"  bỏ qua {spec['label']}: {type(exc).__name__}: {exc}")
                continue
            results[spec["label"]] = run(candidate, refs, spec["label"], spec["backend"], "auto")
            results[spec["label"]]["ram_mb"] = ram
            del candidate

    report(results)
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nChi tiết: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
