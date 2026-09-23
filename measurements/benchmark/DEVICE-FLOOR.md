# Device floor — độ trễ sàn của ES3C28P

**Trạng thái (10/09/2026): ĐỦ CẢ HAI CHẶNG.** Chặng lên và chặng xuống đều có số, và
bảng 3 cộng được. Sàn thiết bị **p50 = 526 ms**, trong đó chặng xuống 299 ms đắt hơn
chặng lên 198 ms — ngược với dự đoán trước khi đo.

`t_dev_ack` **vẫn rỗng** (firmware v2.3.0 không báo ngược), nên chặng xuống không đo được
từ xa; nó đo được bằng **mic thứ hai**: mic laptop mở ở WASAPI exclusive, nghe tiếng loa
board, đối chiếu bằng lọc phối hợp với đúng dòng PCM mà server đã gửi. Cách làm, ba chỗ
khác §B, và **bốn khoản sai số** nằm ở mục "Đo chặng xuống bằng mic thứ hai (10/09/2026)"
— **đọc mục đó trước khi trích bảng 2b và bảng 3.**

Bảng 1 và bảng 2 dưới đây vẫn là số của **giai đoạn echo** (06/09), giữ nguyên làm hồ sơ.
Bảng 2b là số của chế độ **pipeline**; mốc và định nghĩa của chế độ ấy ở mục
"Chế độ `pipeline`" phía dưới.

Ngày lập: 2026-09-06. Nguồn số: `desktop/logs/device_floor.jsonl` do
`desktop/device_server.py` ghi (47 lượt có phát lại, trong 57 lượt ghi được).

> **ĐÍNH CHÍNH 10/09/2026 (việc 29a) — đọc trước khi trích số của mẻ 09/09.**
>
> Dữ liệu thô đã chép vào `docs/benchmark/` để truy được nguồn:
> `device_floor_20260906_v1.jsonl` (mẻ 06/09) và `device_floor_20260909_v1.jsonl`
> (mẻ 09/09). **Log gốc `desktop/logs/device_floor.jsonl` đã xoay vòng** — nó không
> còn bản ghi nào của 06/09; mẻ ấy nằm ở `device_floor_20260906_lansuadau.jsonl`.
>
> **Mẻ 06/09 (Bảng 1 và 2): tái lập 100 %.** Lát cắt đúng như câu trên — 57 bản ghi
> đầu, giữ lượt có `t_tx_first` → 47 lượt. Không con số nào phải sửa.
>
> **Mẻ 09/09: lát cắt 44/48 lượt KHÔNG tái lập được.** File đã bị ghi thêm 203 bản ghi
> sau đó (phiên `1788966446-9950` — chính đoạn "te te te" ở âm lượng 85 kể phía dưới),
> nên mốc byte 31221 giờ trỏ vào chỗ khác. Bài dùng lát cắt có nguyên tắc: **trọn phiên
> `1788966181-b850`, 59 lượt**. Số đổi theo: `t_rx_first` p50 **132,3 → 131,6**, p95
> **141,9 → 143,7**; jitter **5,79/9,99/10,29 → 6,12/10,24/13,40**; cỡ khung
> **146/146/147 → 143/146/153**; lệch hai nhóm **1,2 → 1,1 ms** (47 tone vs 12 im).
>
> **RTT p95 = 109,2 ms bị GỠ: giá trị ấy không tồn tại trong dữ liệu.** Mọi bản ghi của
> phiên mang `rtt_p50` = 4,65 (hằng số). Câu "p95 vẫn 109 ms — đuôi dài không mất đi
> cùng cái router" ở Bảng 1 dưới đây **sai và phải bỏ**.
>
> Bảng dưới giữ nguyên số cũ làm hồ sơ. Số vào bài lấy ở `docs/PAPER-NUMBERS.md` §1b–§1c.

## Câu hỏi cần trả lời

Baseline v3 (`docs/baseline/README.md`) nói vòng thoại **chạy hết trên laptop** tốn
e2e p50 ~5,1 s. Câu hỏi của M7: **đưa mic và loa ra board thì cộng thêm bao nhiêu?**

Đó là "device floor" — phần độ trễ mà phần mềm thoại **không** động tới được, dù có
tối ưu STT/LLM/TTS đến đâu. Biết nó rồi mới biết ngân sách còn lại cho pipeline.

## Cách đo

Giai đoạn **echo** của `device_server.py`: board thu tiếng, gửi khung Opus lên laptop,
laptop **vọng lại đúng những khung ấy**, board phát ra loa. Không có STT/LLM/TTS trong
vòng — nên toàn bộ thời gian đo được là của **mic + mã hoá + Wi-Fi + giải mã + loa**.

Vọng khung thô (không giải mã rồi mã hoá lại) là cố ý: thêm một vòng codec ở server sẽ
tính nhầm chi phí của ta vào chi phí của thiết bị.

## Mốc thời gian

Mọi mốc tính từ lúc `listen start` mở lượt, đơn vị ms, ghi trong `device_floor.jsonl`:

| trường | nghĩa |
|---|---|
| `t_rx_first` | khung Opus **đầu tiên** của lượt tới server |
| `t_rx_speech_first` | khung đầu tiên **CÓ TIẾNG** — mốc để trừ khi làm loopback vật lý; ở `mode=auto` nó khác `t_rx_first` đúng bằng quãng chờ người ta mở miệng |
| `t_rx_last` / `t_dev_vad_end` | khung **cuối** — thiết bị dứt lời, nhìn từ server |
| `t_tx_first` | khung **đầu tiên** server gửi trả |
| `t_dev_ack` | board báo đã bắt đầu phát — **có thể luôn rỗng**, xem "Giới hạn" |
| `jitter_ms` | lệch trung vị giữa khoảng cách các khung và 60 ms kỳ vọng |
| `rtt_p50` / `rtt_p95` | khứ hồi ping/pong ở tầng WebSocket |
| `clock_offset_ms` | **nửa RTT**, không phải lệch đồng hồ thật — xem "Giới hạn" |

## Bảng 1 — mạng

| | p50 | p95 | max | n |
|---|---|---|---|---|
| RTT ping/pong (ms) | 32,4 | 157,8 | 157,8 | 47 phiên |
| jitter khung Opus (ms) | 6,1 | 13,3 | 59,9 | 47 lượt |
| lỗi giải mã Opus / lượt | 0 | 0 | 0 | 38 lượt có giải mã |

