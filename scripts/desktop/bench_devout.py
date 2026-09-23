r"""Chặng XUỐNG của thiết bị: byte rời server -> Wi-Fi -> board giải mã -> I2S -> loa.

    # cửa sổ 1: server thoại thật
    python device_server.py --reply pipeline --advertise 192.168.137.1 \
        --latency-log ..\docs\benchmark\latency_es3c28p_20260910_v1.jsonl

    # cửa sổ 2: phát 10 câu bài test qua loa laptop, mic laptop thu cả buổi
    python scripts\bench_devout.py chay --out logs\devout_20260910

    # sau đó, không cần board nữa
    python scripts\bench_devout.py doc --dir logs\devout_20260910

Đây là ô "mic -> loa" mà `DEVICE-FLOOR.md` bảng 2 và bảng 3 còn để trống. `t_dev_ack`
rỗng ở mọi lượt vì firmware v2.3.0 không gửi ngược "đã bắt đầu phát", nên chặng cuối
không đo được từ xa — chỉ đo được bằng tai của một cái mic khác.

## Vì sao mic LAPTOP dùng được ở đây, trong khi §B nói là không

`bench_loopback.py` kết luận "mic laptop không dùng được" và kết luận ấy ĐÚNG **cho
phép đo của nó**: ở đó tiếng kích thích phát ra từ **loa laptop**, mà AEC của mic array
(Intel Smart Sound) lấy đúng loa laptop làm tín hiệu tham chiếu — nên nó triệt tiêu
đúng cái đỉnh thứ nhất mà phép đo cần.

Phép đo này khác ở chỗ **cái cần nghe là loa BOARD**, không phải loa laptop. Loa board
không nằm trong tín hiệu tham chiếu của bất kỳ AEC nào trên máy này, nên nó đi qua
nguyên vẹn.

Nhưng phép (b) dưới đây VẪN cần nghe được tiếng click của chính laptop, và AEC vẫn ăn
mất nó — đo lại 10/09 ở chế độ shared: tỉ số đỉnh/nền của click chỉ còn 17 lần, trong
khi để chấm mốc cho ra hồn thì cần vài trăm. **Đường vòng: mở mic ở WASAPI EXCLUSIVE.**
Chế độ độc quyền đi thẳng vào endpoint, không qua chuỗi APO của Windows — mà AEC/khử ồn
của Intel Smart Sound chính là một APO. Đo trên máy này: exclusive mở được ở **4 kênh
48 kHz** (1 kênh và 2 kênh đều bị từ chối, 16 kHz cũng vậy), độ trễ khai báo 10,7 ms
thay vì 22 ms.

Nên kết luận "mic laptop không dùng được" của `bench_loopback.py` cần một dòng đính
chính: nó đúng cho **chế độ shared**, mà shared là mặc định của mọi thư viện âm thanh,
nên nó đúng cho tới khi có ai đi mở exclusive. Không phải mic hỏng — là đường đi tới
mic có một bộ lọc mà ứng dụng không gọi và cũng không tắt được từ bên trong.

## Hai phép đo, hai mốc "bắt đầu" khác nhau, chạy trên CÙNG một file thu

**(a) mốc của server** — `tx_first_perf_ms` trong `device_floor.jsonl`:

        Δ_a = (lúc mic laptop nghe thấy loa board) − (lúc byte Opus đầu rời server)

  Trên Windows `time.perf_counter()` là QueryPerformanceCounter, chung gốc cho MỌI
  tiến trình (đo trên chính máy này: ba tiến trình lệch < 1 ms). Nên tuy máy ghi âm và
  server là hai tiến trình, đây vẫn là một HIỆU trên MỘT đồng hồ. Cái nó cõng thêm là
  **độ trễ đường thu của laptop** `m` — từ lúc không khí rung tới lúc mẫu mang dấu thời
  gian: xem "m đo được, không phải đoán" bên dưới.

**(b) hai đỉnh trong file thu** — đúng §B của `PROTOCOL.md`:

        Δ_vòng   = (nghe thấy loa board) − (nghe thấy tiếng click của ta)
        Δ_server = t_tx_first − t_rx_speech_first          (đồng hồ server)
        Δ_còn    = Δ_vòng − Δ_server                       (chặng lên + chặng xuống)
        chặng lên ≈ nửa khung Opus (30 ms) + rtt_p50/2
        chặng xuống(b) = Δ_còn − chặng lên

  Ở đây `m` **tự triệt tiêu**: cả hai đỉnh đều đi qua cùng đường thu ấy.

## m đo được, không phải đoán — và đó là món quà của việc chạy cả hai

Cả hai phép trên cùng đo một thứ, chỉ khác chỗ `m`:

        Δ_a − chặng xuống(b) = m + (sai số của ước lượng "chặng lên")

Nên chạy cả hai không phải là làm hai lần cho chắc: **hiệu của chúng là một phép đo
độc lập cho độ trễ đường thu của laptop**, thứ mà cách (a) một mình chỉ có thể đi mượn
từ con số danh nghĩa của driver. Hai số lệch nhau nhiều hơn `m` hợp lý (≈ 2–30 ms theo
WASAPI khai báo) thì có gì đó sai, và phải nói ra chứ đừng chọn số đẹp hơn.

## Ghép lượt thu với lượt log: ghép theo ĐỒNG HỒ, không theo thứ tự

§B ghép theo thứ tự và tự ghi lại rằng phép ghép ấy đã sai một lần: board tự kích hoạt,
20 click đẻ ra 48 lượt, và bảng số ra "trông hoàn toàn bình thường và sai từ dòng đầu".

Có `opened_at_perf_ms` rồi thì không cần ghép theo thứ tự nữa. Mỗi lượt trong
`device_floor.jsonl` có mốc TUYỆT ĐỐI của byte đầu rời server; đỉnh nào trong file thu
là của lượt ấy thì phải nằm SAU mốc ấy và trước mốc của lượt kế. Lượt thừa do board tự
kích hoạt vẫn hiện ra, nhưng chúng không còn làm lệch pha cả mẻ — chúng chỉ là những
lượt không ghép được với đỉnh nào, và ta đếm chúng ra thành một con số riêng.

## Số ra là CHẶN DƯỚI

Không có dao động ký thì không được phát biểu như thể có. Khử ồn của Windows có thể
NUỐT đỉnh, không thể DỜI nó sớm lên — nên sai số nghiêng về phía làm số xấu đi.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import enable_utf8_console

DESKTOP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DESKTOP_DIR.parent
FLOOR_LOG = DESKTOP_DIR / "logs" / "device_floor.jsonl"
REFS = REPO_DIR / "docs" / "baseline" / "realvoice_2026-09-06_v2_refs.json"
UTTS_DIR = DESKTOP_DIR / "logs" / "utts"

FS = 48_000
CLICK_MS = 6
CLICK_HP = 2_000
# click -> câu nói. Đặt 0,05 s chứ không phải 0,25 s, và lý do là một phép đo:
# VAD của pipeline chốt câu sau **250 ms** im lặng (`pipeline.py`, `min_silence_ms`),
# nên một quãng lặng 250 ms giữa click và câu nói làm VAD cắt ngay tại đó — click
# thành một "câu" riêng, và mốc `rx_speech_first` của server rơi vào câu ấy chứ không
# phải câu ta muốn. Để 50 ms thì click và tiếng nói nằm trong CÙNG một khung Opus
# 60 ms: server chỉ có thể đánh mốc theo khung, nên hai bên chấm vào đúng một sự kiện.
#
# Cái giá phải ghi vào threat-to-validity: mốc phía server bị **lượng tử hoá 60 ms**
# bởi chính độ dài khung. Nó không lệch trung bình (khung nào cũng có thể chứa click
# ở bất kỳ đâu trong 60 ms ấy), nhưng nó cộng vào phương sai — và 60 ms là một khoản
# lớn so với thứ đang đo.
CLICK_GAP_S = 0.05

# Lần thu đầu của mỗi câu trong bộ 31 lượt giọng CHỦ NHÂN ngày 06/09. Dùng lại đúng
# bộ audio của bảng WER desktop: cùng tiếng nói, cùng câu, nên số của board so thẳng
# được với baseline v3 mà không phải cãi nhau về "giọng khác thì khác".
LAN_DAU = ["001", "004", "007", "010", "013", "016", "020", "023", "026", "029"]


# -- phần thu ---------------------------------------------------------------


@dataclass
class MayGhiAm:
    """Mic laptop chạy suốt buổi, giữ đủ mốc để quy chỉ số mẫu về `perf_counter`.

    Giữ CẢ HAI trục thời gian của PortAudio thay vì chọn sẵn một cái:

    - `inputBufferAdcTime` — PortAudio tự trừ độ trễ đường thu nó KHAI BÁO;
    - `perf_counter` lúc callback chạy — mốc đến tay ta, muộn hơn ADC đúng bằng
      độ trễ ấy.

    Hai trục lệch nhau đúng bằng thứ ta không chắc, nên ghi cả hai rồi để `doc` quyết
    định; chọn sẵn ở đây là chôn mất một giả định vào dữ liệu thô.
    """

    device: int | None = None
    doc_quyen: bool = True
    khoi: list[np.ndarray] = field(default_factory=list)
    moc: list[dict] = field(default_factory=list)
    kenh: int = 0
    che_do: str = ""
    _stream: sd.InputStream | None = None
    _tong: int = 0

    def _callback(self, indata, frames, time_info, status) -> None:
        perf = time.perf_counter()
        if status:
            self.moc.append({"canh_bao": str(status), "mau": self._tong})
        self.khoi.append(indata.copy())
        self.moc.append({
            "mau": self._tong,
            "adc": float(time_info.inputBufferAdcTime),
            "hien_tai": float(time_info.currentTime),
            "perf": perf,
        })
        self._tong += frames

    def bat_dau(self) -> None:
        """Thử exclusive trước, shared sau — và NÓI RA nó rơi xuống đường nào.

        Rơi xuống shared thì AEC bật lại, đỉnh click chìm mất: lúc ấy phép (b) hỏng
        còn phép (a) vẫn chạy. Đó là một thay đổi về Ý NGHĨA của số ra, nên nó phải
        hiện lên màn hình và nằm trong meta.json, không được lặng lẽ.
        """
        loi = []
        if self.doc_quyen:
            for so_kenh in (4, 2, 1):
                try:
                    self._mo(so_kenh, sd.WasapiSettings(exclusive=True))
                    self.kenh, self.che_do = so_kenh, "exclusive"
                    print(f"  mic: WASAPI EXCLUSIVE, {so_kenh} kenh — APO (ke ca AEC) "
                          f"khong chen vao duong thu.")
                    return
                except Exception as e:                       # noqa: BLE001
                    loi.append(f"exclusive {so_kenh}ch: {e}")
        self._mo(1, sd.WasapiSettings(auto_convert=True))
        self.kenh, self.che_do = 1, "shared"
        print("  mic: WASAPI SHARED — ! AEC CON TRONG DUONG THU, dinh click co the "
              "bi nuot, phep (b) se khong dung duoc.")
        for d in loi:
            print(f"     ({d})")

    def _mo(self, so_kenh: int, extra) -> None:
        self._stream = sd.InputStream(
            device=self.device, channels=so_kenh, samplerate=FS, dtype="float32",
            blocksize=0, callback=self._callback, extra_settings=extra,
        )
        self._stream.start()

    def muc_gan_day(self, giay: float) -> float:
        """RMS của chừng `giay` cuối cùng đã thu. Dùng để biết loa board im chưa."""
        can = int(FS * giay)
        lay, n = [], 0
        for khoi in reversed(self.khoi):
            lay.append(khoi)
            n += len(khoi)
            if n >= can:
                break
        if not lay:
            return 0.0
        x = np.concatenate(lay[::-1])[-can:]
        if x.ndim > 1:
            x = x[:, 0]
        # Lọc về đúng dải giọng nói TRƯỚC khi lấy RMS. Đo 10/09: RMS băng rộng của
        # phòng im là 0,0031, còn RMS trong dải 300–3400 Hz của cùng đoạn ấy chỉ
        # 0,00044 — chênh 7 lần, toàn bộ là ù tần số thấp mà mic array raw thu được.
        # Lấy ngưỡng "đã im" trên số băng rộng thì nó nằm CAO HƠN cả tiếng loa board,
        # và vòng chờ tuyên bố "im rồi" ngay lập tức: mẻ đầu 10/09 chờ đúng 8,0 s ở
        # cả 10 câu, tức là không chờ gì cả.
        return float(np.sqrt((loc_dai(x.astype(np.float64), 300.0, 3400.0) ** 2).mean()))

    def dung(self) -> tuple[np.ndarray, dict]:
        assert self._stream is not None
        do_tre = float(self._stream.latency)
        self._stream.stop()
        self._stream.close()
        thu = (np.concatenate(self.khoi) if self.khoi
               else np.zeros((0, max(1, self.kenh)), dtype=np.float32))
        return thu, {"do_tre_khai_bao_s": do_tre, "moc": self.moc, "fs": FS,
                     "so_kenh": self.kenh, "che_do": self.che_do}


@dataclass
class MayPhat:
    """Loa laptop mở MỘT lần cho cả buổi, và biết chính xác mẫu nào ra loa lúc nào.

    `sd.play()` mở stream mới mỗi lần gọi, và trên máy này lần mở ấy tốn tới **870 ms**
    trước khi tiếng thật sự ra loa (đo 10/09: gọi ở mẫu 46 008, tiếng ra quanh mẫu
    100 800). Với phép đo lấy mốc bằng ms thì mở stream mỗi lượt là tự chuốc lấy một
    biến ngẫu nhiên gần một giây, và cửa sổ đi tìm đỉnh phải nới rộng tới mức bắt nhầm
    cả tiếng động khác.

    Một stream chạy suốt buổi, dữ liệu đẩy qua hàng đợi: mốc DAC của PortAudio nói mẫu
    đầu của kích thích chạm loa lúc nào, trên cùng trục `perf_counter`.
    """

    device: int | None = None
    _stream: sd.OutputStream | None = None
    _hang: list[np.ndarray] = field(default_factory=list)
    _dang: np.ndarray | None = None
    _o: int = 0
    _tong: int = 0
    moc_phat: list[dict] = field(default_factory=list)
    moc: list[dict] = field(default_factory=list)

    def _callback(self, outdata, frames, time_info, status) -> None:
        perf = time.perf_counter()
        self.moc.append({"mau": self._tong, "dac": float(time_info.outputBufferDacTime),
                         "hien_tai": float(time_info.currentTime), "perf": perf})
        outdata.fill(0.0)
        viet = 0
        while viet < frames:
            if self._dang is None:
                if not self._hang:
                    break
                self._dang, self._o = self._hang.pop(0), 0
                # Mốc DAC của ĐÚNG mẫu đầu tiên của kích thích: mốc của khung này cộng
                # phần đã ghi trước nó trong chính khung này.
                self.moc_phat.append({
                    "dac": float(time_info.outputBufferDacTime) + viet / FS,
                    "hien_tai": float(time_info.currentTime),
                    "perf": perf,
                    "mau_ra": self._tong + viet,
                })
            con = len(self._dang) - self._o
            n = min(con, frames - viet)
            outdata[viet:viet + n, 0] = self._dang[self._o:self._o + n]
            self._o += n
            viet += n
            if self._o >= len(self._dang):
                self._dang = None
        self._tong += frames

    def bat_dau(self) -> None:
        self._stream = sd.OutputStream(
            device=self.device, channels=1, samplerate=FS, dtype="float32",
            blocksize=0, callback=self._callback,
            extra_settings=sd.WasapiSettings(auto_convert=True),
        )
        self._stream.start()

    def phat(self, song: np.ndarray) -> dict:
        """Xếp hàng rồi CHỜ hết — stream đã chạy sẵn nên không có chi phí mở."""
        assert self._stream is not None
        truoc = len(self.moc_phat)
        self._hang.append(np.asarray(song, dtype=np.float32))
        het = time.perf_counter() + len(song) / FS + 5.0
        while len(self.moc_phat) == truoc or self._dang is not None or self._hang:
            if time.perf_counter() > het:
                raise SystemExit("loa khong rut het hang doi — stream chet?")
            time.sleep(0.005)
        time.sleep(float(self._stream.latency) + 0.05)
        return self.moc_phat[-1]

    def dung(self) -> dict:
        assert self._stream is not None
        do_tre = float(self._stream.latency)
        self._stream.stop()
        self._stream.close()
        return {"do_tre_khai_bao_s": do_tre, "moc": self.moc, "moc_phat": self.moc_phat}


def quy_ve_perf(moc: list[dict], truc: str) -> tuple[float, float]:
    """Khớp tuyến tính chỉ số mẫu -> `perf_counter` (giây). Trả (hệ số, hằng số).

    Khớp cả chuỗi chứ không lấy mốc đầu: một callback lỡ nhịp làm lệch mốc đầu cả
    chục ms, còn khớp bình phương tối thiểu trên vài nghìn callback thì nó chỉ là một
    điểm ngoại lai. Hệ số khớp được cũng chính là tốc độ mẫu THẬT của card.
    """
    diem = [(m["mau"], m[truc]) for m in moc if truc in m and "mau" in m]
    if len(diem) < 3:
        raise SystemExit(f"không đủ mốc để khớp trục {truc!r}")
    x = np.array([p[0] for p in diem], dtype=np.float64)
    y = np.array([p[1] for p in diem], dtype=np.float64)
    if truc != "perf":
        # Trục của PortAudio lệch gốc so với perf_counter. Đo độ lệch ấy bằng chính
        # cặp (currentTime, perf) ghi trong cùng callback, rồi cộng vào.
        cap = [(m["hien_tai"], m["perf"]) for m in moc if "hien_tai" in m and "perf" in m]
        lech = statistics.median(p - c for c, p in cap)
        y = y + lech
    he_so, hang_so = np.polyfit(x, y, 1)
    return float(he_so), float(hang_so)


# -- phát -------------------------------------------------------------------


def kich_thich(cau_wav: Path, bien_do_click: float,
               chuan_hoa: float = 0.95) -> np.ndarray:
    """[click 6 ms] + [im 250 ms] + [câu nói của chủ nhân], tất cả ở 48 kHz.

    Click đi TRƯỚC câu nói vì hai lý do, và cái thứ hai mới là cái quyết định:

    1. sườn lên của click sắc tới một mẫu, còn giọng người lên biên độ thoai thoải qua
       cả trăm ms — định vị đỉnh trên giọng nói thì sai số to ngang thứ đang đo;
    2. click cũng là cái làm VAD của server nổ, nên `t_rx_speech_first` mà server ghi
       và đỉnh thứ nhất trong file thu là **cùng một sự kiện vật lý**. Nếu để câu nói
       tự làm mốc thì hai bên chấm vào hai chỗ khác nhau của cùng một sườn lên, và
       phần chênh ấy rơi thẳng vào ô "chặng xuống".
    """
    am, sr = sf.read(cau_wav, dtype="float32", always_2d=False)
    if am.ndim > 1:
        am = am.mean(axis=1)
    if sr != FS:
        am = sig.resample_poly(am, FS, sr).astype(np.float32)
    # Chuẩn hoá đỉnh: bộ thu 06/09 nằm ở −3,8 tới −11,4 dBFS, và qua loa laptop thì
    # tới mic board chỉ còn khoảng −40 dBFS — đo mẻ đầu 10/09: đỉnh RMS 328/32768, và
    # ở mức ấy VAD Silero của pipeline **phần lớn không nổ**, 7 lượt thì 4 lượt chép ra
    # chuỗi rỗng. Kéo mỗi câu lên gần toàn thang là lấy lại 6–11 dB, miễn phí.
    #
    # Cái phải nói rõ khi trích số: việc này làm MẤT chênh lệch âm lượng giữa các câu.
    # Với phép đo ĐỘ TRỄ thì không sao — cái ta đo là mốc thời gian, không phải mức to
    # nhỏ. Với WER thì sẽ là một biến đã bị can thiệp, nên đừng lấy transcript của mẻ
    # này đi so WER với bảng desktop.
    if chuan_hoa > 0:
        dinh = float(np.abs(am).max())
        if dinh > 1e-6:
            am = am * (chuan_hoa / dinh)

    rng = np.random.default_rng(20260910)
    n = int(FS * CLICK_MS / 1000)
    b, a = sig.butter(4, CLICK_HP / (FS / 2), btype="high")
    click = sig.lfilter(b, a, rng.standard_normal(n))
    click *= np.linspace(1.0, 0.0, n) ** 2
    click = (click * (bien_do_click / np.abs(click).max())).astype(np.float32)

    im = np.zeros(int(FS * CLICK_GAP_S), dtype=np.float32)
    return np.concatenate([click, im, am.astype(np.float32)])


def chay(args: argparse.Namespace) -> int:
    thu_muc = Path(args.out)
    thu_muc.mkdir(parents=True, exist_ok=True)

    refs = json.loads(REFS.read_text(encoding="utf-8"))
    cau: list[dict] = []
    for stt, hau_to in enumerate(LAN_DAU, start=1):
        ten = f"20260906_134002_{hau_to}.wav"
        duong = UTTS_DIR / ten
        if not duong.exists():
            raise SystemExit(f"thiếu {duong}")
        cau.append({"stt": stt, "wav": ten, **refs[ten]})

    if args.chi:
        giu = {int(x) for x in args.chi.split(",")}
        cau = [c for c in cau if c["stt"] in giu]

    print("Bo kich thich: cau bai test, giong CHU NHAN, lan thu dau cua moi cau.")
    for c in cau:
        print(f"  {c['stt']:2d}. [{c['lang']}] {c['text']}")

    danh_dau_moc = FLOOR_LOG.stat().st_size if FLOOR_LOG.exists() else 0

    ghi = MayGhiAm(device=args.mic)
    ghi.bat_dau()
    loa = MayPhat(device=args.speaker)
    loa.bat_dau()
    print()
    print(f"Dang thu. Cho vit BAT DAU dap (toi da {args.cho_bat_dau:.0f} s), "
          f"roi cho no NOI XONG (toi da {args.nghi_toi_da:.0f} s).")
    t0 = time.perf_counter()
    time.sleep(args.dan)                       # lấy nền phòng
    nen_phong = ghi.muc_gan_day(min(args.dan, 2.0))
    nguong_im = max(nen_phong * args.im_gap, 1e-5)
    print(f"  nen phong {nen_phong:.6f} -> nguong 'da im' {nguong_im:.6f}")

    def cho_im(nhan: str) -> dict:
        """Chờ vịt NÓI XONG: chờ nó bắt đầu đã, rồi mới chờ nó im.

        Chỉ chờ-cho-tới-khi-im là không đủ, và đây là chỗ mẻ 22:43 ngày 10/09 hỏng:
        sau khi phát xong câu hỏi thì phòng ĐANG im thật — vịt còn đang nghĩ. STT
        2,5 s + LLM 1 s + TTS 1 s + chặng xuống 0,8 s, cộng 700 ms VAD phải chờ, nên
        tiếng đáp chỉ ra sau chừng 6–7 giây. Vòng chờ cũ thấy im ở giây thứ 6 liền
        tuyên bố xong và phát câu kế — câu kế rơi đúng lúc board đang nói, mà lúc nói
        thì board TẮT MIC. Kết quả: 10 kích thích ra 3 lượt.

        Nên hai pha, và pha một mới là pha quan trọng.
        """
        bat_dau = time.perf_counter()
        # Chắn cứng trước khi bắt đầu rình: đuôi vang của chính câu hỏi ta vừa phát
        # còn trong phòng thêm cả giây, và `loa.phat()` chỉ chờ hết đệm chứ không chờ
        # hết vang. Mẻ 22:57 ngày 10/09 dính đúng cái đó — cả 10 câu đều báo "vịt đáp
        # xong sau 3,9 s", trong khi e2e nhanh nhất đo được là 4,1 s CHƯA kể vịt nói.
        # Nói cách khác nó rình phải tiếng của chính mình.
        time.sleep(args.cho_truoc)
        da_noi = False
        while time.perf_counter() - bat_dau < args.cho_bat_dau:
            if ghi.muc_gan_day(0.3) > nguong_im:
                time.sleep(0.25)
                if ghi.muc_gan_day(0.3) > nguong_im:   # phải DAI, không phải một cú cạch
                    da_noi = True
                    break
            time.sleep(0.05)
        if not da_noi:
            print(f"      {nhan}: KHONG THAY VIT DAP trong {args.cho_bat_dau:.0f} s")
            return {"cho_s": time.perf_counter() - bat_dau, "co_dap": False}

        im_tu = None
        while time.perf_counter() - bat_dau < args.nghi_toi_da:
            if ghi.muc_gan_day(0.5) < nguong_im:
                im_tu = im_tu or time.perf_counter()
                if time.perf_counter() - im_tu >= args.im_bao_lau:
                    break
            else:
                im_tu = None
            time.sleep(0.05)
        time.sleep(args.nghi_them)
        cho = time.perf_counter() - bat_dau
        print(f"      {nhan}: vit dap, xong sau {cho:.1f} s"
              + ("" if im_tu else "  ! HET GIO, van con tieng"))
        return {"cho_s": cho, "co_dap": True, "het_gio": im_tu is None}

    ke_hoach = []
    for c in cau:
        song = kich_thich(UTTS_DIR / c["wav"], args.bien_do, args.chuan_hoa)
        moc_phat = loa.phat(song)
        ke_hoach.append({
            **c,
            "phat_perf": moc_phat["perf"],
            "phat_dac": moc_phat["dac"],
            "phat_hien_tai": moc_phat["hien_tai"],
            "dai_kich_thich_s": len(song) / FS,
        })
        ke_hoach[-1] |= cho_im(f"[{c['stt']:2d}/10] phat {len(song)/FS:.2f} s")

    time.sleep(args.duoi)
    thu, meta = ghi.dung()
    meta_loa = loa.dung()
    t1 = time.perf_counter()

    wav = thu_muc / "thu.wav"
    sf.write(wav, thu, FS)
    (thu_muc / "meta.json").write_text(json.dumps({
        "ngay": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mic": args.mic, "speaker": args.speaker,
        "mic_ten": sd.query_devices(args.mic)["name"] if args.mic is not None else "mặc định",
        "loa_ten": sd.query_devices(args.speaker)["name"] if args.speaker is not None else "mặc định",
        "fs": FS, "click_ms": CLICK_MS, "click_gap_s": CLICK_GAP_S,
        "bien_do_click": args.bien_do,
        "t0_perf": t0, "t1_perf": t1,
        "floor_log_byte_truoc": danh_dau_moc,
        "floor_log": str(FLOOR_LOG),
        "ke_hoach": ke_hoach,
        "thu": meta,
        "phat": meta_loa,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nThu xong {len(thu)/FS:.1f} s -> {wav}")
    print(f"Mốc và kế hoạch -> {thu_muc/'meta.json'}")
    print("Giờ chạy:  python scripts\\bench_devout.py doc --dir", thu_muc)
    return 0


# -- phần đọc ---------------------------------------------------------------


def bao_bang(x: np.ndarray, cua_so_ms: float) -> np.ndarray:
    n = max(1, int(FS * cua_so_ms / 1000))
    bp = sig.fftconvolve(x.astype(np.float64) ** 2, np.ones(n) / n, mode="same")
    return np.sqrt(np.maximum(bp, 0.0))


def loc_dai(x: np.ndarray, thap: float, cao: float) -> np.ndarray:
    b, a = sig.butter(4, [thap / (FS / 2), cao / (FS / 2)], btype="band")
    return sig.lfilter(b, a, x)


def suon_len(bao: np.ndarray, tu: int, den: int, nguong: float, giu_ms: float) -> int | None:
    """Mẫu đầu tiên trong [tu, den) vượt ngưỡng và GIỮ được `giu_ms`.

    Điều kiện giữ là bắt buộc: một tiếng động cửa hay tiếng gõ phím cũng vượt ngưỡng,
    nhưng nó tắt trong vài chục ms còn câu trả lời của vịt thì kêu cả giây. Không có
    nó thì mốc chấm vào tiếng động lạ và số ra nhỏ đi một cách trông rất đẹp.
    """
    giu = int(FS * giu_ms / 1000)
    tren = (bao[tu:den] > nguong).astype(np.int32)
    if tren.size <= giu:
        return None
    # Tổng trượt bằng tổng tích luỹ, không phải np.convolve: cửa sổ ở đây dài 7 200
    # mẫu trên đoạn 720 000, và tích chập trực tiếp là ~5 tỉ phép — bảng quét độ nhạy
    # chạy 12 lần như thế làm `doc` treo quá hai phút. Tổng tích luỹ là O(n).
    cs = np.concatenate([[0], np.cumsum(tren)])
    dem = cs[giu:] - cs[:-giu]
    ung = np.flatnonzero(dem == giu)
    return None if ung.size == 0 else tu + int(ung[0])


def loc_phoi_hop(bao_thu: np.ndarray, tu: int, den: int,
                 mau: np.ndarray, buoc: int) -> dict:
    """Trượt ĐƯỜNG BAO của dòng TTS đã gửi dọc đường bao file thu, lấy đỉnh tương quan.

    Vì sao đối chiếu ĐƯỜNG BAO chứ không phải dạng sóng: giữa hai bên có một cái loa
    8 Ω, một căn phòng, một mic, và một vòng Opus 24 kHz. Pha thì những thứ đó phá
    sạch; còn "to nhỏ theo thời gian" thì chúng giữ gần như nguyên. Tương quan trên
    dạng sóng sẽ ra một mặt phẳng nhiễu, trên đường bao thì ra một đỉnh.

    Trả về cả `bien` — đỉnh cao hơn đỉnh nhì bao nhiêu lần. Đó là thước đo "phép ghép
    này có duy nhất không". `bien` sát 1 nghĩa là có hai chỗ khớp ngang nhau và mốc
    chấm được không đáng tin, dù giá trị tương quan có cao đến đâu.
    """
    x = bao_thu[tu:den:buoc].astype(np.float64)
    m = mau[::buoc].astype(np.float64)
    if x.size < m.size + 4 or m.size < 8:
        return {"loi": "cua so ngan hon mau"}
    x = x - x.mean()
    m = m - m.mean()
    if not np.any(m) or not np.any(x):
        return {"loi": "mau hoac cua so phang"}
    # Tương quan chuẩn hoá theo từng vị trí: mẫu cố định, cửa sổ thì trượt, nên phải
    # chia cho chuẩn của ĐOẠN đang so chứ không phải của cả cửa sổ.
    tu_so = sig.correlate(x, m, mode="valid")
    nang = sig.correlate(x ** 2, np.ones(m.size), mode="valid")
    mau_so = np.sqrt(np.maximum(nang, 1e-30)) * np.sqrt((m ** 2).sum())
    r = tu_so / mau_so
    i = int(np.argmax(r))
    dinh = float(r[i])
    # Đỉnh nhì: bỏ hẳn một vùng quanh đỉnh nhất, không thì "đỉnh nhì" chỉ là sườn của
    # chính đỉnh nhất và tỉ số luôn đẹp.
    cam = max(1, int(m.size // 2))
    khac = np.concatenate([r[:max(0, i - cam)], r[i + cam:]])
    nhi = float(khac.max()) if khac.size else 0.0
    return {"mau_lech": i * buoc, "dinh": round(dinh, 4), "nhi": round(nhi, 4),
            "bien": round(dinh / nhi, 2) if nhi > 1e-6 else float("inf")}


def doc(args: argparse.Namespace) -> int:
    thu_muc = Path(args.dir)
    meta = json.loads((thu_muc / "meta.json").read_text(encoding="utf-8"))
    thu, sr = sf.read(thu_muc / "thu.wav", dtype="float32", always_2d=True)
    assert sr == FS
    # Mic array raw có nhiều kênh; chúng cách nhau vài cm nên lệch nhau ~0,1 ms —
    # không đáng kể so với thứ đang đo. Lấy kênh KHOẺ NHẤT cho tỉ số đỉnh/nền cao nhất.
    muc = [float(np.sqrt((thu[:, c] ** 2).mean())) for c in range(thu.shape[1])]
    kenh = int(np.argmax(muc)) if args.kenh is None else args.kenh
    if thu.shape[1] > 1:
        print("Kenh mic: " + " · ".join(f"ch{c} rms {v:.5f}" for c, v in enumerate(muc))
              + f"  -> dung ch{kenh}")
    thu = thu[:, kenh]

    he_so, hang_so = quy_ve_perf(meta["thu"]["moc"], args.truc)
    do_tre_khai_bao = meta["thu"]["do_tre_khai_bao_s"]

    def perf_cua(mau: int) -> float:
        return he_so * mau + hang_so

    def mau_cua(perf: float) -> int:
        return int(round((perf - hang_so) / he_so))

    print(f"Truc thoi gian: {args.truc!r} · toc do mau khop duoc {1/he_so:.1f} Hz "
          f"(khai bao {FS}) · do tre duong thu WASAPI khai bao "
          f"{do_tre_khai_bao*1000:.1f} ms · che do {meta['thu'].get('che_do','?')}")

    # -- ĐỈNH 1: click của ta, trong chính file thu ---------------------------
    b, a = sig.butter(4, CLICK_HP / (FS / 2), btype="high")
    cao = np.abs(sig.lfilter(b, a, thu))
    clicks = []
    for k in meta["ke_hoach"]:
        # Cửa sổ LỆCH MỘT PHÍA: click chỉ ra loa SAU lúc ta xếp nó vào hàng đợi, không
        # bao giờ trước. Mốc DAC của PortAudio lệch hệ thống ~100 ms so với trục ADC
        # trên máy này (đo 10/09), nên đừng lấy nó làm tâm.
        tu = max(0, mau_cua(k["phat_perf"]) - int(FS * 0.05))
        den = min(thu.size, tu + int(FS * args.cua_so_click))
        if den - tu < 10:
            continue
        i_c = tu + int(np.argmax(cao[tu:den]))
        nen = float(np.median(cao[tu:den]))
        clicks.append({"stt": k["stt"], "text": k["text"], "mau": i_c,
                       "perf": perf_cua(i_c), "dinh": float(cao[i_c]), "nen": nen,
                       "ti_so": round(float(cao[i_c]) / max(nen, 1e-12), 1),
                       "tin": bool(cao[i_c] > max(30 * nen, 1e-3))})
    tin = [c for c in clicks if c["tin"]]
    if clicks:
        ti = [c["ti_so"] for c in clicks]
        print(f"Click nghe ro: {len(tin)}/{len(clicks)} · ti so dinh/nen "
              f"min {min(ti):.0f}x median {statistics.median(ti):.0f}x")
        if len(tin) < len(clicks):
            print("  ! Click bi nuot -> AEC con trong duong thu, hoac loa qua nho.")

    # -- CHẶNG LÊN: ghép click trong file thu với cạnh lên phía server ---------
    duong_floor = Path(meta["floor_log"])
    with duong_floor.open("rb") as h:
        h.seek(meta["floor_log_byte_truoc"])
        moi = h.read().decode("utf-8", "replace")
    turns = [json.loads(d) for d in moi.splitlines() if d.strip()]
    canh_len = sorted(v / 1000.0 for t in turns for v in (t.get("onsets_perf_ms") or []))
    print(f"Canh len phia server trong buoi: {len(canh_len)} (tren {len(turns)} Turn)")

    for c in clicks:
        # Cửa sổ ghép chặn theo VẬT LÝ, không theo cảm tính. Cận dưới: một khung Opus
        # dài 60 ms và server chỉ nhận được nguyên khung, nên khung CHỨA tiếng click
        # không thể tới sớm hơn chừng ấy sau lúc click vang lên — trừ đi `m` (~20 ms)
        # thì cận dưới hợp lệ là 30 ms. Số nào nhỏ hơn thế là ghép nhầm vào một cạnh
        # lên khác, và mẻ 22:24 ngày 10/09 đã cho ra "12,1 ms" đúng theo kiểu ấy.
        ung = [o for o in canh_len
               if args.len_toi_thieu <= o - c["perf"] <= args.ghep_toi_da]
        if ung:
            c["server_perf"] = ung[0]
            c["len_tru_m_ms"] = round((ung[0] - c["perf"]) * 1000.0, 1)
    co_len = [c for c in clicks if "len_tru_m_ms" in c]
    print(f"Ghep duoc chang len: {len(co_len)}/{len(clicks)} click")

    # -- lượt TRẢ LỜI: một bản ghi mỗi câu, từ log latency của pipeline --------
    duong = Path(args.latency)
    ban_ghi = [json.loads(d) for d in duong.read_text(encoding="utf-8").splitlines() if d.strip()]
    t0, t1 = meta["t0_perf"], meta["t1_perf"]
    luot = [r for r in ban_ghi
            if r.get("tx_first_perf_ms") is not None
            and t0 <= r["tx_first_perf_ms"] / 1000.0 <= t1]
    print(f"Ban ghi latency co moc tx trong buoi thu: {len(luot)}")
    thieu = [r for r in ban_ghi
             if r.get("tx_first_perf_ms") is None and r.get("source") == "device"]
    if thieu:
        print(f"  ({len(thieu)} ban ghi khong co tra loi — STT ra rong hoac LLM khong dap)")

    # -- mẫu THAM CHIẾU: đúng dòng PCM server đã gửi xuống board ---------------
    mau_tts: list[dict] = []
    if args.tts:
        d_tts = Path(args.tts)
        dong = (d_tts / "tts.jsonl")
        if dong.exists():
            for l in dong.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    mau_tts.append(json.loads(l))
        print(f"Mau TTS tham chieu: {len(mau_tts)}")

    def lay_mau(tx_perf_ms: float) -> np.ndarray | None:
        """Dòng TTS của câu trả lời có mốc perf gần `tx_perf_ms` nhất."""
        if not mau_tts:
            return None
        gan = min(mau_tts, key=lambda r: abs(r["perf_ms"] - tx_perf_ms))
        if abs(gan["perf_ms"] - tx_perf_ms) > 500:
            return None
        y, sr_y = sf.read(Path(args.tts) / gan["wav"], dtype="float32", always_2d=False)
        if y.ndim > 1:
            y = y.mean(axis=1)
        if sr_y != FS:
            y = sig.resample_poly(y, FS, sr_y).astype(np.float32)
        y = y[: int(FS * args.dai_mau)]
        return bao_bang(loc_dai(y, 300.0, 3400.0), 20.0)

    # -- ĐỈNH 2: loa board đáp ------------------------------------------------
    # Dải 300–3400 Hz: giọng vịt qua loa 8 Ω nhỏ nằm gọn trong đó, còn ù nguồn 50 Hz
    # và tiếng quạt thì không.
    bao = bao_bang(loc_dai(thu, 300.0, 3400.0), 20.0)

    ket: list[dict] = []
    for idx, r in enumerate(luot):
        tx_perf = r["tx_first_perf_ms"] / 1000.0
        ke = luot[idx + 1]["tx_first_perf_ms"] / 1000.0 if idx + 1 < len(luot) else None
        tu = mau_cua(tx_perf)
        den = min(int(mau_cua(ke)) if ke else thu.size, thu.size,
                  tu + int(FS * args.cua_so))
        mot = {
            "ts": r.get("ts"), "user_text": r.get("user_text"),
            "duck_text": (r.get("duck_text") or "")[:60],
            "tx_perf": tx_perf,
            "end_to_end_ms": r.get("end_to_end_ms"),
            "t_dev_vad_end": r.get("t_dev_vad_end"),
            "rx_speech_first_perf_ms": r.get("rx_speech_first_perf_ms"),
        }
        if den - tu < FS // 10:
            mot["loi"] = "cua so qua ngan"
            ket.append(mot)
            continue
        # Nền lấy ở 500 ms NGAY TRƯỚC mốc tx — quãng vịt đang nghĩ, phòng im. Nền của
        # đúng lúc ấy, không phải nền trung bình cả buổi.
        n0 = max(0, tu - int(FS * 0.5))
        nen = float(np.median(bao[n0:tu])) if tu > n0 + 100 else float(np.median(bao))
        nguong = max(args.he_so_nen * nen, args.nen_toi_thieu)
        i_dap = suon_len(bao, tu, den, nguong, args.giu_ms)
        mot |= {"nen": nen, "nguong": nguong}
        if i_dap is None:
            mot["loi"] = "khong thay loa board dap trong cua so"
            ket.append(mot)
            continue
        mot["dap_perf_nguong"] = perf_cua(i_dap)
        mot["xuong_nguong_ms"] = round((perf_cua(i_dap) - tx_perf) * 1000.0, 1)

        # Lọc phối hợp: mốc chính. Ngưỡng ở trên giữ lại làm đối chứng — hai cách
        # chấm độc lập mà ra gần nhau thì tin được, lệch nhau thì phải nói ra.
        mau_bao = lay_mau(r["tx_first_perf_ms"])
        if mau_bao is not None and mau_bao.size:
            lpp = loc_phoi_hop(bao, tu, den, mau_bao, args.buoc)
            mot["lpp"] = lpp
            if "mau_lech" in lpp:
                mot["dap_perf"] = perf_cua(tu + lpp["mau_lech"])
                mot["xuong_cong_m_ms"] = round(
                    (mot["dap_perf"] - tx_perf) * 1000.0, 1)
                # `bien` là CHẨN ĐOÁN, không phải cổng chặn — và đây là chỗ đã suýt
                # chọn nhầm. Lúc đầu tôi loại mọi lượt có bien < 1,25; đo ra thì hai
                # lượt bị loại ấy có mốc 319 và 307 ms, tức là nằm gọn trong cụm
                # 295–332 ms của những lượt được nhận. Cổng ấy đang vứt đi số ĐÚNG,
                # chỉ vì đường bao của giọng nói tự nó có đỉnh phụ thật.
                #
                # Nên giữ tất cả, gắn nhãn "ghép yếu", rồi báo cả hai bộ. Ai đọc cũng
                # thấy được việc loại chúng đi có đổi kết luận hay không.
                mot["ghep_yeu"] = bool(lpp["bien"] < args.bien_toi_thieu)
        if "dap_perf" not in mot:
            mot["loi"] = mot.get("loi") or "loc phoi hop khong chay duoc"

        # (b) chặng lên − m: click nào là câu hỏi của lượt này. Lấy click GẦN NHẤT
        # TRƯỚC mốc tx — vịt không thể đáp trước khi nghe.
        truoc = [c for c in co_len if c["perf"] < tx_perf]
        if truoc and "xuong_cong_m_ms" in mot:
            gan = truoc[-1]
            mot["click_stt"] = gan["stt"]
            mot["click_perf"] = gan["perf"]
            mot["len_tru_m_ms"] = gan["len_tru_m_ms"]
            # TỔNG hai chặng: m TRIỆT TIÊU, vì nó vào một lần với dấu dương và một lần
            # với dấu âm. Đây là con số duy nhất ở đây không cần một giả định nào về
            # đường thu của laptop — và cũng đúng là con số bảng 3 cần cộng.
            mot["san_thiet_bi_ms"] = round(
                gan["len_tru_m_ms"] + mot["xuong_cong_m_ms"], 1)
            mot["delta_server_ms"] = round(
                (tx_perf - gan["server_perf"]) * 1000.0, 1)
            mot["delta_vong_ms"] = round((mot["dap_perf"] - gan["perf"]) * 1000.0, 1)
        ket.append(mot)

    (thu_muc / "ket.json").write_text(
        json.dumps({"clicks": clicks, "luot": ket, "truc": args.truc,
                    "kenh": kenh, "fs_that": 1 / he_so,
                    "do_tre_khai_bao_s": do_tre_khai_bao,
                    "latency_log": str(duong)},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    def pct(xs, q):
        if not xs:
            return float("nan")
        xs = sorted(xs)
        return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]

    cot = {
        "chang len - m (do truc tiep)": [c["len_tru_m_ms"] for c in co_len],
        "chang xuong + m (loc phoi hop)": [m["xuong_cong_m_ms"] for m in ket if "xuong_cong_m_ms" in m],
        "  ...chi nhung luot ghep MANH": [m["xuong_cong_m_ms"] for m in ket
                                          if "xuong_cong_m_ms" in m and not m.get("ghep_yeu")],
        "chang xuong + m (nguong, doi chung)": [m["xuong_nguong_ms"] for m in ket if "xuong_nguong_ms" in m],
        "SAN THIET BI = len + xuong": [m["san_thiet_bi_ms"] for m in ket if "san_thiet_bi_ms" in m],
        "delta_vong (click -> loa board)": [m["delta_vong_ms"] for m in ket if "delta_vong_ms" in m],
        "delta_server (pipeline)": [m["delta_server_ms"] for m in ket if "delta_server_ms" in m],
    }
    hong = [m for m in ket if "dap_perf" not in m]
    print()
    print(f"Ghep duoc {len(cot['SAN THIET BI = len + xuong'])}/{len(luot)} luot.")
    if hong:
        print(f"  ! {len(hong)} luot khong thay loa board dap — nghe lai thu.wav "
              f"quanh moc truoc khi tin phan con lai.")
    print()
    print(f"  {'':34s} {'p50':>8s} {'p95':>8s} {'min':>8s} {'max':>8s}   n")
    for ten, xs in cot.items():
        if xs:
            print(f"  {ten:34s} {pct(xs,0.5):8.1f} {pct(xs,0.95):8.1f} "
                  f"{min(xs):8.1f} {max(xs):8.1f} {len(xs):3d}")

    # -- QUÉT ĐỘ NHẠY ---------------------------------------------------------
    # Ngưỡng và thời gian giữ của bộ dò tiếng đáp là hai con số ta TỰ CHỌN, mà chọn
    # sau khi đã nhìn dữ liệu thì rất dễ chọn ra con số mình muốn. Nên in luôn cả
    # bảng: số nào đứng yên qua cả dải thì tin được, số nào nhảy theo tham số thì
    # phải nói ra là nó nhảy.
    print("\n  Do nhay cua 'chang xuong + m' theo tham so bo do (p50 ms / n):")
    print('  ' + 'giu_ms / he_so_nen'.rjust(22)
          + ''.join(f"{k:>12.0f}" for k in (4, 6, 10)))
    for giu in (40.0, 60.0, 100.0, 150.0):
        hang = f"  {giu:>22.0f}"
        for hs in (4.0, 6.0, 10.0):
            xs = []
            for idx, r in enumerate(luot):
                tx_perf = r["tx_first_perf_ms"] / 1000.0
                ke = luot[idx + 1]["tx_first_perf_ms"] / 1000.0 if idx + 1 < len(luot) else None
                tu = mau_cua(tx_perf)
                den = min(int(mau_cua(ke)) if ke else thu.size, thu.size,
                          tu + int(FS * args.cua_so))
                if den - tu < FS // 10:
                    continue
                n0 = max(0, tu - int(FS * 0.5))
                nen = float(np.median(bao[n0:tu])) if tu > n0 + 100 else float(np.median(bao))
                i_d = suon_len(bao, tu, den, max(hs * nen, args.nen_toi_thieu), giu)
                if i_d is not None:
                    xs.append((perf_cua(i_d) - tx_perf) * 1000.0)
            hang += f"{pct(xs,0.5):>8.0f}/{len(xs):<3d}" if xs else f"{'—':>12s}"
        print(hang)
    return 0


def main() -> int:
    enable_utf8_console()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="lenh", required=True)

    r = sub.add_parser("chay", help="phát 10 câu + thu cả buổi")
    r.add_argument("--out", required=True)
    r.add_argument("--mic", type=int, default=None, help="thiết bị thu (WASAPI)")
    r.add_argument("--speaker", type=int, default=None, help="thiết bị phát (WASAPI)")
    r.add_argument("--slot", type=float, default=20.0,
                   help="(bỏ) giữ lại cho tương thích, nhịp giờ theo tín hiệu")
    r.add_argument("--cho-truoc", type=float, default=3.0,
                   help="giây chắn cứng sau khi phát xong, trước khi rình tiếng đáp")
    r.add_argument("--cho-bat-dau", type=float, default=25.0,
                   help="giây chờ vịt BẮT ĐẦU đáp; hết giờ thì coi như lượt này mất")
    r.add_argument("--nghi-them", type=float, default=1.5,
                   help="giây đệm sau khi vịt im, trước khi phát câu kế")
    r.add_argument("--nghi-toi-da", type=float, default=45.0,
                   help="giây tối đa chờ vịt nói xong")
    r.add_argument("--im-bao-lau", type=float, default=2.0,
                   help="giây im liên tục thì coi là vịt đã nói xong")
    r.add_argument("--im-gap", type=float, default=2.5,
                   help="ngưỡng 'đã im' = nền phòng nhân chừng này")
    r.add_argument("--dan", type=float, default=3.0, help="giây im đầu buổi")
    r.add_argument("--duoi", type=float, default=5.0, help="giây im cuối buổi")
    r.add_argument("--bien-do", type=float, default=0.5, help="biên độ click 0..1")
    r.add_argument("--chuan-hoa", type=float, default=0.95,
                   help="kéo đỉnh mỗi câu lên mức này (0 = giữ nguyên)")
    r.add_argument("--chi", default=None, metavar="1,2,3",
                   help="chỉ chạy những câu này (đánh số từ 1) — dùng để thử trước")
    r.add_argument("--danh-thuc", default=None, metavar="WAV",
                   help="phát file này trước cả buổi để board bắt cụm gọi và mở phiên "
                        "(board chỉ mở WebSocket sau wake word)")
    r.add_argument("--cho-thuc", type=float, default=6.0,
                   help="giây chờ sau cụm gọi, cho board vào phiên")
    r.set_defaults(func=chay)

    d = sub.add_parser("doc", help="phân tích file đã thu")
    d.add_argument("--dir", required=True)
    d.add_argument("--truc", default="adc", choices=("adc", "perf"),
                   help="adc = mốc ADC của PortAudio (đã trừ độ trễ khai báo); "
                        "perf = lúc callback chạy (chưa trừ gì)")
    d.add_argument("--cua-so", type=float, default=15.0, help="giây tìm tiếng đáp")
    d.add_argument("--cua-so-click", type=float, default=1.0,
                   help="giây tìm click, tính từ lúc xếp vào hàng đợi loa")
    d.add_argument("--he-so-nen", type=float, default=6.0)
    d.add_argument("--nen-toi-thieu", type=float, default=2e-4)
    d.add_argument("--giu-ms", type=float, default=150.0)
    d.add_argument("--kenh", type=int, default=None, help="ép dùng kênh mic này")
    d.add_argument("--latency", required=True,
                   help="log latency của pipeline (một bản ghi mỗi câu trả lời)")
    d.add_argument("--tts", default=None, metavar="THU_MUC",
                   help="thư mục --dump-tts của device_server: dòng PCM tham chiếu")
    d.add_argument("--dai-mau", type=float, default=3.0,
                   help="giây đầu của câu trả lời dùng làm mẫu lọc phối hợp")
    d.add_argument("--buoc", type=int, default=48,
                   help="bước lấy mẫu đường bao khi tương quan (48 = 1 ms)")
    d.add_argument("--bien-toi-thieu", type=float, default=1.25,
                   help="đỉnh tương quan phải cao hơn đỉnh nhì chừng này lần")
    d.add_argument("--len-toi-thieu", type=float, default=0.030,
                   help="giây: chặn dưới vật lý của chặng lên (một khung Opus trừ m)")
    d.add_argument("--ghep-toi-da", type=float, default=0.35,
                   help="giây: lệch tối đa cho phép giữa mốc click trong file thu và "
                        "mốc server nghe thấy nó, khi ghép hai bên")
    d.set_defaults(func=doc)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
