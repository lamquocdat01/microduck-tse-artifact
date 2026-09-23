r"""Đo và tổng kết latency của vòng thoại.

    python scripts\bench_latency.py                      # thống kê logs/latency.jsonl
    python scripts\bench_latency.py --run                 # chạy pipeline thật, không cần mic:
                                                          #   câu mẫu -> TTS -> PCM -> VAD -> STT -> LLM -> TTS
    python scripts\bench_latency.py --run --lang vi       # bộ câu tiếng Việt (M2)
    python scripts\bench_latency.py --last 20             # chỉ tính 20 lượt gần nhất
    python scripts\bench_latency.py --run --wav-dir logs\utts --refs refs.json
                                                          # phát lại WAV giọng thật qua ĐÚNG
                                                          # đường mic: WAV -> VAD -> STT -> ...
    python scripts\bench_latency.py --run --lang mail --turns 12
                                                          # 12 câu hỏi mail trên hộp thư GIẢ
                                                          # (ADR-014) -> docs/benchmark/MAIL-QA-<ngày>.md

Chế độ --run đi qua đúng các handler như lúc chạy thật, chỉ thay micro và loa
bằng hàng đợi, nên số đo so sánh được với lúc nói thật (trừ độ trễ driver audio).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, enable_utf8_console  # noqa: E402
from latency import MARKS, LatencyTracker, MarkingQueue  # noqa: E402

# (ngôn ngữ người nói, câu). Micro giả tổng hợp bằng đúng TTS của ngôn ngữ đó.
PROMPTS: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("en", "Hello duck, what is your name?"),
        ("en", "Can you remember that I like strong coffee in the morning?"),
        ("en", "What time do you think I should take a break?"),
        ("en", "Tell me one very short joke about ducks."),
        ("en", "Thanks, that was helpful."),
    ],
    "vi": [
        ("vi", "Chào em, em tên gì?"),
        ("vi", "Em nhớ giúp anh là anh thích cà phê đậm buổi sáng nhé."),
        ("vi", "Theo em thì mấy giờ anh nên nghỉ giải lao?"),
        ("vi", "Kể cho anh một câu đùa thật ngắn về vịt đi."),
        ("vi", "Cảm ơn em, vậy là ổn rồi."),
    ],
    # Tiêu chí M2: xen kẽ trong cùng một phiên, mỗi lượt phải trả lời đúng ngôn ngữ.
    "mix": [
        ("vi", "Chào em, em tên gì?"),
        ("en", "Can you also speak English?"),
        ("vi", "Anh thích cà phê đậm buổi sáng nhé."),
        ("en", "Tell me one very short joke about ducks."),
        ("vi", "Cảm ơn em, vậy là ổn rồi."),
    ],
}


AUDIO_OUT_TIMEOUT_S = 60.0     # chờ t_audio_out landing trước khi đóng sổ
TURN_PAUSE_S = 1.0             # nghỉ giữa hai lượt, cho giống người thật


class BenchTracker(LatencyTracker):
    """Không cho đóng sổ lượt trước khi t_audio_out kịp được đánh.

    Handler TTS gọi finish() ngay TRƯỚC khi yield AUDIO_RESPONSE_DONE, còn
    t_audio_out chỉ được đánh khi có ai đó rút chunk đầu khỏi hàng đợi loa.
    Ở v0 hai việc này đua nhau và bench thua 1/90 lượt (en lượt 26: có
    t_tts_first, mất t_audio_out, dù vẫn ra 103 chunk audio).

    Chờ NGOÀI lock: mark() cần đúng cái lock ấy, giữ lock mà chờ là deadlock.
    """

    def __init__(self, *args: Any, audio_out_timeout: float = AUDIO_OUT_TIMEOUT_S, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.audio_out_timeout = audio_out_timeout
        self._audio_out = threading.Event()
        self.late_marks = 0        # số lượt v0 đã thua cuộc đua này
        self.waited_ms = 0.0       # tổng thời gian finish() phải chờ

    def start_turn(self, *args: Any, **kwargs: Any) -> None:
        self._audio_out.clear()
        super().start_turn(*args, **kwargs)

    def mark(self, name: str, **info: Any) -> None:
        super().mark(name, **info)
        if name == "t_audio_out":
            with self._lock:
                landed = self._turn is not None and "t_audio_out" in self._turn.marks
            if landed:
                self._audio_out.set()

    def finish(self, **info: Any) -> dict[str, Any] | None:
        with self._lock:
            turn = self._turn
            # Chỉ đáng chờ khi TTS đã thật sự phát audio; lượt bị bỏ vì
            # transcript rỗng thì không có chunk nào để mà chờ.
            pending = (
                turn is not None
                and "t_audio_out" not in turn.marks
                and "t_tts_first" in turn.marks
            )
        if pending and "error" not in info:
            t0 = time.perf_counter()
            got = self._audio_out.wait(self.audio_out_timeout)
            self.waited_ms += (time.perf_counter() - t0) * 1000.0
            if got:
                self.late_marks += 1
            else:
                info.setdefault("error", f"t_audio_out không tới trong {self.audio_out_timeout:.0f} s")
        return super().finish(**info)


def _wait_turn_done(speaker: Any, record_written: Any, timeout: float = 60.0) -> None:
    """Chặn tới khi lượt thật sự khép lại.

    Hai điều kiện, thiếu một cái là chưa được bơm câu sau:
      (a) sentinel AUDIO_RESPONSE_DONE đã về  -> vịt nói xong
      (b) tracker.finish() đã ghi xong dòng log -> mốc của lượt đã chốt
    """
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if speaker.sentinel.is_set() and record_written.is_set():
            return
        time.sleep(0.02)
    if not speaker.sentinel.is_set():
        raise TimeoutError(f"quá {timeout:.0f} s không thấy AUDIO_RESPONSE_DONE ({speaker.chunks} chunk)")
    raise TimeoutError(f"quá {timeout:.0f} s tracker.finish() chưa ghi dòng nào")


class _Speaker(threading.Thread):
    """Đóng vai loa: rút liên tục khỏi hàng đợi, không chỉ trong vòng chờ của lượt.

    Rút ngay thì MarkingQueue đánh t_audio_out đúng lúc chunk đầu ra khỏi hàng
    đợi, thay vì để nó nằm im tới sau khi handler TTS đã finish().
    """

    def __init__(self, queue: Any) -> None:
        super().__init__(daemon=True)
        self._queue = queue
        self._stop = threading.Event()
        self.sentinel = threading.Event()
        self.chunks = 0

    def new_turn(self) -> None:
        self.sentinel.clear()
        self.chunks = 0

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except Exception:
                continue
            if isinstance(item, bytes):          # AUDIO_RESPONSE_DONE
                self.sentinel.set()
            else:
                self.chunks += 1

    def stop(self) -> None:
        self._stop.set()


def _count_records(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _append_error(path: Path, lang: str, index: int, text: str, reason: str) -> None:
    """Lượt hỏng vẫn phải để lại dấu vết: một dòng có "error", không có mốc nào."""
    record = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "source": "bench",
        "bench_set": lang,
        "bench_turn": index,
        "user_text": text,
        "error": reason,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  [LỖI] {reason}")


# Tầng = phần thời gian RIÊNG của một khâu, không phải mốc tích luỹ.
STAGES: dict[str, tuple[str, str | None]] = {
    "stt": ("t_stt", None),                    # từ lúc dứt lời tới khi có transcript
    "llm": ("t_llm_first", "t_stt"),           # transcript -> token/câu đầu
    "tts": ("t_tts_first", "t_llm_first"),     # câu đầu -> mẫu audio đầu
    "out": ("t_audio_out", "t_tts_first"),     # mẫu đầu -> chạm loa
}


def _pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def _med(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def _stage(records: list[dict], key: str) -> list[float]:
    """Thời gian riêng của một tầng (ms). Bỏ qua lượt thiếu mốc ở hai đầu."""
    end_mark, start_mark = STAGES[key]
    out: list[float] = []
    for r in records:
        if end_mark not in r or (start_mark is not None and start_mark not in r):
            continue
        out.append(float(r[end_mark]) - (float(r[start_mark]) if start_mark else 0.0))
    return sorted(out)


def _table(records: list[dict], title: str) -> None:
    """Một bảng mốc + một bảng tầng cho một nhóm lượt."""
    ok = [r for r in records if "error" not in r]
    bad = [r for r in records if "error" in r]
    span = f"  ({ok[0]['ts'][:19]} → {ok[-1]['ts'][:19]})" if ok else ""
    print(f"\n[{title}]  {len(records)} lượt, {len(bad)} lỗi{span}")

    print(f"{'mốc (tích luỹ)':<16}{'p50':>9}{'p95':>9}{'min':>9}{'max':>9}   (ms, từ lúc dứt lời)")
    for mark in (*MARKS[1:], "end_to_end_ms"):
        values = sorted(float(r[mark]) for r in ok if mark in r)
        if not values:
            continue
        print(
            f"{mark:<16}{_med(values):>9.0f}{_pct(values, 0.95):>9.0f}"
            f"{values[0]:>9.0f}{values[-1]:>9.0f}   n={len(values)}"
        )

    print(f"{'tầng (riêng)':<16}{'p50':>9}{'p95':>9}{'min':>9}{'max':>9}")
    for key in STAGES:
        values = _stage(ok, key)
        if not values:
            continue
        print(
            f"{key:<16}{_med(values):>9.0f}{_pct(values, 0.95):>9.0f}"
            f"{values[0]:>9.0f}{values[-1]:>9.0f}   n={len(values)}"
        )

    for r in bad:
        print(f"  LỖI lượt {r.get('bench_turn', '?')}: {r['error']}")


def _mix_vs_pure(records: list[dict]) -> None:
    """Hình phạt trộn ngôn ngữ nằm ở tầng nào: so cùng câu, bộ thuần vs bộ mix."""
    rows_printed = False
    for lang in ("vi", "en"):
        pure = [r for r in records if r.get("bench_set") == lang and "error" not in r]
        inmix = [r for r in records
                 if r.get("bench_set") == "mix" and r.get("stt_lang") == lang and "error" not in r]
        if not pure or not inmix:
            continue
        if not rows_printed:
            print("\nHình phạt trộn ngôn ngữ (p50 ms, thời gian RIÊNG từng tầng):")
            print(f"{'':<18}{'stt':>8}{'llm':>8}{'tts':>8}{'out':>8}{'e2e':>10}")
            rows_printed = True
        for label, rows in ((f"{lang} thuần", pure), (f"{lang} trong mix", inmix)):
            cells = "".join(f"{_med(_stage(rows, k)):>8.0f}" for k in STAGES)
            e2e = _med(sorted(float(r["end_to_end_ms"]) for r in rows if "end_to_end_ms" in r))
            print(f"{label:<18}{cells}{e2e:>10.0f}   n={len(rows)}")
        deltas = [_med(_stage(inmix, k)) - _med(_stage(pure, k)) for k in STAGES]
        de2e = (_med(sorted(float(r["end_to_end_ms"]) for r in inmix if "end_to_end_ms" in r))
                - _med(sorted(float(r["end_to_end_ms"]) for r in pure if "end_to_end_ms" in r)))
        print(f"{'  → chênh lệch':<18}" + "".join(f"{d:>+8.0f}" for d in deltas) + f"{de2e:>+10.0f}")
    if not rows_printed:
        print("\n(không đủ dữ liệu để so mix vs thuần)")


def _outliers(records: list[dict], title: str) -> list[dict]:
    """Lượt có end_to_end_ms > 3× trung vị của chính nhóm đó. Không xoá khỏi log."""
    e2e = [float(r["end_to_end_ms"]) for r in records if "end_to_end_ms" in r]
    if not e2e:
        return []
    limit = 3 * statistics.median(e2e)
    out = [r for r in records if float(r.get("end_to_end_ms", 0)) > limit]
    for r in out:
        print(f"  [{title}] lượt {r.get('bench_turn', '?')}: "
              f"{r['end_to_end_ms']:.0f} ms (> {limit:.0f})  {r.get('user_text', '')!r}")
    return out


def summarize(records: list[dict], last: int | None = None) -> None:
    if last:
        records = records[-last:]
    if not records:
        print("Chưa có lượt nào trong log.")
        return

    # Nhóm theo bộ câu, giữ thứ tự xuất hiện. Log cũ không có bench_set -> một nhóm.
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(str(r.get("bench_set", "(không rõ)")), []).append(r)

    for title, rows in groups.items():
        _table(rows, title)

    if len(groups) > 1:
        _table(records, "TẤT CẢ")
        _mix_vs_pure(records)

    print("\nOutlier (end_to_end_ms > 3× trung vị của bộ đó, GIỮ NGUYÊN trong log):")
    found = [r for title, rows in groups.items() for r in _outliers(rows, title)]
    if not found:
        print("  không có")

    thieu = [r for r in records if "error" not in r
             and not all(k in r for k in MARKS)]
    if thieu:
        print(f"\nLượt thiếu mốc (không phải lỗi): {len(thieu)}")
        for r in thieu:
            missing = [k for k in MARKS if k not in r]
            print(f"  [{r.get('bench_set')}] lượt {r.get('bench_turn')}: thiếu {', '.join(missing)}")

    langs = [(r.get("stt_lang"), r.get("reply_lang")) for r in records if r.get("stt_lang")]
    if langs:
        khop = sum(1 for heard, replied in langs if heard == replied)
        print(f"\nTrả lời đúng ngôn ngữ: {khop}/{len(langs)}")

    e2e = sorted(float(r["end_to_end_ms"]) for r in records if "end_to_end_ms" in r)
    if e2e:
        p50 = statistics.median(e2e)
        verdict = "ĐẠT" if p50 < 4000 else "CHƯA ĐẠT"
        print(f"\nTiêu chí M1: p50 end-to-end < 4000 ms → {p50:.0f} ms  {verdict}")


# Lịch sử tiếng Việt để nạp sẵn: bẫy ngôn ngữ của ADR-008. Vịt bám lịch sử mạnh
# hơn bám chỉ dẫn trong system prompt, nên bench chạy từ lịch sử RỖNG là bài dễ
# hơn hẳn lúc dùng thật — phiên 06/09 sai 13/15 câu tiếng Anh đúng vì chỗ này.
PRELOAD_VI: list[tuple[str, str]] = [
    ("Chào em, em tên gì?", "Em là Vịt, một robot vịt nhỏ 25 cm ạ!"),
    ("Anh tên là Đạt, làm ở Suntory PepsiCo.", "Em nhớ rồi ạ, anh Đạt làm ở Suntory PepsiCo."),
    ("Nhắc anh họp lúc ba giờ chiều thứ Sáu.", "Dạ, em đã ghi lại cuộc họp ba giờ chiều thứ Sáu ạ."),
    ("Theo em thì mấy giờ anh nên nghỉ giải lao?", "Em nghĩ khoảng mười giờ sáng là hợp lý ạ."),
    ("Cảm ơn em, vậy là ổn rồi.", "Dạ không có gì đâu ạ, anh cần gì cứ gọi em nhé!"),
]


def _load_replay(wav_dir: str, refs_path: str) -> tuple[list[tuple[str, str]], list[Any], list[str]]:
    """Đọc thư mục WAV + file refs -> (prompts, pcm, tên file), giữ thứ tự tên file.

    Đây là cách đo sạch nhất ta có: cùng một audio giọng NGƯỜI, đi qua ĐÚNG đường
    mic thật (kể cả VAD, để `t_vad_end` có nghĩa), chỉ khác là nguồn audio đến từ
    file thay vì micro. So với bench mic giả thì nó bỏ được cái dễ của giọng TTS;
    so với phiên nói thật thì nó lặp lại được.
    """
    from audio_wav import read_wav, to_int16

    wavs = sorted(Path(wav_dir).glob("*.wav"))
    if not wavs:
        raise SystemExit(f"Không có file .wav nào trong {wav_dir}")
    refs = json.loads(Path(refs_path).read_text(encoding="utf-8"))
    prompts: list[tuple[str, str]] = []
    voices: list[Any] = []
    names: list[str] = []
    for wav in wavs:
        row = refs.get(wav.name)
        if row is None:
            raise SystemExit(f"refs không có mục cho {wav.name} — ghép tay là chỗ dễ sai nhất")
        prompts.append((row["lang"], row["text"]))
        voices.append(to_int16(read_wav(wav)))
        names.append(wav.name)
    print(f"Phát lại {len(wavs)} file WAV từ {wav_dir}")
    return prompts, voices, names


def _preload_vi_history(duck: Any, turns: int) -> None:
    """Nhét sẵn `turns` lượt hội thoại tiếng Việt vào lịch sử của LLM."""
    from google.genai import types

    llm = duck.llm
    for user_text, duck_text in PRELOAD_VI[:turns]:
        llm.history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        llm.history.append(types.Content(role="model", parts=[types.Part(text=duck_text)]))
    print(f"Đã nạp sẵn {min(turns, len(PRELOAD_VI))} lượt lịch sử tiếng Việt "
          f"({len(llm.history)} content).")


def _mail_fixture_store(cfg: Config) -> Any:
    """Cache mail GIẢ cho `--lang mail`: fixture của test, dời về đúng hôm nay.

    Đặt ở thư mục tạm, KHÔNG ở logs/: cache chứa nguyên chuỗi mồi của fixture, còn logs/ là
    đúng chỗ luật riêng tư của ADR-014 đòi không có nội dung mail nào.
    """
    import tempfile
    from datetime import datetime, timezone

    from mail.editorial import EditorialRules
    from mail.fake import FakeGmail
    from mail.store import MailStore
    from mail.sync import MailSync

    now = datetime.now(timezone.utc)
    fake = FakeGmail.from_fixture(now=now)
    store = MailStore(Path(tempfile.mkdtemp(prefix="bench_mail_")) / "mail.sqlite", cfg.mail_tz)
    result = MailSync(store, lambda: fake, EditorialRules.load(cfg.mail_rules), tz_name=cfg.mail_tz,
                      clock=lambda: now).sync_once()
    print(f"Hộp thư giả: {result}")
    return store


def run_pipeline(cfg: Config, lang: str, turns: int, brain: bool = True, reflect: bool = True,
                 preload_vi: int = 0, save_utts: bool = False,
                 wav_dir: str | None = None, refs_path: str | None = None,
                 replies: dict[int, str] | None = None) -> list[dict]:
    """Chạy pipeline thật với micro giả: câu mẫu được tổng hợp rồi bơm vào queue VAD.

    `replies`: nếu truyền, lời vịt của từng lượt (theo `bench_turn`) được ghi vào đây — bộ
    `mail` cần nó để chấm, vì `duck_text` của lượt đọc mail không xuống latency.jsonl.
    """
    import numpy as np
    from speech_to_speech.utils.thread_manager import ThreadManager

    from pipeline import build_pipeline

    mail_store = _mail_fixture_store(cfg) if lang == "mail" else None
    brain_holder: dict[str, Any] = {}

    def capture_reply(user_text: str, duck_text: str, reply_lang: str) -> None:
        if replies is not None:
            replies[int(tracker.defaults.get("bench_turn") or 0)] = duck_text
        if brain_holder.get("brain") is not None:
            brain_holder["brain"].on_turn_end(user_text, duck_text, reply_lang)

    print("Đang nạp model...")
    # Tracker của bench thay cho tracker mặc định: cần finish() biết chờ mốc.
    replay = wav_dir is not None
    tracker = BenchTracker(
        path=cfg.latency_log,
        defaults=({"source": "replay", "bench_set": "replay"} if replay
                  else {"source": "bench", "bench_set": lang}),
    )
    duck = build_pipeline(
        cfg,
        tracker=tracker,
        log_latency=True,
        with_brain=brain,
        with_reflect=reflect,
        # Không lưu WAV: audio của bench là do chính TTS trong máy đọc PROMPTS ra,
        # dựng lại lúc nào cũng được. Để nó ghi thì `logs/utts/` lẫn giọng máy vào
        # giọng người, mà thư mục đó sinh ra để giữ giọng người. `--save-utts` bật
        # lại khi cần chính đoạn audio SAU VAD để soi một transcript lạ.
        utt_dir=(cfg.latency_log.parent / "utts_bench") if save_utts else None,
        # Bench không được làm bẩn ký ức thật của chủ nhân.
        memory_path=cfg.latency_log.parent / "bench_memory.v1.json",
        mail_store=mail_store,
        mail_tz=cfg.mail_tz,
        on_turn_end=capture_reply if replies is not None else None,
    )
    brain_holder["brain"] = duck.brain
    speaker_queue = MarkingQueue(duck.queues["speaker"], duck.tracker)
    names: list[str] = []
    if replay:
        prompts, voices, names = _load_replay(wav_dir, refs_path)
    else:
        # Bộ câu chỉ có 5 câu; lặp vòng cho đủ `turns` lượt (repeated measures).
        if lang == "mail":
            from mail_qa_set import prompts as mail_prompts

            base = mail_prompts()
        else:
            base = PROMPTS[lang]
        prompts = [base[i % len(base)] for i in range(turns)]

    if not replay:
        # Giọng "người dùng": tổng hợp trước khi chạy thread, gọi thẳng Kokoro gốc để
        # không đụng vào tracker của handler TTS trong pipeline.
        print(f"Tổng hợp {len(base)} câu mẫu làm micro giả ({lang}), dùng cho {turns} lượt...")
        tts_handler = duck.handlers[-1]
        unique_voices: list[np.ndarray] = []
        for prompt_lang, prompt in base:
            if prompt_lang == "vi":
                chunks = list(tts_handler.vieneu.stream(prompt))
            else:
                chunks = list(tts_handler._process_kokoro(prompt, "en"))
            unique_voices.append(np.concatenate(chunks).astype(np.int16))
        voices = [unique_voices[i % len(base)] for i in range(turns)]

    if preload_vi:
        _preload_vi_history(duck, preload_vi)

    manager = ThreadManager(duck.handlers)
    manager.start()
    duck.should_listen.set()

    # (b) của điều kiện bơm câu tiếp: finish() đã ghi xong dòng log.
    record_written = threading.Event()
    tracker.on_record = lambda record: record_written.set()

    speaker = _Speaker(speaker_queue)
    speaker.start()

    records: list[dict] = []
    try:
        for index, ((prompt_lang, text), spoken) in enumerate(zip(prompts, voices), 1):
            print(f"\n--- lượt {index}/{len(prompts)} ---")
            # Lượt nào của bộ nào: finish() đọc ra, không đụng field cũ.
            tracker.defaults["bench_turn"] = index
            # Ground truth: ở đây ta BIẾT người nói dùng thứ tiếng nào, vì chính
            # ta tổng hợp câu đó. `finish()` dùng nó để tách lỗi STT khỏi lỗi LLM
            # thay vì chấm `reply_lang` với `stt_lang` (xem latency._score_language).
            tracker.defaults["spoken_lang"] = prompt_lang
            if replay:
                # Câu mẫu đi cùng bản ghi -> latency._score_language() chấm luôn
                # WER/CER, khỏi ghép log với refs ở bước sau.
                tracker.defaults["wav"] = names[index - 1]
                tracker.defaults["ref"] = text
            before = _count_records(cfg.latency_log)
            speaker.new_turn()
            record_written.clear()
            try:
                pcm = np.concatenate([spoken, np.zeros(16000, dtype=np.int16)])   # 1 s im lặng để VAD chốt câu
                for start_i in range(0, len(pcm), 512):
                    block = pcm[start_i : start_i + 512]
                    if len(block) < 512:
                        block = np.pad(block, (0, 512 - len(block)))
                    duck.queues["mic"].put(block.tobytes())

                try:
                    _wait_turn_done(speaker, record_written)
                finally:
                    print(f"  ({speaker.chunks} chunk audio ~ {speaker.chunks * 512 / 16000:.1f}s)")
            except Exception as exc:
                # Không nuốt lỗi: chốt sổ lượt đang mở nếu có, không thì ghi thẳng
                # một dòng "error", rồi chạy tiếp lượt sau.
                reason = f"{type(exc).__name__}: {exc}"
                try:
                    tracker.finish(error=reason)
                except Exception:
                    pass
                if _count_records(cfg.latency_log) == before:
                    _append_error(cfg.latency_log, lang, index, text, reason)
                else:
                    print(f"  [LOI] {reason}")
            finally:
                duck.should_listen.set()
            time.sleep(TURN_PAUSE_S)      # nghỉ giữa hai lượt, cho giống người thật
    finally:
        speaker.stop()
        manager.stop()
        tracker.defaults.pop("bench_turn", None)
        tracker.defaults.pop("spoken_lang", None)
        if tracker.late_marks:
            print(f"\n[harness] {tracker.late_marks} lượt phải chờ t_audio_out "
                  f"(tổng {tracker.waited_ms:.0f} ms) — v0 sẽ mất các mốc này.")

    if cfg.latency_log.exists():
        records = [json.loads(line) for line in cfg.latency_log.read_text(encoding="utf-8").splitlines() if line]
        records = records[-len(prompts) :]
    return records


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="chạy pipeline với micro giả rồi tổng kết")
    parser.add_argument("--lang", choices=["en", "vi", "mix", "mail"], default="en",
                        help="bộ câu mẫu; `mail` = 12 câu hỏi mail trên hộp thư giả (ADR-014)")
    parser.add_argument("--turns", type=int, default=5, help="số lượt khi --run")
    parser.add_argument("--last", type=int, default=None, help="chỉ tính N lượt gần nhất trong log")
    parser.add_argument("--verbose", action="store_true", help="log INFO của các handler (xem RTF từng câu)")
    parser.add_argument("--no-brain", action="store_true", help="tắt persona/kiến thức/ký ức, chỉ đo phần thoại")
    parser.add_argument("--no-reflect", action="store_true", help="tắt vòng học sau mỗi lượt")
    parser.add_argument("--wav-dir", default=None,
                        help="phát lại WAV có sẵn thay cho micro giả (cần --refs)")
    parser.add_argument("--refs", default=None,
                        help="ánh xạ {tên file wav: {text, lang}} cho --wav-dir")
    parser.add_argument("--save-utts", action="store_true",
                        help="lưu audio SAU VAD vào logs/utts_bench (để soi transcript lạ)")
    parser.add_argument("--preload-vi", type=int, default=0, metavar="N",
                        help="nạp sẵn N lượt lịch sử TIẾNG VIỆT trước khi đo (bẫy ngôn ngữ, ADR-008)")
    args = parser.parse_args()
    if args.verbose:
        import logging

        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    cfg = Config.load()

    if args.wav_dir and not args.refs:
        raise SystemExit("--wav-dir cần --refs để biết mỗi file là câu nào")

    if args.run:
        replies: dict[int, str] | None = {} if args.lang == "mail" else None
        records = run_pipeline(cfg, args.lang, args.turns, brain=not args.no_brain, reflect=not args.no_reflect,
                               preload_vi=args.preload_vi, save_utts=args.save_utts,
                               wav_dir=args.wav_dir, refs_path=args.refs, replies=replies)
        if args.lang == "mail":
            from config import REPO_DIR
            from mail_qa_set import write_report

            first = records[0] if records else {}
            report = write_report(records, replies or {}, repo_dir=REPO_DIR, conditions={
                "LLM": f"{first.get('llm_model') or cfg.gemini_model}, temperature 0,8, thinking_budget 0",
                "STT": cfg.stt_backend,
                "tra cứu web (search_enabled)": first.get("search_enabled"),
                "cổng gác đầu ra + cắt lời đọc thư (mail_gate)": first.get("mail_gate"),
                "từ vựng mail trong prompt STT (mail_stt_vocab)": first.get("mail_stt_vocab"),
                "micro giả": "câu hỏi tổng hợp bằng TTS (VieNeu / Kokoro) rồi đi qua VAD -> STT thật",
                "lịch sử hội thoại": "LIÊN TỤC qua 12 lượt, không xoá giữa các câu (giống dùng thật)",
                "hộp thư": "fixture tests/fixtures/mail/inbox.json dời về hôm nay, giờ " + cfg.mail_tz,
                "reflect": "bật cho lượt thường; lượt đọc mail bị chặn (ADR-014 §5)",
            })
            print(f"\nBáo cáo mail: {report}")

    if not cfg.latency_log.exists():
        print(f"Chưa có {cfg.latency_log}. Chạy `python app.py` hoặc thêm --run.")
        return 1
    records = [json.loads(line) for line in cfg.latency_log.read_text(encoding="utf-8").splitlines() if line]
    summarize(records, last=args.turns if args.run else args.last)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