RTT p50 của phiên tốt nhất là **22,3 ms**; con số 157,8 ms đến từ những phiên board
liên tục rớt kết nối cuối buổi. Wi-Fi cùng LAN, board cách router chừng 5 m, RSSI −49
đến −57 dBm.

Cỡ khung Opus: **132 / 146 / 173 byte** (min / trung vị / max). Gần như hằng số — encoder
trên board chạy **CBR**, khung im lặng to bằng khung có tiếng. Ghi lại vì nó đã làm hỏng
bản VAD đầu tiên của server, xem `SPEECH_REL` trong `device_server.py`.

## Bảng 2 — độ trễ một lượt echo

| chặng | p50 | p95 | n |
|---|---|---|---|
| `t_rx_first` (mở lượt → khung đầu tới server) | 133,4 | 166,0 | 47 |
| `t_rx_last − t_rx_first` (thời lượng thu) | 2 643,6 | 14 948,8 | 47 |
| `t_tx_first − t_rx_last` (server quay đầu) | **0,5** | 9,0 | 47 |
| **mic → loa** | **đã đo được 10/09**, xem bảng 2b | | |

Con số đáng chú ý là **`t_rx_first` p50 = 133 ms**: chi phí board dựng đường audio sau
khi báo bắt đầu nghe. Nó nằm thẳng trong ngân sách độ trễ, cộng vào **trước cả STT**, và
baseline desktop hiện tại không có khoản này vì mic cắm thẳng vào laptop.

Chặng "server quay đầu" 0,5 ms là của **giai đoạn echo**, đừng đọc như chi phí thật:
server chỉ đẩy lại khung có sẵn. Khi nối vào pipeline thoại, chỗ này sẽ là toàn bộ
STT + LLM + TTS.

`t_dev_ack` **rỗng ở cả 47 lượt** — firmware v2.3.0 không gửi `tts state=start` ngược
lên, nên server không có mốc nào của board. Nó vẫn rỗng hôm nay; chặng cuối đo được là
nhờ một cái mic thứ hai, không phải nhờ board chịu nói.

## Bảng 2b — chặng lên và chặng xuống của thiết bị (10/09/2026)

Ba mẻ độc lập, mỗi mẻ 10 câu bài test phát qua loa laptop cho board nghe, `--reply
pipeline`, board đáp bằng giọng thật ra loa của nó. Cách đo và sai số: mục "Đo chặng
xuống bằng mic thứ hai" phía dưới — **đọc mục đó trước khi trích ba con số này.**

| chặng | p50 | p95 | min | max | n |
|---|---|---|---|---|---|
| **chặng lên** − m (không khí ở mic board → khung Opus tới server) | 177,8 | 334,9 | 99,9 | 337,2 | 22 |
| **chặng xuống** + m (byte rời server → không khí ở loa board) | **319,0** | 352,0 | 257,0 | 1 466,0 | 18 |
| **SÀN THIẾT BỊ = lên + xuống** (m tự triệt tiêu) | **525,9** | 653,9 | 429,1 | 666,9 | 16 |

`m` là độ trễ đường thu của laptop — WASAPI exclusive khai báo **20,0 ms**. Nó vào chặng
lên với dấu âm và vào chặng xuống với dấu dương, nên **dòng thứ ba không phụ thuộc vào nó
chút nào**; hai dòng đầu thì có, và đó là lý do dòng thứ ba mới là dòng đem đi cộng.

Trừ `m` ra: chặng xuống ≈ **299 ms**, chặng lên ≈ **198 ms** (p50).

**Chặng xuống rất chụm.** 17 trong 18 lượt nằm gọn trong **257–352 ms**, trung bình
319,5 ms, độ lệch chuẩn **22,2 ms** — qua ba mẻ, hai buổi tối, hai kênh mic khác nhau.
Một lượt duy nhất ra 1 466 ms (mẻ p1, câu "over my."); nó ở lại trong bảng và kéo cột
`max`, nhưng nó không phải là 5 % đuôi của một phân phối trơn — nó là một điểm rời hẳn.
p95 = 352 ms là số đáng dùng; 1 466 ms là số đáng đi tìm nguyên nhân.

**Chặng lên có hai cụm.** 19 giá trị nằm trong 99,9–212,9 ms, rồi ba giá trị 332,9 /
334,9 / 337,2 ms đứng riêng — mà 337 ms lại sát trần cửa sổ ghép (350 ms). Ba giá trị
ấy **có thể là ghép nhầm chứ không phải chặng lên thật**, và tôi không có cách phân biệt
từ dữ liệu này. Chúng ở lại trong bảng, nhưng **bỏ hay giữ ba giá trị ấy đổi CẢ HAI phân
vị**, không phải chỉ p95:

| bộ | n | p50 | p95 |
|---|---|---|---|
| tất cả | 22 | 177,8 | 334,9 |
| bỏ cụm cao (< 250 ms) | 19 | **164,0** | **207,2** |

Nên ai trích dòng "chặng lên" phải nói rõ đang trích bộ nào. Bảng 2b và bảng 3 dùng
**bộ tất cả (n = 22)**, vì loại ba điểm ấy là một quyết định không có căn cứ từ dữ liệu
— chỉ có căn cứ từ việc chúng trông không giống phần còn lại, mà đó không phải căn cứ.

Cận dưới 99,9 ms có ý nghĩa vật lý và nó là một kiểm tra tốt: một khung Opus dài **60 ms**
và server chỉ nhận được nguyên khung, nên khung CHỨA tiếng kích thích không thể tới sớm
hơn 60 ms sau khi tiếng ấy vang lên. Cộng AFE trên board và Wi-Fi thì 100–210 ms là đúng
tầm. Chính vì vậy mẻ 22:24 cho ra "12,1 ms" đã bị loại: nó không thể đúng.

## Bảng 3 — cộng vào baseline

| | laptop-only (baseline v3) | + sàn thiết bị | tổng |
|---|---|---|---|
| e2e p50 | 5 129 ms | **526 ms** | **5 655 ms** |
| e2e p95 | 7 649 ms | 654 ms | *(xem cảnh báo)* **8 303 ms** |

