"""Số luồng nào là đúng cho máy 4 nhân vật lý / 8 luồng logic (docs/ADR-005).

    python scripts\\bench_threads.py

`pipeline._restore_torch_threads()` đang đặt `torch.set_num_threads(os.cpu_count())`
= 8 luồng LOGIC trên 4 nhân VẬT LÝ, và CTranslate2 (Whisper) lẫn ONNX Runtime
(VieNeu) mỗi cái còn tự mở một pool cỡ tương tự. SESSION-01 chỉ so 8 với 1, chưa
bao giờ so 8 với 4.

Bài đo: mỗi cấu hình chạy hai lần — máy rảnh, và máy có 2 luồng bận (xấp xỉ cái
trình duyệt làm khi console đang mở: AudioWorklet + canvas 60 fps + giải mã audio).
Cấu hình nào ít bị phạt nhất khi có tải mới là cấu hình đúng, chứ không phải cấu
hình nhanh nhất lúc rảnh.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))     # scripts/ không phải package

import numpy as np  # noqa: E402

from bench_contention import CpuLoad, speech_like  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402

REPEATS = 3
LOADS = (0, 2)


def median_ms(fn, repeats: int = REPEATS) -> float:
    times = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        times.append((time.perf_counter() - started) * 1000)
    return statistics.median(times)


def bench_whisper(cfg: Config, audio: np.ndarray, cpu_threads: int, repeats: int) -> dict[int, float]:
    """CTranslate2 nhận cpu_threads lúc dựng model, nên phải nạp lại cho từng cấu hình."""
    from faster_whisper import WhisperModel

    model = WhisperModel(cfg.stt_model, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    gen = {"language": None, "beam_size": 1, "task": "transcribe", "without_timestamps": True,
           "vad_filter": False, "condition_on_previous_text": False}

    def run() -> None:
        segments, _info = model.transcribe(audio, **gen)
        list(segments)                                  # transcribe() lười, phải duyệt mới chạy

    run()                                               # warm-up, đừng tính lần đầu
    result = {}
    for threads in LOADS:
        with CpuLoad(threads):
            result[threads] = median_ms(run, repeats)
    del model
    return result


def bench_vieneu(cfg: Config, threads_setting: int, repeats: int) -> dict[int, float]:
    """RTF của VieNeu; ONNX Runtime nhận số luồng lúc dựng."""
    from handlers.tts_vieneu import VieNeuEngine

    engine = VieNeuEngine(voice=cfg.tts_voice_vi, precision="fp32", blocksize=512, threads=threads_setting)
    text = "Quạc, em là Vịt đây ạ. Anh cần em giúp gì không ạ?"

    def rtf() -> float:
        started = time.perf_counter()
        samples = sum(len(chunk) for chunk in engine.stream(text))
        return (time.perf_counter() - started) / max(samples / 16000, 1e-3)

    rtf()
    result = {}
    for load in LOADS:
        with CpuLoad(load):
            result[load] = statistics.median([rtf() for _ in range(repeats)])
    del engine
    return result


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args()

    cfg = Config.load()
    physical = (os.cpu_count() or 4) // 2               # 4 nhân vật lý, 8 luồng logic
    logical = os.cpu_count() or 8
    print(f"nhân vật lý ~{physical}, luồng logic {logical}\n")

    audio = speech_like(2.0)
    print("1) Whisper base — CTranslate2 cpu_threads")
    print(f"   {'cpu_threads':>12}{'rảnh':>9}{'2 luồng bận':>14}{'phạt':>8}")
    for cpu_threads in (0, physical, logical):
        times = bench_whisper(cfg, audio, cpu_threads, args.repeats)
        label = f"{cpu_threads} (auto)" if cpu_threads == 0 else str(cpu_threads)
        print(f"   {label:>12}{times[0]:>9.0f}{times[2]:>14.0f}{times[2] / times[0]:>7.1f}x")

    print("\n2) VieNeu — số luồng của ONNX Runtime (RTF, >1,0 là tiếng đứt)")
    print(f"   {'threads':>12}{'rảnh':>9}{'2 luồng bận':>14}{'phạt':>8}")
    for threads in (0, physical, logical):
        rtfs = bench_vieneu(cfg, threads, args.repeats)
        label = f"{threads} (auto)" if threads == 0 else str(threads)
        print(f"   {label:>12}{rtfs[0]:>9.2f}{rtfs[2]:>14.2f}{rtfs[2] / rtfs[0]:>7.1f}x")

    print("\nĐọc bảng: chọn cấu hình có cột 'phạt' NHỎ NHẤT, không phải cột 'rảnh' nhỏ nhất —")
    print("lúc chạy thật thì trình duyệt luôn giành CPU, nên hình phạt mới là thứ người dùng nghe thấy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
