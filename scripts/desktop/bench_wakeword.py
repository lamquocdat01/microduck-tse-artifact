r"""Đo wake word bằng SỐ, không bằng cảm giác: phát cụm gọi qua loa rồi đếm log board.

    # 20 lần gọi, đếm số lần board bắt
    python scripts\bench_wakeword.py --phrase "Hi Ducky" --times 20 --log <monitor.log>

    # 10 phút im lặng, đếm báo động giả
    python scripts\bench_wakeword.py --silence-min 10 --log <monitor.log>

Tiêu chí nghiệm thu (prompt 09/09): **≥ 16/20 lần bắt** và **≤ 1 báo động giả /
10 phút**. Con số thứ hai quan trọng ngang cái thứ nhất — một wake word bắt tốt mà
tự kích hoạt liên tục thì tệ hơn là không có.

CÁCH ĐO VÀ GIỚI HẠN CỦA NÓ — đọc trước khi trích số:

Cụm gọi được tổng hợp bằng Kokoro rồi phát qua LOA LAPTOP, board nghe bằng mic của
nó. Đây KHÔNG thay thế được người nói thật:

- một giọng TTS duy nhất, không có biến thiên giữa người với người;
- đường loa->mic thêm một chặng méo mà giọng người trực tiếp không có;
- khoảng cách và hướng do chỗ đặt laptop quyết định, không phải chỗ người ngồi.

Nên số ra đây là **chặn dưới và để SO SÁNH các phương án với nhau**, trong cùng một
điều kiện. Nghiệm thu cuối vẫn phải do người nói. Ghi rõ điều này cạnh mọi bảng số.

Ngược lại, phần đếm báo động giả thì đo được đàng hoàng: nó chỉ cần board ngồi yên
trong phòng, không cần ai nói gì.

Bộ đếm đọc log của `esp_idf_monitor` đang chạy sẵn (mở ở cửa sổ khác, KHÔNG reset
board). Nó đếm theo mốc byte: ghi vị trí cuối file trước khi phát, rồi chỉ đọc phần
mới thêm — nên log cũ của lần chạy trước không lọt vào.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import enable_utf8_console

# Dòng board in ra khi bắt được, cho cả hai đường: WakeNet (afe_audio_engine.cc)
# và MultiNet (custom_wake_word.cc:192).
DETECT = re.compile(r"Wake word detected|Custom wake word detected", re.IGNORECASE)

# Bắt được là board RỜI `idle` và TẮT LUÔN bộ dò wake word suốt lượt thoại
# (`xEventGroupClearBits(event_group_, kWakeWordEnabled)` trong afe_audio_engine.cc).
# Không chờ nó quay về `idle` thì mọi lần gọi tiếp theo rơi vào lúc nó đang bận và
# bị đếm là TRƯỢT — đúng cái bẫy đã làm phép đo đầu tiên ra 1/6 thay vì số thật.
BACK_TO_IDLE = re.compile(r"StateMachine: State: .* -> idle", re.IGNORECASE)


def tail_new(path: Path, since: int) -> tuple[str, int]:
    """Phần log thêm vào sau mốc `since` byte, và mốc mới."""
    with path.open("rb") as handle:
        handle.seek(since)
        data = handle.read()
    return data.decode("utf-8", errors="replace"), since + len(data)


def dem(text: str) -> list[str]:
    return [line for line in text.splitlines() if DETECT.search(line)]


def noi(phrase: str, voice: str, times: int, gap: float, log: Path, warmup: float,
        idle_wait: float) -> int:
    """Phát `phrase` `times` lần qua loa, trả về số lần board bắt được."""
    import numpy as np
    import sounddevice as sd
    from kokoro import KPipeline

    print(f"Nạp Kokoro… (giọng {voice})")
    pipeline = KPipeline(lang_code="a")
    # Kokoro trả torch.Tensor, không phải ndarray — `.astype` không có ở đây.
    audio = np.concatenate([
        np.asarray(getattr(chunk, "cpu", lambda: chunk)(), dtype="float32")
        for _, _, chunk in pipeline(phrase, voice=voice)
    ])
    # Chuẩn hoá về cùng một đỉnh cho MỌI cụm gọi. Không làm thì cụm dài/ngắn ra
    # mức khác nhau và bảng so sánh giữa các phương án mất nghĩa — chênh lệch có
    # thể chỉ là chênh âm lượng.
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio * (0.95 / peak)
    duration = len(audio) / 24000
    print(f"Cụm gọi {phrase!r}: {duration:.2f} s, {len(audio)} mẫu @ 24 kHz, "
          f"đỉnh gốc {peak:.3f} -> 0.95")

    mark = log.stat().st_size if log.exists() else 0
    print(f"Bắt đầu từ mốc {mark} byte của {log.name}. Chờ {warmup:.0f} s cho board ổn định…")
    time.sleep(warmup)

    bat = 0
    for lan in range(1, times + 1):
        cho_idle(log, idle_wait)             # chỉ gọi khi board đang thật sự nghe
        truoc = log.stat().st_size if log.exists() else mark
        sd.play(audio, 24000)
        sd.wait()
        time.sleep(gap)                      # chờ board xử lý xong rồi mới xét
        moi, _ = tail_new(log, truoc)
        hit = dem(moi)
        if hit:
            bat += 1
        print(f"  lần {lan:>2}/{times}: {'BẮT' if hit else '   '}  "
              f"({bat}/{lan} tới giờ)" + (f"  {hit[0].strip()[:70]}" if hit else ""))
    return bat


def cho_idle(log: Path, timeout: float) -> None:
    """Chờ board quay về `idle`. Đã ở idle sẵn thì về ngay."""
    mark = log.stat().st_size if log.exists() else 0
    het = time.monotonic() + timeout
    ban = False
    while time.monotonic() < het:
        moi, _ = tail_new(log, mark)
        if BACK_TO_IDLE.search(moi):
            time.sleep(1.0)                  # cho bộ dò kịp bật lại
            return
        if not ban and not DETECT.search(moi):
            # Không thấy dấu hiệu board đang bận -> coi như nó vẫn đang nghe.
            return
        ban = True
        time.sleep(1.0)
    print("    (chờ quá lâu mà board chưa về idle — vẫn gọi tiếp)")


def im_lang(minutes: float, log: Path) -> list[str]:
    """Để board yên, trả về danh sách dòng báo động giả."""
    mark = log.stat().st_size if log.exists() else 0
    print(f"Ngồi im {minutes:.0f} phút, đếm báo động giả. ĐỪNG phát gì qua loa.")
    het = time.monotonic() + minutes * 60
    while time.monotonic() < het:
        time.sleep(15)
        con = (het - time.monotonic()) / 60
        moi, _ = tail_new(log, mark)
        print(f"  còn {con:>4.1f} phút — báo động giả tới giờ: {len(dem(moi))}")
    moi, _ = tail_new(log, mark)
    return dem(moi)


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True, help="file log của esp_idf_monitor đang chạy")
    parser.add_argument("--phrase", default=None, help="cụm gọi; bỏ trống thì chỉ đo báo động giả")
    parser.add_argument("--voice", default="am_michael", help="giọng Kokoro")
    parser.add_argument("--times", type=int, default=20)
    parser.add_argument("--gap", type=float, default=2.5, help="giây chờ sau mỗi lần phát")
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--idle-wait", type=float, default=45.0,
                        help="giây chờ board quay về idle giữa hai lần gọi")
    parser.add_argument("--silence-min", type=float, default=0.0, help="phút đo báo động giả")
    args = parser.parse_args()

    log = Path(args.log)
    if not log.exists():
        print(f"Chưa có {log}. Mở `esp_idf_monitor --no-reset` ghi vào file đó trước.")
        return 1

    if args.phrase:
        bat = noi(args.phrase, args.voice, args.times, args.gap, log, args.warmup,
                  args.idle_wait)
        dat = "ĐẠT" if bat >= 16 else "CHƯA ĐẠT"
        print(f"\nBẮT ĐƯỢC: {bat}/{args.times}   (mốc ≥16/20) → {dat}")
        print("Đây là giọng TTS qua loa laptop, KHÔNG thay được người nói thật — "
              "dùng để so các phương án với nhau, không để nghiệm thu cuối.")

    if args.silence_min > 0:
        gia = im_lang(args.silence_min, log)
        dat = "ĐẠT" if len(gia) <= 1 else "CHƯA ĐẠT"
        print(f"\nBÁO ĐỘNG GIẢ: {len(gia)} trong {args.silence_min:.0f} phút   "
              f"(mốc ≤1/10 phút) → {dat}")
        for line in gia:
            print(f"  {line.strip()[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