> **Dòng p95 là một CẬN TRÊN THÔ, không phải p95 của tổng.** p95 của một tổng không bằng
> tổng hai p95 trừ khi hai thành phần đạt đuôi cùng lúc — mà ở đây chúng độc lập: đuôi
> của pipeline là LLM nghĩ lâu, đuôi của thiết bị là Wi-Fi vấp. Muốn p95 thật của tổng
> thì phải đo tổng, không phải cộng hai bảng. Dòng p50 thì cộng được: trung vị của tổng
> hai đại lượng độc lập gần bằng tổng hai trung vị khi cả hai đều lệch nhẹ.

Ba điều rút ra, và điều thứ hai là điều bất ngờ:

1. **Sàn thiết bị là 526 ms — cỡ 10 % của e2e.** Nó không đổi được bằng cách tối ưu
   STT/LLM/TTS, vì nó nằm ngoài cả ba.
2. **Chặng XUỐNG đắt gấp rưỡi chặng LÊN** (299 so với 198 ms). Trước khi đo tôi đã đoán
   ngược lại: chặng lên phải gánh mã hoá Opus và một khung 60 ms, còn chặng xuống thì
   "chỉ có giải mã". Đoán sai. Board giữ một quãng đệm trước khi cho I2S chạy, và quãng
   đệm ấy — chứ không phải giải mã — là khoản lớn nhất của cả sàn thiết bị.
3. **Con số này đo được vì `t_rx_first` KHÔNG phải là nó.** `t_rx_first` (130–133 ms) là
   chi phí board dựng đường audio sau `listen start`, đo được từ xa. Chặng lên/xuống ở
   bảng 2b là chi phí của một lượt nói đã chạy, và không mốc nào phía server nhìn thấy
   nó. Hai con số khác nhau; đừng thay cái này bằng cái kia.

`t_rx_first` của mẻ 10/09: **p50 130,3 ms, p95 139,9 ms** (25 Turn) — lần xác nhận thứ
ba, sau 133,4 (06/09) và 132,3 (09/09), trên ba cấu hình mạng và ba loại kích thích khác
nhau. 130 ms là hằng số của board.

## Mẻ 09/09/2026 — bảng 1 đo lại được, bảng 2 thì KHÔNG, và vì sao

Định lấy 20 lượt sạch bằng cách phát 20 tiếng click cách nhau 7 giây. Ra 48 lượt, 44
lượt dùng được. Nhưng đọc mốc thời gian thì **phần lớn không phải click của tôi**:

    22:03:43 cách  3,0s  audio 780 ms  rms đỉnh 443
    22:03:46 cách  3,0s  audio 780 ms  rms đỉnh  74
    22:03:49 cách  3,0s  audio 840 ms  rms đỉnh 661
    22:03:51 cách  2,0s  audio 780 ms  rms đỉnh 579

Click cách nhau **7 giây**, lượt lại đẻ ra mỗi **2–3 giây**, và `audio_ms` gần như hằng
số 780 ms. Phân loại 48 lượt: **39 lượt** dài 780 ms với RMS đỉnh 300–670, **8 lượt**
im (RMS < 200), **1 lượt** còn lại.

**Board đang tự kích hoạt bằng chính tiếng nó vừa phát.** Server trả tone 880 Hz →
loa board kêu → mic board nghe lại → VAD nổ → server lại trả tone. Vòng lặp tự nuôi
nhau, chu kỳ 2–3 giây.

Về sau tôi đặt âm lượng board lên 85 để chuẩn bị cho loopback, và vòng lặp thành ồn
thật sự — RMS đỉnh nhảy từ ~500 lên **15 000–22 500**, board kêu "te te te" liên tục
cho tới khi tắt server. Chủ nhân nghe thấy trước khi tôi đọc log.

### Tôi đã viết SAI một câu, sửa ở đây

`PROTOCOL.md` §B và `bench_loopback.py` từng viết: *"`tone` không có rủi ro đó: âm ra
không phụ thuộc âm vào."* **Nửa đúng, và nửa sai là nửa quan trọng.**

- Đúng: `tone` không **khuếch đại** — biên độ không lớn dần qua mỗi vòng như `echo`.
- Sai: `tone` vẫn **tự kích hoạt lại**. Không cần khuếch đại; chỉ cần tiếng loa vượt
  ngưỡng VAD của mic là vòng lặp chạy mãi ở biên độ không đổi.

Gốc rễ vẫn là ES8311 **không có kênh tham chiếu** nên **AEC chưa từng chạy**
(ADR-013 §10.2) — cùng một nguyên nhân, chỉ khác cách biểu hiện. Ngưỡng an toàn là
**âm lượng board**, không phải chế độ trả lời.

### Hệ quả cho giao thức loopback: KHÔNG được ghép click với lượt theo thứ tự

`bench_loopback.py` ghép theo thứ tự, giả định *mỗi click sinh đúng một lượt*. Giả định
ấy vừa bị chính dữ liệu này bác. Ghép theo thứ tự trong lúc board tự kích hoạt sẽ cho
ra một bảng số **trông rất bình thường và sai toàn bộ** — mỗi Δ ghép nhầm với một lượt
của tiếng tone trước đó.

Nên trước khi chạy việc 16 phải chặn vòng lặp. Đã thêm `--cooldown-ms` cho
`device_server.py`: trong khoảng ấy sau khi phát xong, server **không trả lời** lượt
mới (vẫn ghi log, vẫn đánh dấu `cooldown: true`). Mặc định **0**, giữ nguyên hành vi cũ.

### Cái mẻ này VẪN đo được — vì nó không phụ thuộc kích thích

`t_rx_first` là quãng từ lúc `listen start` tới khung Opus đầu tiên đến server. Nó là
chi phí board **dựng đường audio**, không phụ thuộc âm thanh nào đã kích hoạt lượt. Và
dữ liệu xác nhận đúng thế:

| nhóm lượt | n | `t_rx_first` p50 | p95 |
|---|---|---|---|
| tự kích hoạt bằng tone (780 ms, RMS > 200) | 39 | **132,3 ms** | 141,8 ms |
| lượt im (RMS ≤ 200) | 8 | **131,1 ms** | 145,2 ms |
| tất cả | 48 | **132,2 ms** | 145,2 ms |

