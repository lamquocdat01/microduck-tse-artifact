"""Vì sao STT chậm hơn khi nói bằng mic thật, và vì sao giọng bị bể (docs/ADR-005).

    python scripts\\bench_contention.py

Ba phép đo, không cần micro:

1. **STT có phụ thuộc độ dài câu không.** Whisper luôn đệm audio lên 30 giây trước
   khi mã hoá, nên giả thuyết "VAD cắt kèm im lặng nên chậm" chỉ đúng nếu thời gian
   chép TĂNG theo độ dài. Đo cùng một câu ở nhiều độ dài để biết.

2. **Tranh chấp CPU.** Bài nghiệm thu bơm WAV chạy trên máy rảnh; lúc nói thật thì
   trình duyệt cũng đang chạy AudioWorklet + canvas 60 fps trên cùng 4 nhân vật lý.
   Đo lại chính phép trên khi có N luồng bận để xem hình phạt bao nhiêu.

3. **TTS có kịp thời gian thực không.** Console phát audio theo đúng nhịp phát; nếu
   RTF của TTS vượt 1,0 thì tổng hợp chậm hơn phát, hàng đợi cạn và tiếng bị đứt.
   Đây là chỗ cần nhìn khi giọng bị bể, chứ không phải cỡ bộ đệm ở trình duyệt.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from config import Config, enable_utf8_console  # noqa: E402

REPEATS = 3
LENGTHS_S = (0.5, 1.0, 2.0, 4.0, 8.0)
LOADS = (0, 2, 4)


class CpuLoad:
    """N luồng quay vòng để giả tranh chấp CPU (trình duyệt, TTS lượt trước...)."""

    def __init__(self, threads: int) -> None:
        self.threads = threads
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []

    def __enter__(self) -> "CpuLoad":
        for _ in range(self.threads):
            worker = threading.Thread(target=self._spin, daemon=True)
            worker.start()
            self._workers.append(worker)
        if self.threads:
            time.sleep(0.3)                    # để tải kịp ổn định
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        for worker in self._workers:
            worker.join(timeout=2.0)

    def _spin(self) -> None:
        # numpy nhả GIL nên đây là tải CPU thật, không phải chỉ giữ GIL.
        block = np.random.rand(256, 256)
        while not self._stop.is_set():
            block @ block


def median_ms(fn, repeats: int = REPEATS) -> float:
    times = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        times.append((time.perf_counter() - started) * 1000)
    return statistics.median(times)


def speech_like(seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Tín hiệu giả giọng nói: formant + bao biên độ, đủ để Whisper chạy hết đường."""
    t = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
    tone = sum(np.sin(2 * np.pi * f * t) for f in (140, 420, 980))
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3.5 * t)
    return (tone / 3 * envelope * 0.3).astype(np.float32)


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args()

    cfg = Config.load()
    from pipeline import build_pipeline

    print("Đang nạp model...")
    duck = build_pipeline(cfg, with_brain=False, log_latency=False, with_bus=False, preload_all_stt=True)
    stt, tts = duck.stt, duck.tts

    print("\n1) STT có phụ thuộc độ dài câu không (backend base, máy rảnh)")
    print(f"   {'audio':>7}{'t_stt':>9}{'ms/giây audio':>16}")
    stt.set_language_mode("auto")
    for seconds in LENGTHS_S:
        audio = speech_like(seconds)
        elapsed = median_ms(lambda: stt.transcribe_audio(audio, backend="base"), args.repeats)
        print(f"   {seconds:>6.1f}s{elapsed:>9.0f}{elapsed / seconds:>16.0f}")

    print("\n2) Tranh chấp CPU (câu 2,0 giây)")
    audio = speech_like(2.0)
    print(f"   {'luồng bận':>10}{'base':>9}{'phowhisper-reread':>20}{'phạt':>8}")
    baseline = None
    for threads in LOADS:
        with CpuLoad(threads):
            one = median_ms(lambda: stt.transcribe_audio(audio, backend="base"), args.repeats)
            two = median_ms(lambda: stt.transcribe_audio(audio, backend="phowhisper-reread"), args.repeats)
        baseline = baseline or one
        print(f"   {threads:>10}{one:>9.0f}{two:>20.0f}{one / baseline:>7.1f}x")

    print("\n3) TTS có kịp thời gian thực không (RTF > 1,0 là tiếng sẽ đứt)")
    vi_text = "Quạc, em là Vịt đây ạ. Anh cần em giúp gì không ạ?"
    en_text = "Quack, hello there. How can I help you today?"
    print(f"   {'luồng bận':>10}{'VieNeu RTF':>12}{'Kokoro RTF':>12}")
    for threads in LOADS:
        with CpuLoad(threads):
            rtfs = []
            for engine, text in ((tts.vieneu, vi_text), (None, en_text)):
                started = time.perf_counter()
                if engine is not None:
                    samples = sum(len(c) for c in engine.stream(text))
                else:
                    from speech_to_speech.pipeline.messages import TTSInput

                    samples = sum(len(c) for c in tts.process(TTSInput(text=text, language_code="en")))
                elapsed = time.perf_counter() - started
                rtfs.append(elapsed / max(samples / 16000, 1e-3))
        flag = "  <- tiếng sẽ đứt" if max(rtfs) > 1.0 else ""
        print(f"   {threads:>10}{rtfs[0]:>12.2f}{rtfs[1]:>12.2f}{flag}")

    print("\nĐọc bảng: (1) ms/giây audio giảm mạnh khi câu dài ra nghĩa là chi phí gần như")
    print("cố định — Whisper đệm lên 30 s, nên độ dài câu KHÔNG phải nguyên nhân.")
    print("(2) cột 'phạt' là hình phạt tranh chấp CPU. (3) RTF > 1,0 là TTS không kịp phát.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
