r"""Loopback vật lý: mic thứ hai đo chặng mic → loa của board (việc 16).

    # cửa sổ 1
    python device_server.py --reply tone

    # cách chuẩn: điện thoại ghi âm đặt cạnh board (xem "Mic thứ hai" bên dưới)
    python scripts\bench_loopback.py --reps 12 --khong-thu     # laptop chỉ phát click
    python scripts\bench_loopback.py --wav-in ghi_am.wav       # rồi phân tích file

    # chỉ dùng khi có mic NGOÀI cắm vào laptop, không dùng mic tích hợp
    python scripts\bench_loopback.py --reps 12 --mic 5 --speaker 7

Đây là cách DUY NHẤT lấy được chặng cuối. `t_dev_ack` rỗng ở mọi lượt vì firmware
v2.3.0 không báo ngược "đã bắt đầu phát", nên mọi mốc phía server đều dừng ở lúc byte
rời server — phần Wi-Fi chiều xuống + board giải mã + I2S đẩy ra loa không đo được từ
xa, chỉ đo được bằng tai của một cái mic khác.

## Vì sao cách này không cần đồng bộ đồng hồ

**Một file ghi âm duy nhất chứa CẢ tiếng kích thích LẪN tiếng board đáp.** Khoảng cách
giữa hai đỉnh trong cùng một file chính là độ trễ vòng — đó là một HIỆU của hai mốc
đo trên cùng một đồng hồ, không phải hiệu của hai đồng hồ khác nhau. Nên không có sai
số đồng bộ nào để mà cãi. Đây là điểm mấu chốt của phương pháp.

Cùng lý lẽ đó cho phần trừ: `t_tx_first − t_rx_speech_first` cũng là một HIỆU, đo
trên đồng hồ của server. Cộng/trừ hai hiệu đo trên hai đồng hồ khác nhau vẫn hợp lệ —
chỉ cần hai đồng hồ chạy đúng NHỊP, mà thạch anh nào cũng đúng nhịp tới cỡ ppm.

## Mic thứ hai PHẢI là điện thoại, không dùng được mic laptop — đo rồi mới biết

Ý đầu tiên là dùng mic laptop cho tự động hoá được: một luồng `playrec` vừa phát click
vừa thu, lặp 12 lần chỉ tốn một lệnh. **Đo thì thấy nó hỏng**, và hỏng vì đúng cái
bệnh mà tài liệu này đang đo ở board.

Mic array của laptop (Intel Smart Sound) chạy **AEC tham chiếu vào chính loa laptop**.
Mà tiếng click lại phát ra từ loa laptop. Nên AEC học đường vọng rồi triệt tiêu đúng
cái đỉnh thứ nhất mà phép đo cần. Số đo trên chính máy này, một âm 440 Hz biên độ 0,7
phát liên tục 3 giây, đỉnh thu được theo từng nửa giây:

    0,0-0,5 s  0,199      1,0-1,5 s  0,008      2,0-2,5 s  0,068  (AEC học lại)
    0,5-1,0 s  0,076      1,5-2,0 s  0,0001     2,5-3,0 s  0,004

Hội tụ trong 1,5 giây, còn lại đúng nền nhiễu. Ở lượt lặp thứ hai trở đi thì không còn
đỉnh thứ nhất nữa. Mic mặc định (MME) còn tệ hơn: thu ra 0,000 ngay từ đầu.

Điểm trớ trêu đáng ghi vào bài: **phép đo sinh ra vì board KHÔNG có AEC lại bị chặn vì
laptop CÓ AEC.**

Nên đường chuẩn là `--wav-in`: điện thoại đặt cạnh board, ghi 48 kHz, laptop phát click.
AEC của laptop không đụng tới mic điện thoại, và tiếng loa board vốn không nằm trong
tín hiệu tham chiếu của bất kỳ AEC nào ở đây. `--reps` (chế độ playrec) giữ lại để đo
mic ngoài cắm vào laptop — mic ngoài không đi qua chuỗi xử lý của mic array.

Cái giá phải nói rõ dù thu bằng đường nào: đây không phải thiết bị đo chuẩn, nên số ra
là **chặn dưới**, dùng để so tương đối giữa các cấu hình chứ không phải giá trị tuyệt
đối. `--wav` giữ lại file thu để nghe lại khi số ra kỳ quặc.

## Kích thích là tiếng click, không phải giọng nói

Click có sườn lên sắc, định vị đỉnh chính xác tới vài ms. Giọng nói lên biên độ thoai
thoải qua cả trăm ms — sai số định vị lúc đó to ngang thứ đang đo.

## Cảnh báo: KHÔNG `--reply echo`, và `tone` cũng phải có `--cooldown-ms`

AEC chưa từng chạy trên board này (ES8311 không có kênh tham chiếu, ADR-013 §10.2).

`echo` phát lại đúng cái mic vừa nghe nên vòng lặp vừa tự nuôi vừa **lớn dần** — cấm
hẳn. `tone` **không lớn dần**, và tôi từng viết ở đây rằng nó "không có rủi ro đó".
**Sai.** Nó vẫn **tự kích hoạt lại**: tiếng loa vượt ngưỡng VAD của mic là đủ, không
cần khuếch đại. Đo 09/09: 20 click ra 48 lượt, chu kỳ 2–3 giây, `audio_ms` hằng số
780 ms.

Hệ quả trực tiếp cho script này: **phép ghép click↔lượt theo thứ tự sẽ sai** nếu board
tự kích hoạt. Chạy `device_server.py --reply tone --cooldown-ms 3000`, và nếu số lượt
ghi thêm khác số click thì bỏ cả mẻ.

## Đọc số ra sao

    Δ_vòng      hiệu hai đỉnh trong file thu — mic → server → loa, ĐỦ CẢ VÒNG
    Δ_server    t_tx_first − t_rx_speech_first, phần server tự ghi (cõng 700 ms
                SILENCE_END_MS mà VAD phải chờ)
    Δ_còn lại   Δ_vòng − Δ_server = chặng lên (mic + đóng khung + Wi-Fi lên)
                + chặng xuống (Wi-Fi xuống + giải mã + I2S + loa)
    chặng lên   ước lượng: nửa khung (30 ms) + rtt_p50/2
    chặng xuống Δ_còn lại − chặng lên  ← con số việc 16 cần

Báo p50/p95, không báo trung bình: n = 12 mà có một lượt Wi-Fi vấp là trung bình hỏng.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import enable_utf8_console

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
FLOOR_LOG = Path(__file__).resolve().parents[1] / "logs" / "device_floor.jsonl"

FS = 48_000                  # điện thoại lẫn laptop đều thu được; 1 mẫu = 20,8 µs
TONE_HZ = 880                # tone_frames() của device_server
CLICK_MS = 6                 # đủ ngắn để đỉnh sắc, đủ dài để board nghe thấy
CLICK_HP = 2_000             # tách click khỏi tone: click băng rộng, tone hẹp ở 880


def bang_click(reps: int, gap: float, dan: float, bien_do: float) -> np.ndarray:
    """Chuỗi phát: `dan` giây im lặng lấy nền, rồi `reps` tiếng click cách nhau `gap`.

    Click là một mẩu ồn trắng lọc thông cao, bọc trong đường bao dốc đứng — sườn lên
    trong một mẫu. Ồn trắng chứ không phải một tần số: một hình sin ngắn thì đỉnh của
    nó chính là đỉnh của sóng mang, và ta sẽ đo lệch đi tới nửa chu kỳ.
    """
    rng = np.random.default_rng(20260910)
    n_click = int(FS * CLICK_MS / 1000)
    b, a = sig.butter(4, CLICK_HP / (FS / 2), btype="high")
    click = sig.lfilter(b, a, rng.standard_normal(n_click))
    click *= np.linspace(1.0, 0.0, n_click) ** 2       # tắt dần, không kêu "bụp" đuôi
    click *= bien_do / np.abs(click).max()

    tong = int(FS * (dan + reps * gap))
    ra = np.zeros(tong, dtype=np.float32)
    moc = []
    for i in range(reps):
        at = int(FS * (dan + i * gap))
        ra[at:at + n_click] = click
        moc.append(at)
    return ra, moc


def bao_bang(x: np.ndarray, cua_so_ms: float) -> np.ndarray:
    """Đường bao năng lượng, cửa sổ trượt RMS."""
    n = max(1, int(FS * cua_so_ms / 1000))
    # fftconvolve chứ không phải np.convolve: file thu dài cả phút, nhân cửa sổ 960 mẫu
    # theo kiểu trực tiếp là ~10^9 phép tính và bài test mất hơn hai phút.
    binh_phuong = sig.fftconvolve(x.astype(np.float64) ** 2, np.ones(n) / n, mode="same")
    return np.sqrt(np.maximum(binh_phuong, 0.0))    # FFT có thể trả số âm cỡ 1e-18


def loc_dai(x: np.ndarray, thap: float, cao: float) -> np.ndarray:
    b, a = sig.butter(4, [thap / (FS / 2), cao / (FS / 2)], btype="band")
    return sig.lfilter(b, a, x)


def suon_len(bao: np.ndarray, tu: int, den: int, nguong: float,
             giu_ms: float) -> int | None:
    """Mẫu đầu tiên trong [tu, den) mà đường bao vượt ngưỡng và GIỮ được `giu_ms`.

    Bắt buộc phải giữ: click cũng có chút năng lượng rơi vào dải 880 Hz, nhưng nó tắt
    sau vài ms còn tone thì kêu 1,5 giây. Không có điều kiện giữ thì đỉnh thứ hai bị
    chấm trùng vào đỉnh thứ nhất và mọi số ra đều bằng 0 — sai một cách trông rất đẹp.
    """
    giu = int(FS * giu_ms / 1000)
    tren = bao[tu:den] > nguong
    if tren.size <= giu:
        return None
    # Cửa sổ trượt: chỉ nhận chỗ nào từ đó trở đi liên tục `giu` mẫu đều trên ngưỡng.
    dem = np.convolve(tren.astype(np.int32), np.ones(giu, dtype=np.int32), mode="valid")
    ung = np.flatnonzero(dem == giu)
    return None if ung.size == 0 else tu + int(ung[0])


def do_mot_luot(thu: np.ndarray, at_click: int, gap_n: int) -> dict:
    """Hai đỉnh của một lượt, tính bằng mẫu, trong cửa sổ của riêng lượt ấy."""
    # Cửa sổ tìm click: quanh chỗ ta ĐỊNH phát, nới ±200 ms cho độ trễ card âm thanh.
    lech = int(FS * 0.2)
    c0, c1 = max(0, at_click - lech), min(thu.size, at_click + lech)
    cao = np.abs(sig.lfilter(*sig.butter(4, CLICK_HP / (FS / 2), btype="high"), thu[c0:c1]))
    if not cao.size or cao.max() <= 0:
        return {"loi": "không thấy click"}
    i_click = c0 + int(np.argmax(cao))

    # Cửa sổ tìm tone: từ 80 ms sau click tới hết khoảng cách giữa hai lượt.
    t0 = i_click + int(FS * 0.08)
    t1 = min(thu.size, at_click + gap_n)
    if t1 - t0 < FS // 10:
        return {"loi": "cửa sổ tone quá ngắn"}
    dai = loc_dai(thu[t0:t1], TONE_HZ - 25, TONE_HZ + 25)
    bao = bao_bang(dai, 20.0)
    nen = float(np.median(bao[: int(FS * 0.05)])) if bao.size > FS // 20 else 0.0
    dinh = float(bao.max())
    if dinh < max(4 * nen, 1e-5):
        return {"loi": "không thấy tone 880 Hz", "dinh": dinh, "nen": nen}
    # Ngưỡng 25 % đỉnh: sườn lên của tone qua bộ lọc hẹp mất chừng 20 ms, lấy thấp
    # hơn nữa thì chấm vào đuôi lọc, lấy cao hơn thì chấm muộn vào giữa tone.
    i_tone = suon_len(bao, 0, bao.size, 0.25 * dinh, 50.0)
    if i_tone is None:
        return {"loi": "tone không giữ đủ 50 ms"}
    return {"i_click": i_click, "i_tone": t0 + i_tone,
            "delta_ms": round((t0 + i_tone - i_click) / FS * 1000.0, 1),
            "tone_snr": round(dinh / nen, 1) if nen > 0 else None}


def tim_cap_trong_file(thu: np.ndarray, gap: float) -> list[dict]:
    """Tìm các cặp (click, tone) trong một file thu sẵn, KHÔNG cần biết lịch phát.

    Đi ngược chiều với chế độ playrec: ở đó ta biết mình phát click lúc nào, ở đây thì
    không. Nên bám vào thứ KHÔNG thể nhầm — tràng tone 880 Hz dài 1,5 giây — rồi từ mỗi
    tràng ấy lần NGƯỢC về sau tối đa `gap` giây để tìm tiếng click gần nhất.

    Làm ngược lại (tìm click trước) thì hỏng: mọi tiếng động trong phòng đều là một
    đỉnh băng rộng, còn tràng 880 Hz giữ đủ 1,5 giây thì gần như không có gì giả được.
    """
    dai = loc_dai(thu, TONE_HZ - 25, TONE_HZ + 25)
    bao = bao_bang(dai, 20.0)
    if not bao.size:
        return []
    nguong = 0.25 * float(bao.max())
    giu = int(FS * 0.6)                    # tone thật dài 1,5 s; đòi giữ 0,6 s là đủ chặt
    tren = (bao > nguong).astype(np.int32)
    if tren.size <= giu:
        return []
    dem = np.round(sig.fftconvolve(tren, np.ones(giu), mode="valid")).astype(np.int64)
    ung = np.flatnonzero(dem == giu)
    if ung.size == 0:
        return []
    # Gom thành tràng theo CHỖ ĐỨT trong chính `ung`, không theo khoảng cách tới tràng
    # trước. Một tràng tone 1,5 s cho một dải chỉ số LIỀN NHAU dài 0,9 s; đo khoảng
    # cách tới mốc đầu thì mọi chỉ số cách nó hơn `giu` bị tính thành tràng mới, và
    # một tiếng tone hoá ra hai. Bài test bắt đúng lỗi này (6 cặp thay vì 3).
    dut = np.flatnonzero(np.diff(ung) > 1)
    dau_trang = [int(ung[0])] + [int(ung[i + 1]) for i in dut]

    b, a = sig.butter(4, CLICK_HP / (FS / 2), btype="high")
    cao = np.abs(sig.lfilter(b, a, thu))
    ra: list[dict] = []
    for i_tone in dau_trang:
        t0 = max(0, i_tone - int(FS * gap))
        cua_so = cao[t0:i_tone]
        if cua_so.size < FS // 100 or cua_so.max() <= 0:
            ra.append({"loi": "không thấy click trước tone"})
            continue
        i_click = t0 + int(np.argmax(cua_so))
        if i_tone - i_click < int(FS * 0.02):
            ra.append({"loi": "click và tone dính nhau — nghi phản xạ phòng"})
            continue
        ra.append({"i_click": i_click, "i_tone": i_tone,
                   "delta_ms": round((i_tone - i_click) / FS * 1000.0, 1),
                   "tone_snr": None})
    return ra


def doc_luot_moi(offset: int) -> list[dict]:
    """Các dòng device_floor.jsonl ghi thêm SAU mốc `offset` byte."""
    if not FLOOR_LOG.exists():
        return []
    with FLOOR_LOG.open("rb") as handle:
        handle.seek(offset)
        raw = handle.read().decode("utf-8", errors="replace")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def pxx(values: list[float], q: float) -> float | None:
    """Phân vị gần nhất, KHÔNG nội suy — n = 12 thì nội suy là bịa độ mịn."""
    if not values:
        return None
    xep = sorted(values)
    return xep[min(len(xep) - 1, max(0, round(q * (len(xep) - 1))))]


def bang(ten: str, values: list[float]) -> None:
    if not values:
        print(f"  {ten:<28} (không có lượt nào)")
        return
    print(f"  {ten:<28} n={len(values):<3} p50 {pxx(values, 0.5):7.1f}   "
          f"p95 {pxx(values, 0.95):7.1f}   min {min(values):7.1f}   max {max(values):7.1f}")


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reps", type=int, default=12, help="số lần lặp (>=10)")
    parser.add_argument("--gap", type=float, default=7.0,
                        help="giây giữa hai click; phải > 1,5 s tone + 0,7 s VAD + vòng")
    parser.add_argument("--lead", type=float, default=2.0, help="giây im lặng lấy nền")
    parser.add_argument("--amp", type=float, default=0.6, help="biên độ click, 0-1")
    parser.add_argument("--mic", default=None, help="thiết bị thu (số hoặc tên)")
    parser.add_argument("--speaker", default=None, help="thiết bị phát (số hoặc tên)")
    parser.add_argument("--wav", default=None, help="giữ file thu lại để nghe")
    parser.add_argument("--wav-in", default=None,
                        help="phân tích file ĐÃ thu sẵn (điện thoại) thay vì tự thu")
    parser.add_argument("--khong-thu", action="store_true",
                        help="chỉ phát click, không thu — dùng khi mic thứ hai là điện thoại")
    parser.add_argument("--floor-log", default=None,
                        help="đọc device_floor.jsonl từ mốc byte này (dùng với --wav-in)")
    parser.add_argument("--out", default=None)
    parser.add_argument("--note", default="", help="ghi kèm điều kiện đo (phòng, khoảng cách)")
    args = parser.parse_args()

    phat, moc = bang_click(args.reps, args.gap, args.lead, args.amp)
    duration = phat.size / FS
    print(f"Loopback vật lý: {args.reps} click, cách nhau {args.gap} s, tổng {duration:.0f} s")
    print("Board phải đang nối vào device_server.py --reply tone. KHÔNG dùng --reply echo.")

    def thiet_bi(v):
        if v is None:
            return None
        return int(v) if str(v).isdigit() else v

    offset = FLOOR_LOG.stat().st_size if FLOOR_LOG.exists() else 0
    if args.floor_log is not None:
        offset = int(args.floor_log)

    if args.wav_in:
        thu, fs_vao = sf.read(args.wav_in, dtype="float64", always_2d=True)
        thu = thu[:, 0]
        if fs_vao != FS:
            # Điện thoại hay ghi 44,1 kHz. Lấy mẫu lại về 48 kHz để mọi hằng số
            # trong file này vẫn đúng; sai số lấy mẫu lại nhỏ hơn một mẫu.
            thu = sig.resample_poly(thu, FS, fs_vao)
            print(f"Đọc {args.wav_in}: {fs_vao} Hz -> lấy mẫu lại về {FS} Hz")
        print(f"Đọc {thu.size / FS:.0f} s, đỉnh {np.abs(thu).max():.3f}")
        do = tim_cap_trong_file(thu, args.gap)
        print(f"Tìm thấy {len(do)} tràng tone 880 Hz trong file")
    elif args.khong_thu:
        sd.play(phat, samplerate=FS, blocking=True, device=thiet_bi(args.speaker))
        print("\nĐã phát xong chuỗi click. Dừng ghi âm trên điện thoại, chép file về,")
        print(f"rồi chạy lại:  python scripts\\bench_loopback.py --wav-in <file> "
              f"--floor-log {offset}")
        return 0
    else:
        thu = sd.playrec(phat, samplerate=FS, channels=1, blocking=True,
                         device=(thiet_bi(args.mic), thiet_bi(args.speaker)))
        thu = np.asarray(thu, dtype=np.float64).ravel()
        print(f"Thu xong {thu.size / FS:.0f} s, đỉnh {np.abs(thu).max():.3f}")
        if np.abs(thu).max() < 0.002:
            print("  !! Đường thu gần như im. Mic tích hợp của laptop có AEC tham chiếu"
                  " vào chính loa laptop\n     và nó triệt tiêu đúng tiếng click —"
                  " xem phần 'Mic thứ hai' ở đầu file. Dùng --wav-in.")
        gap_n = int(FS * args.gap)
        do = [do_mot_luot(thu, at, gap_n) for at in moc]

    if args.wav and not args.wav_in:
        sf.write(args.wav, thu.astype(np.float32), FS)
        print(f"Giữ file thu: {args.wav}")
    tot = [d for d in do if "loi" not in d]
    hong = [d for d in do if "loi" in d]
    print(f"Bắt được hai đỉnh ở {len(tot)}/{len(do)} lượt")
    for d in hong[:4]:
        print(f"  bỏ: {d['loi']}")

    luot = doc_luot_moi(offset)
    print(f"Server ghi thêm {len(luot)} lượt vào device_floor.jsonl")
    lech_mode = {r.get("reply_mode") for r in luot}
    if lech_mode and lech_mode != {"tone"}:
        print(f"  !! reply_mode = {lech_mode}, phải là 'tone' — số dưới đây KHÔNG dùng được")

    # Ghép theo THỨ TỰ: mỗi click sinh đúng một lượt, và cả hai danh sách đều theo
    # thời gian. Ghép theo mốc tuyệt đối thì phải đồng bộ đồng hồ — đúng cái phương
    # pháp này tránh. Lệch số lượng thì chỉ ghép được phần đầu, và nói ra.
    thua = [r for r in luot if r.get("cooldown")]
    if thua:
        print(f"  !! {len(thua)}/{len(luot)} lượt rơi vào cooldown — board ĐANG tự kích hoạt")
    if len(luot) != len(do):
        print(f"  !! {len(do)} click nhưng {len(luot)} lượt. Ghép theo thứ tự CHỈ đúng khi"
              f" mỗi click sinh đúng một lượt;\n     lệch số lượng nghĩa là board tự kích"
              f" hoạt xen vào, và phần chung cũng đã lệch pha.\n     BỎ CẢ MẺ, chạy lại"
              f" với --cooldown-ms 3000. Số dưới đây chỉ để chẩn đoán, KHÔNG dùng được.")

    rows = []
    for i, (d, r) in enumerate(zip(do, luot)):
        span = None
        if r.get("t_tx_first") is not None and r.get("t_rx_speech_first") is not None:
            span = round(r["t_tx_first"] - r["t_rx_speech_first"], 1)
        rtt = r.get("rtt_p50")
        len_uoc = round(30.0 + (rtt / 2 if rtt else 0.0), 1)   # nửa khung + nửa RTT
        row = {
            "rep": i, "ok": "loi" not in d, "loi": d.get("loi"),
            "delta_vong_ms": d.get("delta_ms"),
            "t_rx_speech_first": r.get("t_rx_speech_first"),
            "t_tx_first": r.get("t_tx_first"),
            "t_dev_vad_end": r.get("t_dev_vad_end"),
            "t_rx_first": r.get("t_rx_first"),
            "delta_server_ms": span,
            "rtt_p50": rtt, "jitter_ms": r.get("jitter_ms"),
            "len_uoc_ms": len_uoc,
            "tone_snr": d.get("tone_snr"),
            "session_id": r.get("session_id"), "ts": r.get("ts"),
        }
        if row["ok"] and span is not None and d.get("delta_ms") is not None:
            row["con_lai_ms"] = round(d["delta_ms"] - span, 1)
            row["xuong_ms"] = round(row["con_lai_ms"] - len_uoc, 1)
        rows.append(row)

    out = Path(args.out) if args.out else BENCH_DIR / f"loopback_es3c28p_{date.today():%Y%m%d}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({**row, "note": args.note}, ensure_ascii=False) + "\n")
    print(f"Ghi {len(rows)} bản ghi vào {out}\n")

    dung = [r for r in rows if r.get("xuong_ms") is not None]
    print(f"=== LOOPBACK VẬT LÝ (n={len(dung)}/{args.reps} lượt dùng được) ===")
    bang("Δ vòng (hai đỉnh)", [r["delta_vong_ms"] for r in dung])
    bang("Δ server (log)", [r["delta_server_ms"] for r in dung])
    bang("Δ còn lại (lên + xuống)", [r["con_lai_ms"] for r in dung])
    bang("chặng lên (ước lượng)", [r["len_uoc_ms"] for r in dung])
    bang("CHẶNG XUỐNG", [r["xuong_ms"] for r in dung])
    print("\n=== Bảng 2 của DEVICE-FLOOR (cùng mẻ lượt này) ===")
    bang("t_rx_first", [r["t_rx_first"] for r in rows if r.get("t_rx_first") is not None])
    bang("t_tx_first − t_dev_vad_end",
         [round(r["t_tx_first"] - r["t_dev_vad_end"], 1) for r in rows
          if r.get("t_tx_first") is not None and r.get("t_dev_vad_end") is not None])
    bang("jitter", [r["jitter_ms"] for r in rows if r.get("jitter_ms") is not None])
    bang("RTT p50", [r["rtt_p50"] for r in rows if r.get("rtt_p50") is not None])
    print("\nSố phân tán bất thường thì nghi TIẾNG VỌNG PHÒNG trước, đừng nghi board:"
          "\nđỉnh thứ hai lẫn phản xạ tường thì sườn lên nhoè và mốc chấm trôi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