Hai nhóm sinh ra bởi hai thứ hoàn toàn khác nhau mà lệch **1,2 ms**.

### Bảng 1 — mạng, đo lại trên mạng MỚI (44 lượt, một phiên liền mạch)

| | mẻ 06/09 (47 lượt) | **mẻ 09/09 (44 lượt)** |
|---|---|---|
| đường mạng | board → **router** → laptop, LAN 192.168.1.x | board → **hotspot của chính laptop**, 192.168.137.x |
| RTT ping/pong p50 | 32,4 ms | **4,65 ms** |
| RTT ping/pong p95 | 157,8 ms | **109,2 ms** |
| jitter khung Opus p50 / p95 | 6,1 / 13,3 ms | **5,79 / 9,99 ms** (max 10,29) |
| lỗi giải mã Opus | 0 | **0** |
| cỡ khung Opus min/median/max | 132 / 146 / 173 byte | **146 / 146 / 147 byte** |
| `t_rx_first` p50 / p95 | 133,4 / 166,0 ms | **132,3 / 141,9 ms** |

**RTT p50 xuống 7 lần vì bỏ một chặng router**, không phải vì phần mềm khá lên. Đây là
số của **cấu hình triển khai**: chỗ đặt board so với đường mạng đáng giá hơn mọi tối ưu
ở tầng giao thức. Nhưng p95 vẫn 109 ms — đuôi dài không mất đi cùng cái router.

**`t_rx_first` 133,4 → 132,3 ms** qua hai mạng, hai kích thích, hai chế độ trả lời. Đây
là bằng chứng mạnh nhất trong tài liệu này rằng 133 ms là hằng số của **board**.

**Cỡ khung siết còn 146/146/147** so với 132/146/173. CBR vẫn là CBR; dao động cũ đến
từ giọng người lúc im lúc to. Củng cố lý do VAD theo cỡ khung không bao giờ chạy được.

### Bảng 2 — vẫn CHƯA đo lại được, và không được lấy số của mẻ này

Bảng 2 nói về **một lượt nói**: thời lượng thu, server quay đầu, mic → loa. Mẻ này gồm
toàn lượt do máy tự kích hoạt, nên:

- `t_rx_last − t_rx_first` p50 = 730 ms **không phải** thời lượng một câu nói. Nó là
  6 ms tone lọt vào + 700 ms `SILENCE_END_MS` + một khung. Đúng bằng quãng VAD ngồi
  chờ, không hơn.
- `t_tx_first − t_dev_vad_end` p50 = **10,2 ms** (p95 12,5) so với 0,5 ms của mẻ echo.
  Đây **không phải hồi quy**: `tone` phải sinh và mã hoá 1,5 giây Opus mỗi lượt
  (`tone_frames()` gọi mới, không cache), còn `echo` chỉ đẩy lại khung có sẵn. 10 ms
  ấy là chi phí của **dụng cụ đo**, và nó không tồn tại ở chế độ `pipeline`.
- **mic → loa**: vẫn trống. Cần mic ngoài, xem "Loopback vật lý".

Muốn bảng 2 thật thì phải chạy lại với `--cooldown-ms` bật và **người nói thật**, hoặc
ít nhất một kích thích không phải do chính board sinh ra.

Nguồn số: `desktop/logs/device_floor.jsonl` từ mốc byte 31221.

## Vì sao chặng xuống chưa có số

Loa **có kêu** — nhưng phải mất gần cả buổi mới ra, vì hai lỗi chồng lên nhau. Ghi lại
vì cách chẩn đoán sai còn đáng nhớ hơn kết luận:

| giả thuyết | cách loại | kết quả |
|---|---|---|
| tín hiệu vọng lại quá nhỏ để nghe | server tự sinh âm 880 Hz, biên độ 50 % toàn thang | vẫn câm |
| âm lượng board bằng 0 | hỏi board qua MCP `self.get_device_status` | board khai **70** |
| `pa_inverted` sai chiều | **đọc BSP** — `AMP_EN | IO1 | active low` | **đúng là lỗi**, phải để `true` |
| board không nhận được audio | log firmware + `t_tx_first` | board vào `speaking`, nhận đủ khung |
| nguồn/màn hình hỏng | MCP: pin 92 %, màn sáng 100, Wi-Fi khoẻ | lành |

**Hai lỗi thật, và vì sao chúng che nhau suốt buổi:**

1. **`pa_inverted` sai chiều.** BSP ghi `AMP_EN | IO1 | active low`, nên phải để `true`.
   Tôi đổi thành `false` vì đếm thấy 40 board ES8311 khác đều để `false` — đếm phiếu thay
   cho đọc sơ đồ, trong khi chính `config.h` của tôi ghi BSP là nguồn sự thật.
2. **Monitor nối tiếp giữ mất nút BOOT.** Trên USB-Serial/JTAG, DTR của máy tính ánh xạ
   vào GPIO0 — đúng chân nút. Monitor bật thì bấm nút không ăn, log trống trơn, trông
   hệt như board hỏng.

Che nhau thế này: lần flash đầu cực **đúng**, nhưng server chỉ vọng lại giọng người ở
−38 dBFS — gần như không nghe được. Đến khi tôi làm âm thanh to lên (âm chuẩn, rồi nhạc)
thì cực đã bị lật **sai**. Khi cực đúng trở lại thì monitor chặn mất nút. Ba vòng flash,
mỗi vòng đổi một biến, mà không vòng nào có đủ hai điều kiện cùng lúc.

Bài học rẻ nhất trong đây: **loa kêu được thì lúc khuếch đại bật sẽ có tiếng "bụp" nhỏ.**
Đó là dấu hiệu đầu tiên đáng tin, và nó đến trước cả khi có audio. Nghe thấy nó nghĩa là
loa nối đúng và cực đúng — không cần đoán thêm.

## Chế độ `pipeline` — mốc thời gian và định nghĩa e2e

**Đọc mục này trước khi so số của board với baseline v3.** Từ 07/09 `device_server.py`
có `--reply pipeline`: khung Opus của board đi thẳng vào `queues["mic"]` của **đúng
pipeline mà console web dùng** (`PipelineBridge`, dùng lại `WebAudioStreamer`), và audio
TTS đi ngược ra thành Opus 24 kHz. Không có handler nào viết riêng cho board — cố ý, vì
hai đường thoại lệch nhau một chỗ là hai bộ số hết so được.

