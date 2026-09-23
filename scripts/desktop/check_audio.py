r"""Kiểm tra mic/loa trước khi chạy vịt: liệt kê thiết bị, thu 3 giây, phát lại, in RMS.

    python scripts\check_audio.py                 # thiết bị mặc định của Windows
    python scripts\check_audio.py --list          # chỉ liệt kê rồi thoát
    python scripts\check_audio.py --input 1 --output 4 --seconds 5

Ghi tên thiết bị đã chọn vào AUDIO_INPUT_DEVICE / AUDIO_OUTPUT_DEVICE trong ..\.env.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

SAMPLE_RATE = 16000  # cùng tần số với VAD/Whisper trong pipeline


def list_devices() -> None:
    print(f"Host API mặc định: {sd.query_hostapis(sd.default.hostapi)['name']}")
    print(f"{'idx':>3}  {'in':>2} {'out':>3}  {'rate':>6}  tên")
    for idx, dev in enumerate(sd.query_devices()):
        mark = ""
        if idx == sd.default.device[0]:
            mark += " <- mic mặc định"
        if idx == sd.default.device[1]:
            mark += " <- loa mặc định"
        print(
            f"{idx:>3}  {dev['max_input_channels']:>2} {dev['max_output_channels']:>3}"
            f"  {int(dev['default_samplerate']):>6}  {dev['name']}{mark}"
        )


def level_report(audio: np.ndarray) -> float:
    """In RMS/peak và một thanh mức đơn giản. Trả về RMS."""
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    peak = float(np.max(np.abs(audio)))
    dbfs = 20 * np.log10(rms) if rms > 0 else -np.inf
    bars = int(min(rms, 0.5) / 0.5 * 40)
    print(f"RMS  = {rms:.4f} ({dbfs:6.1f} dBFS)  |{'#' * bars}{'.' * (40 - bars)}|")
    print(f"peak = {peak:.4f}")
    if peak >= 0.99:
        print("  ! Clipping — giảm mức mic trong Windows Sound.")
    return rms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="chỉ liệt kê thiết bị rồi thoát")
    parser.add_argument("--input", default=None, help="index hoặc một phần tên thiết bị thu")
    parser.add_argument("--output", default=None, help="index hoặc một phần tên thiết bị phát")
    parser.add_argument("--seconds", type=float, default=3.0, help="thời lượng thu, mặc định 3 s")
    args = parser.parse_args()
    enable_utf8_console()

    def as_device(value: str | None) -> int | str | None:
        if value is None:
            return None
        return int(value) if value.isdigit() else value

    list_devices()
    if args.list:
        return 0

    device_in, device_out = as_device(args.input), as_device(args.output)
    if device_in is not None:
        sd.default.device[0] = device_in
    if device_out is not None:
        sd.default.device[1] = device_out

    frames = int(args.seconds * SAMPLE_RATE)
    print(f"\nThu {args.seconds:g} giây ở {SAMPLE_RATE} Hz mono — nói gì đó vào mic...")
    try:
        recording = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device_in)
        sd.wait()
    except Exception as exc:  # thiết bị bận, sai index, driver không nhận 16 kHz...
        print(f"LỖI khi thu: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    audio = recording[:, 0]
    print("Xong. Mức tín hiệu thu được:")
    rms = level_report(audio)

    if rms < 0.002:
        print("  ! Gần như im lặng. Kiểm tra mic mặc định, quyền micro của Windows, hoặc chọn --input khác.")
    elif rms < 0.01:
        print("  ! Hơi nhỏ. VAD (ngưỡng 0.6) có thể bỏ sót; nói to hơn hoặc tăng mức mic.")

    print("\nPhát lại...")
    try:
        sd.play(audio, samplerate=SAMPLE_RATE, device=device_out)
        sd.wait()
    except Exception as exc:
        print(f"LỖI khi phát: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("Xong. Nghe rõ giọng mình vừa nói là mic/loa đã sẵn sàng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
