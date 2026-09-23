r"""Chấm độ chính xác của nhãn `[lookup]`: vịt có nhận ra câu nào cần tra cứu không.

    python scripts\bench_lookup.py                       # chạy cả bộ, ghi jsonl
    python scripts\bench_lookup.py --out <file.jsonl>

Bộ câu gán nhãn TAY ở `CASES` bên dưới: `needs=True` là câu vịt không thể tự biết,
`needs=False` là câu nó biết chắc. Không lấy nhãn từ chính model — thế thì chấm cái
gì nữa.

Con số quan trọng nhất là **sai-âm**: câu CẦN tra mà vịt không đánh dấu, tức là nó
trả lời bừa. Sai-dương chỉ làm vịt tỏ ra dốt hơn thực tế, phiền nhưng không hại.

Mỗi câu chạy trên lịch sử RỖNG (`on_session_end()` giữa các câu): lịch sử kéo model
bắt chước chính nó (ADR-008), mà ở đây ta đo phản xạ với từng câu hỏi độc lập.

Đọc `lookup_flagged` ra từ `LatencyTracker` chứ không đoán theo lời thoại — đó đúng
là đường mà `latency.jsonl` dùng, nên bài đo này cũng là bài kiểm tầng log.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.persona import load_persona
from config import Config, enable_utf8_console
from handlers.llm_gemini import GeminiLLMHandler
from latency import LatencyTracker
from speech_to_speech.pipeline.messages import Transcription, TTSInput

REPO_DIR = Path(__file__).resolve().parents[2]

# (cần tra cứu?, ngôn ngữ, câu hỏi)
#
# Nhóm KHÔNG cần tra: giải thích khái niệm, lịch sử đã xong, toán, lập trình, dịch
# thuật — những thứ nằm trong trọng số của model và không đổi theo ngày.
# Nhóm CẦN tra: đổi theo thời gian (giá, lịch, hạn, thời tiết, tin) hoặc cụ thể và
# ít phổ biến (một trường, một công ty nhỏ, một người).
CASES: list[tuple[bool, str, str]] = [
    # -- 15 câu KHÔNG cần tra cứu ---------------------------------------------
    (False, "vi", "Em giải thích cho anh chồng chất lượng tử là gì đi."),
    (False, "vi", "Hai mũ mười bằng bao nhiêu?"),
    (False, "vi", "Vì sao bầu trời có màu xanh?"),
    (False, "vi", "Chiến dịch Điện Biên Phủ kết thúc năm nào?"),
    (False, "vi", "Trong Python thì list và tuple khác nhau chỗ nào?"),
    (False, "vi", "Dịch câu 'the early bird catches the worm' sang tiếng Việt giúp anh."),
    (False, "vi", "Nước sôi ở bao nhiêu độ C khi ở mực nước biển?"),
    (False, "vi", "Em kể cho anh nghe một câu chuyện cười ngắn đi."),
    (False, "vi", "Quang hợp là gì hả em?"),
    (False, "vi", "Anh nên học tiếng Anh thế nào cho hiệu quả?"),
    (False, "en", "What is the difference between TCP and UDP?"),
    (False, "en", "Who wrote Pride and Prejudice?"),
    (False, "en", "How do I reverse a string in Python?"),
    (False, "en", "Why do we have leap years?"),
    (False, "en", "Explain what an API is, simply."),

    # -- 15 câu CẦN tra cứu ----------------------------------------------------
    (True, "vi", "Năm nay Đại học Khoa học Tự nhiên tuyển sinh tiến sĩ thế nào em?"),
    (True, "vi", "Giá vàng SJC hôm nay bao nhiêu một lượng?"),
    (True, "vi", "Ngày mai Hà Nội có mưa không em?"),
    (True, "vi", "Hạn nộp hồ sơ học bổng của Đại học Bách khoa năm nay là ngày nào?"),
    (True, "vi", "Tuần rồi có tin gì đáng chú ý về AI không em?"),
    (True, "vi", "Vé máy bay Hà Nội – Đà Nẵng tuần sau khoảng bao nhiêu tiền?"),
    (True, "vi", "Công ty Suntory PepsiCo Việt Nam đang tuyển vị trí nào ở Hà Nội?"),
    (True, "vi", "Tỷ giá đô la Mỹ sang tiền Việt hôm nay là bao nhiêu?"),
    (True, "vi", "Trận Việt Nam đá tối qua tỉ số bao nhiêu em?"),
    (True, "vi", "Phiên bản mới nhất của Python bây giờ là bản nào?"),
    (True, "en", "What is the deadline for the Fulbright scholarship this year?"),
    (True, "en", "How much does a Tesla Model 3 cost right now?"),
    (True, "en", "What is the weather in Singapore tomorrow?"),
    (True, "en", "Who won the Champions League final this year?"),
    (True, "en", "Is the office of Kernelic Systems in Hanoi still hiring?"),
]


def run(out_path: Path, verbose: bool) -> int:
    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY trong ..\\.env")
        return 1

    tracker = LatencyTracker(path=out_path, echo=False,
                             defaults={"bench_set": "lookup_flag", "source": "bench_lookup"})
    handler = GeminiLLMHandler(
        threading.Event(),
        queue_in=queue.Queue(),
        queue_out=queue.Queue(),
        setup_kwargs={
            "api_key": cfg.gemini_api_key,
            "model": cfg.gemini_model,
            "system_prompt": load_persona(cfg.persona_path).system_prompt(),
            "tracker": tracker,
        },
    )

    rows = []
    for index, (needs, lang, text) in enumerate(CASES, start=1):
        handler.on_session_end()                 # lịch sử rỗng cho từng câu
        tracker.start_turn(bench_turn=index, spoken_lang=lang, user_text=text,
                           needs_lookup=needs)
        reply = " ".join(
            out.text for out in handler.process(Transcription(text=text, language_code=lang))
            if isinstance(out, TTSInput)
        )
        record = tracker.finish() or {}
        flagged = bool(record.get("lookup_flagged"))
        rows.append((needs, flagged, lang, text, reply))
        if verbose:
            mark = "OK " if needs == flagged else "SAI"
            print(f"{mark} [{lang}] cần={needs!s:<5} gắn={flagged!s:<5} {text[:50]}")
            print(f"      -> {reply[:110]}")

    dung_duong = sum(1 for n, f, *_ in rows if n and f)
    sai_duong = sum(1 for n, f, *_ in rows if not n and f)
    sai_am = sum(1 for n, f, *_ in rows if n and not f)
    dung_am = sum(1 for n, f, *_ in rows if not n and not f)

    precision = dung_duong / (dung_duong + sai_duong) if (dung_duong + sai_duong) else 0.0
    recall = dung_duong / (dung_duong + sai_am) if (dung_duong + sai_am) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print(f"\nBộ {len(rows)} câu — nhãn [lookup] so với nhãn tay\n")
    print("                     vịt GẮN nhãn   vịt KHÔNG gắn")
    print(f"  thật sự CẦN tra   {dung_duong:>12}   {sai_am:>13}")
    print(f"  KHÔNG cần tra     {sai_duong:>12}   {dung_am:>13}")
    print(f"\n  đúng-dương {dung_duong}   sai-dương {sai_duong}   "
          f"SAI-ÂM {sai_am}   đúng-âm {dung_am}")
    print(f"  precision {precision:.3f}   recall {recall:.3f}   F1 {f1:.3f}")
    print(f"\n  SAI-ÂM = câu cần tra mà vịt không nhận ra rồi trả lời bừa: {sai_am}/"
          f"{dung_duong + sai_am}")
    if sai_am:
        print("  Các câu bị bỏ sót:")
        for needs, flagged, lang, text, reply in rows:
            if needs and not flagged:
                print(f"    [{lang}] {text}")
                print(f"          -> {reply[:120]}")
    print(f"\nGhi {len(rows)} bản ghi vào {out_path}")
    return 0


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None, help="file jsonl đích")
    parser.add_argument("--quiet", action="store_true", help="không in từng câu")
    args = parser.parse_args()
    out = Path(args.out) if args.out else (
        REPO_DIR / "docs" / "benchmark" / f"lookup_flag_{date.today():%Y%m%d}_v1.jsonl")
    return run(out, verbose=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