Bản ghi latency vẫn là `desktop/logs/latency.jsonl` (đổi được bằng `--latency-log`), gắn
`source="device"`, kèm **năm** trường của chặng thiết bị:

| trường | gốc đếm | nghĩa |
|---|---|---|
| `t_dev_rx_first` | VAD pipeline chốt câu | khung Opus **đầu** của lượt tới server — **âm**, vì nó xảy ra trước khi người ta nói xong |
| `t_dev_vad_end` | VAD pipeline chốt câu | lúc **server** cho rằng người nói đã dứt lời |
| `t_dev_tx_first` | VAD pipeline chốt câu | byte Opus **đầu tiên** rời server |
| `e2e_device_ms` | — | `t_dev_tx_first − t_dev_vad_end` — **con số để so** |
| `device_out_rate` | — | tốc độ mẫu server phát cho board (24 000) |

Bốn mốc kia (`t_stt`, `t_llm_first`, `t_tts_first`, `t_audio_out`) giữ nguyên ý nghĩa cũ,
gốc đếm cũng vẫn là `t_vad_end` của pipeline — nên **cột e2e của bảng baseline v3 so
thẳng được với `end_to_end_ms` của dòng `source="device"`**.

### Vì sao e2e của thiết bị đếm từ `t_dev_vad_end` chứ không phải khung cuối

Ở giai đoạn echo hai thứ này là một: server trả lời ngay tại khung làm VAD nổ, nên "khung
cuối nhận được" cũng chính là "lúc server thấy dứt lời". Ở chế độ pipeline thì **không**:
board chỉ tắt mic khi nó vào trạng thái Speaking, tức là mãi tới lúc ta gửi `tts start`.
Trong suốt mấy giây vịt nghĩ, board **vẫn gửi khung đều đặn**, nên `t_rx_last` trôi theo
tới tận lúc ta bắt đầu nói — lấy nó làm gốc thì e2e ra gần bằng **0**, một con số đẹp đẽ
và hoàn toàn vô nghĩa.

Nên `Turn.mark_speech_end()` **đóng băng** mốc ấy ở khung cuối tại thời điểm VAD nổ, và
`t_dev_vad_end` đọc từ chỗ đóng băng đó. Định nghĩa không đổi so với bảng 2 — vẫn là "dứt
lời, nhìn từ server" — chỉ có chỗ đọc là phải giữ lại. Hệ quả cần nhớ khi đọc log:
`t_dev_vad_end < t_rx_last` ở mọi lượt chế độ pipeline, và khoảng cách giữa hai cái chính
là thời gian vịt nghĩ.

Mốc này **vẫn cõng 700 ms** im lặng của `SILENCE_END_MS` — VAD phải chờ chừng ấy mới dám
kết luận. Bảng 2 cũng cõng đúng khoản đó, nên hai bên so được với nhau; nhưng đừng đọc
`e2e_device_ms` như "độ trễ người nghe cảm nhận". Cái đó là `perceived_silence_ms`.

### Cái vẫn chưa đo được

`t_dev_ack` **vẫn rỗng**, vì firmware v2.3.0 vẫn không báo ngược. Nên `e2e_device_ms` dừng
ở **lúc byte rời server**, chưa gồm Wi-Fi chiều xuống + board giải mã + I2S đẩy ra loa.
Muốn con số đầy đủ thì vẫn phải làm loopback vật lý ở mục "Việc còn lại".

### Bẫy đã sập ở chặng này — libopus luôn giải ra 48 kHz

`OpusEnergyVad` đặt `sample_rate = 16000` cho bộ giải mã, và **FFmpeg lờ nó đi**: libopus
giải mã luôn luôn ở 48 kHz, một khung 60 ms ra **2880 mẫu** chứ không phải 960.

Suốt giai đoạn echo không ai thấy, vì chỗ duy nhất dùng PCM là RMS — mà RMS không phụ
thuộc tốc độ mẫu, nên VAD phía server vẫn chạy đúng và log vẫn sạch. Nối vào pipeline thì
cùng dòng PCM ấy chảy vào mic 16 kHz: giọng **nhanh gấp ba**, STT chép ra rác, và không
có một dòng log nào chỉ vào codec. Đã sửa bằng `AudioResampler` trong `decode()`; bài test
`test_giai_ma_opus_ra_dung_toc_do_da_khai` giữ lại cái bẫy.

Bài học cùng họ với `pa_inverted`: **thư viện không hứa làm theo thuộc tính ta gán.** Đo
số mẫu ra một lần là xong, rẻ hơn nhiều so với đi nghi ngờ model STT.

## Giới hạn của phép đo — đọc trước khi trích dẫn

1. **`clock_offset_ms` là nửa RTT, KHÔNG phải lệch đồng hồ thật.** Protocol v1 của
   xiaozhi không mang timestamp của board (v2 có, xem `BinaryProtocol2`), nên không có
   cách đo lệch tuyệt đối. Nửa RTT là **mốc dưới** của độ trễ một chiều, đủ để quy các
   mốc về cùng một trục, không đủ để nói "board chậm hơn server X ms".
2. **`t_dev_ack` rỗng ở cả 47 lượt — đã xác nhận, không còn là phỏng đoán.** Firmware
   v2.3.0 không gửi `tts state=start` ngược lên. Chặng cuối (giải mã + đẩy ra loa trên
   board) **không đo được từ xa** — muốn số thật thì phải đo bằng loopback vật lý (thu
   tiếng loa bằng mic thứ hai), đúng như "protocol đo" còn nợ ở `docs/baseline/README.md`.
   Mà loopback vật lý cũng chính là phép thử sẽ trả lời luôn câu hỏi cái loa.
3. **Wi-Fi không phải hằng số.** Đo lúc mạng rảnh và lúc mạng bận cho hai kết quả khác
   nhau; ghi kèm điều kiện, và đo ít nhất 20 lượt trước khi tin p95.
4. **Board và laptop phải cùng mạng LAN.** Qua Tailscale hay hotspot điện thoại thì số
   không so được với lần đo trước.

## Đo chặng xuống bằng mic thứ hai (10/09/2026) — cách làm và sai số

**Đọc mục này trước khi trích bảng 2b hay bảng 3.**

Dụng cụ: `desktop/scripts/bench_devout.py`. Dữ liệu thô:
`docs/benchmark/devout_20260910_p{1,2,3}.json` (từng lượt),
`docs/benchmark/device_floor_20260910_v1.jsonl`,
`docs/benchmark/latency_es3c28p_20260910_v1.jsonl`.

### Bố trí

Laptop phát 10 câu bài test qua loa của nó cho board nghe bằng mic của board; board chạy
`--reply pipeline` nên nó đáp bằng giọng thật ra loa của nó; **mic laptop thu suốt buổi**.
Kích thích là **giọng chủ nhân**, lần thu đầu của mỗi câu trong bộ 31 lượt ngày 06/09
(`logs/utts/20260906_134002_*.wav`) — cùng bộ audio của bảng WER desktop, nên không phải
cãi nhau về "giọng khác thì khác".

Mỗi câu ghép thêm một tiếng **click** 6 ms (ồn trắng lọc thông cao) đặt trước câu nói
**50 ms**. Click làm mốc: sườn lên của nó sắc tới một mẫu, còn giọng người lên biên độ
thoai thoải qua cả trăm ms.

### Hai đồng hồ, và vì sao chúng so được với nhau

Máy ghi âm và server là hai tiến trình khác nhau. Nhưng trên Windows `time.perf_counter()`
là `QueryPerformanceCounter`, **chung một gốc cho mọi tiến trình** — đo trên chính máy
này: ba tiến trình đọc lệch nhau dưới 1 ms. Nên hiệu giữa mốc của server và mốc của máy
ghi âm là một hiệu trên MỘT đồng hồ, không phải hiệu của hai đồng hồ chưa đồng bộ.

Server được thêm ba mốc tuyệt đối cho việc này: `opened_at_perf_ms` và `onsets_perf_ms`
trong `device_floor.jsonl`, `tx_first_perf_ms` trong log latency.

### Ba chỗ mà cách làm này khác §B của `PROTOCOL.md` — và vì sao

**1. Mic laptop dùng được, nếu mở ở WASAPI EXCLUSIVE.** `bench_loopback.py` kết luận
"mic laptop không dùng được" vì AEC của Intel Smart Sound triệt tiêu đúng tiếng click.
Kết luận ấy đúng **cho chế độ shared** — và shared là mặc định của mọi thư viện âm thanh.
Chế độ **exclusive** đi thẳng vào endpoint, không qua chuỗi APO của Windows, mà AEC chính
là một APO. Đo được: exclusive mở ở **4 kênh 48 kHz** (1 và 2 kênh bị từ chối, 16 kHz
cũng vậy), độ trễ khai báo 20 ms. Tỉ số đỉnh/nền của click: **17 lần ở shared → 70–340
lần ở exclusive**, và 30/30 click nghe rõ qua ba mẻ. Không phải mic hỏng — là đường đi
tới mic có một bộ lọc mà ứng dụng không gọi và cũng không tắt được từ bên trong.

**2. Ghép theo ĐỒNG HỒ, không theo thứ tự.** §B ghép click thứ k với lượt thứ k và tự
ghi lại rằng phép ghép ấy đã sai một lần (20 click đẻ ra 48 lượt, bảng số "trông hoàn
toàn bình thường và sai từ dòng đầu"). Có mốc tuyệt đối rồi thì không cần: mỗi lượt trả
lời ghép với tiếng click gần nhất **trước** nó. Lượt thừa vẫn hiện ra nhưng không làm
lệch pha cả mẻ — chúng chỉ là những lượt không ghép được, và được đếm riêng.

**3. Chấm mốc "loa board bắt đầu kêu" bằng LỌC PHỐI HỢP, không bằng ngưỡng.** Server ghi
lại đúng dòng PCM nó đã gửi xuống (`--dump-tts`); `doc` trượt **đường bao** của dòng ấy
dọc đường bao file thu và lấy đỉnh tương quan. Đối chiếu đường bao chứ không phải dạng
sóng, vì giữa hai bên có một cái loa 8 Ω, một căn phòng, một cái mic và một vòng Opus —
pha thì chúng phá sạch, còn "to nhỏ theo thời gian" thì giữ gần nguyên.

Đây **không** phải chi tiết kỹ thuật vặt. Cùng dữ liệu, cùng lượt:

| cách chấm | p50 | p95 | min | max |
|---|---|---|---|---|
| lọc phối hợp | **319,0** | 352,0 | 257,0 | 1 466,0 |
| ngưỡng + thời gian giữ | 875,9 | 10 882,9 | 546,6 | 11 938,0 |

Cách ngưỡng cho số **lớn gấp gần ba** và tán loạn, vì nó đo "lúc tiếng vượt ngưỡng" chứ
không phải "lúc tiếng bắt đầu" — mà sườn lên của một câu TTS thì thoai thoải, và ngưỡng
thì phải chọn. Quét độ nhạy in kèm trong `bench_devout.py doc` cho thấy cách ngưỡng nhảy
615 → 1 910 ms chỉ vì đổi hai tham số dò; lọc phối hợp không có tham số nào như thế.

### Một chỗ suýt tự lừa mình, ghi lại vì nó rẻ

Ban đầu tôi loại mọi lượt có biên tương quan `bien < 1,25` với lý do "ghép không đủ rõ".
Đo ra thì hai lượt bị loại ấy có mốc **319 và 307 ms** — nằm gọn giữa cụm 295–352 ms của
những lượt được nhận. **Cái cổng ấy đang vứt đi số đúng**, chỉ vì đường bao giọng nói tự
nó có đỉnh phụ thật. Giờ `bien` là nhãn chẩn đoán, không phải cổng chặn, và bảng in cả
hai bộ — bỏ những lượt "ghép yếu" đi thì p50 đổi 319,0 → 323,0 ms, tức là không đổi.

### Sai số — bốn khoản, xếp theo độ lớn

1. **Lượng tử hoá khung Opus: ±60 ms, và đây là khoản lớn nhất.** Server chỉ nhìn thấy
   từng khung 60 ms nguyên vẹn, nên mọi mốc phía server đều bị làm tròn lên tới biên
   khung. Nó không lệch trung bình nhưng cộng thẳng vào phương sai của **chặng lên** —
   và giải thích phần lớn dải 100–213 ms của dòng ấy.
2. **`m`, độ trễ đường thu laptop: 20 ms khai báo, không đo trực tiếp được.** Nó vào
   chặng lên với dấu âm và chặng xuống với dấu dương. **Dòng "sàn thiết bị" của bảng 2b
   không phụ thuộc vào nó**; hai dòng kia thì có, và 20 ms là con số driver khai báo chứ
   không phải con số đo.
3. **Không có dao động ký.** Số ra là **chặn dưới để so tương đối**, không phải giá trị
   tuyệt đối. Khử ồn của Windows có thể NUỐT đỉnh, không thể DỜI nó sớm lên, nên sai số
   nghiêng về phía làm số XẤU đi, không phải đẹp đi.
4. **Đường loa→mic không phải người nói.** Xem "Cái mẻ này KHÔNG đo được" bên dưới.

### ⚠ Threat to validity — dấu thời gian phần mềm trên ESP32

Smelcerz và cs., *"Characterization of Latency Sources in a MicroPython-Based ESP32
Edge–Cloud Sensor Network"*, **Sensors 26(17):5555** (01/09/2026),
<https://www.mdpi.com/1424-8220/26/17/5555> — đo độ trễ trên chính họ ESP32 và cho thấy
dấu thời gian **lấy bằng phần mềm trên board** lệch cỡ **~12 ms** so với mốc lấy bằng
dao động ký.

Áp vào đây thì phải nói cho đúng chỗ, và chỗ ấy quan trọng:

- **Bảng 2b KHÔNG dùng một dấu thời gian nào của board.** Mọi mốc đều lấy trên laptop:
  mốc server (`perf_counter`) và mốc máy ghi âm (`perf_counter`). Board chỉ là vật thể
  vật lý phát ra tiếng. Nên sai số ~12 ms ấy **không vào bảng 2b**.
- **Nó SẼ vào nếu ta đi đường (b) — sửa firmware cho board tự báo "đã bắt đầu phát".**
  Đó là đường còn để ngỏ ở "Việc còn lại". Nếu sau này làm, con số nó cho sẽ cõng ~12 ms
  sai số hệ thống, và **jitter khung Opus của ta chỉ có 6,1–6,4 ms** — tức là **sai số
  của dụng cụ đo sẽ LỚN GẤP ĐÔI thứ nó định đo**. Ghi ra đây để lần sau không ai coi
  mốc firmware là "chính xác hơn vì nó ở gần nguồn hơn".
- Với chặng xuống 299 ms thì 12 ms là 4 %. Với jitter 6,1 ms thì 12 ms là 200 %. Cùng
  một sai số, hai kết luận trái ngược — nên phải nói nó áp cho đại lượng nào.

### Cái mẻ này KHÔNG đo được, nói trước cho khỏi ai trích nhầm

**Không được lấy transcript của mẻ 10/09 đi chấm WER.** Hai biến đã bị can thiệp:

1. Kích thích đi qua **loa laptop → không khí → mic board**, không phải người nói tại
   chỗ. Tới mic board nó chỉ còn **−20 tới −42 dBFS**, và ở mức ấy `gemini-audio` chép
   ra chuỗi RỖNG ở 4/7 lượt.
2. Nên server phải chạy `--mic-gain 9.0` — nhân biên độ PCM trước khi vào pipeline. Nhân
   biên độ **không dời mốc thời gian** nên mọi số độ trễ ở trên không bị nó động tới,
   nhưng mức tín hiệu thì đã là một biến bị can thiệp, và cắt đỉnh là một méo có thật.

Hệ quả nhìn thấy được: câu chép ra sai nhiều ("Anh tên là Đạt, làm ở [COMPANY]"
→ *"tên là Đạt và mở sân golf Mexico"*), và vịt phần lớn đáp lại bằng câu hỏi lại. Với
phép đo ĐỘ TRỄ thì không sao — vịt vẫn nói, loa vẫn kêu, mốc vẫn đúng. Với phép đo ĐỘ
CHÍNH XÁC thì mẻ này vô giá trị.

**Tỉ lệ có lượt: 20/30 câu** qua ba mẻ (7 + 8 + 5). Mười câu mất là do STT chép ra rỗng
nên pipeline không đáp — tập trung ở những câu ngắn nhất ("Ngắn thôi.", "Dừng."). Đây là
tỉ lệ của **bố trí đo**, không phải tỉ lệ của sản phẩm.

### Nhịp phát phải theo TÍN HIỆU, không theo đồng hồ — một lỗi đã làm hỏng hai mẻ

Ở `mode=auto` board **tắt mic suốt lúc nó nói**. Ô cố định 25 giây làm mất **6 trong 10**
kích thích: chúng rơi đúng vào lúc board đang đáp câu trước.

Sửa bằng cách chờ hai pha: chờ vịt **bắt đầu** nói đã, rồi mới chờ nó **im**. Chỉ chờ
cho-tới-khi-im là chưa đủ và đã hỏng thêm một mẻ nữa: ngay sau khi phát xong câu hỏi thì
phòng ĐANG im thật — vịt còn đang nghĩ. Vòng chờ cũ thấy im ở giây thứ 6 liền phát câu
kế, và cả 10 câu đều báo "xong sau 3,9 s" trong khi e2e nhanh nhất đo được là 4,0 s
**chưa kể** thời gian vịt nói.

Kèm theo hai chi tiết nhỏ mà thiếu là hỏng: ngưỡng "đã im" phải lấy **trong dải
300–3400 Hz** (RMS băng rộng của phòng im là 0,0031, còn trong dải giọng nói chỉ 0,00044
— chênh 7 lần, toàn ù tần số thấp; lấy ngưỡng trên số băng rộng thì nó nằm cao hơn cả
tiếng loa board), và phải có một chắn cứng 3 giây sau khi phát xong, không thì nó rình
phải đuôi vang của chính mình.

## Ghi chú cũ: loopback vật lý (09/09/2026)

Ô "mic → loa" của bảng 2 và cả bảng 3 **không còn bị chặn vì thiếu mic thứ hai**. Một
điện thoại ghi âm đặt cạnh board là mic thứ hai hợp lệ; mic laptop cũng vậy, và nó tự
động hoá được nên lặp được nhiều lần — mà số lần lặp mới là thứ quyết định p95 có đáng
tin không.

**Điểm mấu chốt của phương pháp:** một file ghi âm duy nhất chứa CẢ tiếng kích thích
LẪN tiếng board đáp, nên khoảng cách giữa hai đỉnh là một hiệu đo trên CÙNG một đồng
hồ — không có sai số đồng bộ nào để mà cãi. Giao thức đầy đủ ở `PROTOCOL.md` §B; cài
đặt ở `desktop/scripts/bench_loopback.py`.

Server đã có thêm mốc phép đo ấy cần: **`t_rx_speech_first`** — khung Opus đầu tiên
CÓ TIẾNG, tính từ lúc mở lượt. Không phải `t_rx_first`: ở `mode=auto` board phát liên
tục nên khung đầu của lượt thường là khung im, và khoảng cách giữa hai mốc là quãng
chờ người ta mở miệng. Trừ nhầm mốc là cộng cả quãng chờ ấy vào chặng xuống.

    Δ_vòng      hiệu hai đỉnh trong file thu — mic → server → loa, ĐỦ CẢ VÒNG
    Δ_server    t_tx_first − t_rx_speech_first (cõng cả 700 ms SILENCE_END_MS)
    Δ_còn lại   Δ_vòng − Δ_server = chặng lên + chặng xuống
    chặng lên   ước lượng: nửa khung Opus (30 ms) + rtt_p50/2
    chặng xuống Δ_còn lại − chặng lên   ← ô còn trống của bảng 2

**Vì sao board "không lên mạng" tối 09/09 — chẩn đoán đầu tiên đã SAI.**
Chẩn đoán ban đầu là "board chưa bắt được Wi-Fi, nghi 2,4 GHz". Nguyên nhân thật rẻ hơn
nhiều: firmware `SeedWifiCredentials()` ghi cứng SSID **`microduck`** vào NVS và
`CONFIG_OTA_URL` trỏ **192.168.137.1** (SESSION-06), tức board **chỉ** đi được qua
Mobile Hotspot của laptop — mà hotspot đang tắt. Bật lại hotspot là board vào trong
vài chục giây.

Ba bằng chứng loại hẳn giả thuyết băng tần: (a) `netsh wlan show networks` thấy
`PhucMinh` là **2,4 GHz**, board thừa sức bắt; (b) không có AP `Xiaozhi-*` nào phát,
nên board **không** rơi vào chế độ cấu hình; (c) đọc console COM5 thấy board boot bình
thường, `State: activating -> idle`, WakeNet `wn9_hijolly_tts2` đã nạp, màn 24,6 fps.

Bẫy đi kèm, đã có trong project memory: **Mobile Hotspot tự tắt** sau vài phút không
có máy nào nối. Tắt cái timeout ấy cần sửa
`HKLM\...\icssvc\Settings\PeerlessTimeoutEnabled`, mà máy này không có quyền admin.
Nên phải bật hotspot **rồi đánh thức board ngay**, đừng bật xong đi làm việc khác.
Board nối rồi thì hotspot ở yên.

Đánh thức board tự động được: tổng hợp "Hi Jolly" bằng Kokoro rồi phát qua loa laptop
(đúng đường `bench_wakeword.py` dùng). WakeNet trên board bắt được và nó mở WebSocket.

**Cấm dùng `--reply echo` cho phép đo này** — và `tone` cũng KHÔNG miễn nhiễm. AEC
chưa từng chạy trên board (ES8311 không có kênh tham chiếu, ADR-013 §10.2). `echo` phát
lại đúng cái mic vừa nghe nên vòng lặp vừa tự nuôi vừa **lớn dần**; `tone` không lớn
dần nhưng vẫn **tự kích hoạt lại** ở biên độ không đổi, đo được 09/09 (xem trên). Phải
chạy với `--cooldown-ms` đủ dài (≥ 3 000 với tone 1,5 s) và âm lượng board vừa đủ để
mic ngoài nghe thấy.

## Việc còn lại

1. ~~Điền ô **mic → loa** của bảng 2 và bảng 3~~ — **xong 10/09** bằng
   `bench_devout.py`, không phải `bench_loopback.py`: xem "Đo chặng xuống bằng mic thứ
   hai". Bảng 2b và bảng 3 đã có số.
2. ~~Đo lại bảng 1 trong một phiên Wi-Fi liền mạch~~ — **xong 09/09**, 44 lượt một
   phiên, RTT p50 4,65 ms / p95 109,2 ms. Xem "Mẻ 09/09/2026".
3. **Một lượt ra 1 466 ms mà không rõ vì sao** (mẻ p1, câu "over my."). 17 lượt kia nằm
   trong 257–352 ms. Nghe lại `logs/devout_v2_p1/thu.wav` quanh mốc ấy trước khi đoán —
   nhiều khả năng là một cú vấp Wi-Fi, nhưng "nhiều khả năng" không phải là một kết luận.
4. **Chặng xuống 299 ms là của cái gì trong board?** Đã biết nó KHÔNG phải giải mã (giải
   mã Opus 60 ms trên S3 tốn cỡ ms). Nghi quãng đệm trước khi I2S chạy. Đo được bằng cách
   đọc log firmware quanh `ResetDecoder` — rẻ, và nó biến một con số thành một lời giải
   thích.
5. **Đo lại với người nói thật, không qua loa.** Mẻ 10/09 phải bật `--mic-gain 9.0` và
   transcript hỏng vì thế. Số ĐỘ TRỄ không bị ảnh hưởng, nhưng một mẻ có người nói sẽ bỏ
   được cả `--mic-gain` lẫn dòng cảnh báo đi kèm nó.
6. **Đường (b) — sửa firmware cho board báo ngược mốc "đã bắt đầu phát"** vẫn để ngỏ.
   Đọc mục threat-to-validity trước: mốc ấy sẽ cõng ~12 ms sai số hệ thống, gấp đôi
   jitter 6,1 ms của ta. Nó cho biết chặng xuống vỡ ra thành những phần nào (Wi-Fi /
   đệm / I2S) — cái mà mic thứ hai không thấy được — chứ không cho một con số tổng
   chính xác hơn.
