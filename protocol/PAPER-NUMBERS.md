# PAPER-NUMBERS — mọi con số sẽ vào bài, và file gốc của nó

Ngày: 10/09/2026. **Chủ nhân viết chữ từ bảng này.**

Quy tắc của bảng này, không có ngoại lệ:

> **Số nào không truy được về một file trong `docs/benchmark/` hoặc `docs/baseline/`
> thì KHÔNG được vào bài.**

Cột **nguồn** ghi đường dẫn thật. Chỗ nào nguồn nằm ngoài hai thư mục ấy thì đánh dấu
**⚠ NGOÀI PHẠM VI** và số đó **không được trích** cho tới khi file được đưa vào — danh
sách đầy đủ ở **Mục 7**.

**Quy ước phân vị** của cả bài: `_pct(v, q) = sorted(v)[round(q·(n−1))]` — phân vị gần
nhất, **không nội suy** (`desktop/scripts/bench_latency.py::_pct`; `bench_loopback.py::pxx`
giống hệt). Chênh lệch không nhỏ: trên baseline v3 (n = 90), p95 của `end_to_end_ms` là
**7 649 ms** theo quy ước này và **7 534 ms** nếu nội suy tuyến tính — **lệch 115 ms**.

**Và ghi kèm LÁT CẮT HÀNG cạnh mỗi con số.** Việc 29a cho thấy lát cắt là nguồn sai
**nguy hiểm hơn** quy ước phân vị — nhưng phải so **theo tỉ lệ**, vì hai thứ đo hai đại
lượng khác nhau và so bằng mili giây thì vô nghĩa:

| nguồn sai | biên độ | trên nền | **theo tỉ lệ** |
|---|---|---|---|
| lát cắt hàng (device floor, p50 130,1–138,3 ms) | 8,2 ms | ~133 ms | **6,2 %** |
| quy ước phân vị (baseline v3, p95 7 649 vs 7 534) | 115 ms | 7 649 ms | **1,5 %** |

⇒ lát cắt nguy hiểm **gấp khoảng bốn lần**, theo tỉ lệ. (8,2 ms *nhỏ hơn* 115 ms về số
tuyệt đối — đó chính là lý do phải so tỉ lệ chứ đừng so thẳng.)

---

## 1. Bảng 1 — khung ba tầng

| # | số | giá trị | n | KTC 95 % | nguồn |
|---|---|---|---|---|---|
| 1 | `t_rx_first` p50 / p95 (mẻ 06/09) | 133,4 / 166,0 ms | 47 lượt | — | **`[TRUY ĐƯỢC]`** `docs/benchmark/device_floor_20260906_v1.jsonl` — xem §1b |
| 1 | RTT ping/pong p50 / p95 (mẻ 06/09) | 32,4 / 157,8 ms | 47 lượt | — | **`[TRUY ĐƯỢC]`** như trên |
| 1 | `t_rx_first` p50 / p95 (mẻ 09/09, mạng khác) | **131,6** / 143,7 ms | 59 lượt | — | **`[TRUY ĐƯỢC]`** `docs/benchmark/device_floor_20260909_v1.jsonl` — xem §1c |
| 1 | RTT p50 (mẻ 09/09) | 4,65 ms — **hằng số trong phiên** | 59 lượt | — | **`[TRUY ĐƯỢC]`** như trên |
| 1 | lệch hai nhóm kích hoạt | **1,1 ms** (132,2 so với 131,1) | 47 vs 12 lượt | — | **`[TRUY ĐƯỢC]`** như trên |
| 2 | STT: câu cho ≥2 transcript khác nhau qua 3 vòng | **1/10 → 0/10** | 10 câu × 3 vòng | — | **`[TRUY ĐƯỢC]`** `stt_determinism_20260910_v2.jsonl` — xem §3b |
| 2 | STT: `t_stt` p95 khi ghim `temperature=0` (`base`) | 2 506,9 → 1 494,3 ms = **−40,4 %** | 30 / 30 | — | **`[TRUY ĐƯỢC]`** như trên · phân vị gần nhất · lát cắt: cả 3 vòng |
| 3 | LLM ngôn ngữ trả lời | **`[BỎ]` — dòng giữ lại trong Bảng 1 nhưng KHÔNG mang số** | — | — | thô không còn; xem §4b và Hạn chế 14 |
| 4 | định tuyến nhất quán, `temperature=0` | 100/100 câu | 1 000 lượt | cận trên tỉ lệ lật ≈ 0,3 % (quy tắc ba) | `docs/benchmark/lookup_determinism_20260909_v1.jsonl` |
| 4 | định tuyến nhất quán, `temperature=0,8` | 87/100 câu; flip rate 3,30 % | ~1 000 lượt | — | như trên |
| 5 | lịch sử: sau-3-không-tra vs sau-3-có-tra | 93,0 % vs 78,0 %; z = +3,012; **p = 0,0026** | 100 / 100 | Wilson từng ô ở Mục 5 | `docs/benchmark/lookup_history_20260909_v1.jsonl` |
| 6 | grounding: đổi **tập tên miền** | 15/21 = **0,710** | 21 câu có tra | Wilson 0,50–0,86 | `grounding_stability_20260909_run1.jsonl` × `..._20260910_run2.jsonl` |
| 6 | grounding: Jaccard tên miền trung bình | **0,51** | 21 | — | như trên |
| 6 | **đối chứng** — quyết định *có tra hay không* đổi | **0/30** | 30 | — | như trên |

### 1b. Mẻ 06/09 — `[TRUY ĐƯỢC]`, tái lập 100 %

File thô: **`docs/benchmark/device_floor_20260906_v1.jsonl`** (128 bản ghi, chép nguyên
vẹn từ `desktop/logs/device_floor_20260906_lansuadau.jsonl`).

**Lát cắt** — đúng câu DEVICE-FLOOR đã ghi, *"47 lượt có phát lại, trong 57 lượt ghi
được"*: lấy **57 bản ghi đầu file**, giữ lượt có `t_tx_first` khác rỗng → **đúng 47 lượt**.

**Quy ước phân vị:** `pxx()` của `bench_loopback.py` — `sorted(v)[round(q·(n−1))]`, phân
vị gần nhất, không nội suy. Giống hệt `_pct()` của `bench_latency.py`.

Tính lại toàn bộ, **mọi con số khớp**:

| số | DEVICE-FLOOR | tính lại | |
|---|---|---|---|
| `t_rx_first` p50 / p95 | 133,4 / 166,0 | 133,40 / 166,00 | ✓ |
| RTT ping/pong p50 / p95 / max | 32,4 / 157,8 / 157,8 | 32,37 / 157,80 / 157,80 | ✓ |
| RTT phiên tốt nhất | 22,3 | 22,28 | ✓ |
| jitter khung Opus p50 / p95 / max | 6,1 / 13,3 / 59,9 | 6,06 / 13,34 / 59,94 | ✓ |
| cỡ khung Opus min/median/max | 132 / 146 / 173 | 132 / 146 / 173 | ✓ |
| lỗi giải mã Opus (38 lượt có giải mã) | 0 | 0, trên đúng 38 lượt | ✓ |
| `t_rx_last − t_rx_first` p50 / p95 | 2 643,6 / 14 948,8 | 2 643,60 / 14 948,80 | ✓ |
| `t_tx_first − t_rx_last` p50 / p95 | 0,5 / 9,0 | 0,50 / 9,00 | ✓ |
| `t_dev_ack` rỗng | 47/47 | 47/47 | ✓ |

**Bài học của lần khảo cổ này, đáng ghi vào Phương pháp:** ba lần đầu tôi tính ra số
lệch hẳn và suýt kết luận "dữ liệu không khớp". Cả ba lần nguyên nhân là **lát cắt
hàng**, không phải dữ liệu: nhầm file (log đã xoay vòng, `device_floor.jsonl` hiện tại
không còn bản ghi nào của 06/09), rồi nhầm bộ lọc. Câu cứu được cả việc nằm ngay trong
tài liệu — *"47 lượt có phát lại, trong 57 lượt ghi được"*. **Lát cắt hàng phải ghi
cạnh con số, ngang hàng với quy ước phân vị.**

### 1c. Mẻ 09/09 — `[TRUY ĐƯỢC]`, nhưng vài con số ĐÃ ĐỔI so với DEVICE-FLOOR

File thô: **`docs/benchmark/device_floor_20260909_v1.jsonl`** (311 bản ghi, chép nguyên
vẹn từ `desktop/logs/device_floor.jsonl`).

**Lát cắt** — *toàn bộ phiên `1788966181-b850`* (59 lượt, 22:03:18–22:07:07, `rtt_p50`
hằng số 4,65 ms). Đây là "một phiên liền mạch trên mạng mới" mà DEVICE-FLOOR nói tới.
Quy tắc chọn **không nhìn vào đáp án**: lấy trọn một phiên, không cắt xén.

**Lát cắt gốc của DEVICE-FLOOR (44 lượt / 48 lượt) không tái lập được.** File đã được ghi
thêm 203 bản ghi sau đó (phiên `1788966446-9950`, 22:07:29–22:16:28 — chính là đoạn "te
te te" ở âm lượng 85), nên mọi lát cắt theo mốc byte của hôm ấy giờ trỏ vào chỗ khác.

| số | DEVICE-FLOOR (44/48 lượt) | tính lại (toàn phiên, n=59) | |
|---|---|---|---|
| `t_rx_first` p50 | 132,3 | **131,6** | đổi −0,7 |
| `t_rx_first` p95 | 141,9 | **143,7** | đổi +1,8 |
| RTT p50 | 4,65 | 4,65 | ✓ |
| RTT p95 | 109,2 | **4,65** | **gỡ — xem dưới** |
| jitter p50 / p95 / max | 5,79 / 9,99 / 10,29 | **6,12 / 10,24 / 13,40** | đổi |
| cỡ khung Opus | 146 / 146 / 147 | **143 / 146 / 153** | đổi |
| lỗi giải mã Opus | 0 | 0 | ✓ |
| lệch hai nhóm kích hoạt | 1,2 ms (39 vs 8) | **1,1 ms** (47 vs 12) | ≈ ✓ |

**RTT p95 = 109,2 ms bị GỠ vì nó không tồn tại trong dữ liệu.** Mọi bản ghi của phiên ấy
mang `rtt_p50` = 4,65; toàn file chỉ có {4,65 · 14,1 · 22,28 … 670,55}. Không lát cắt nào
sinh ra 109,2. (File 06/09 có 113,47 — nhiều khả năng là chép nhầm cột.) Cách phát biểu
đúng: **RTT trong phiên là hằng số 4,65 ms**, và câu "p95 vẫn 109 ms — đuôi dài không mất
đi cùng cái router" phải bỏ, vì mẻ này không có đuôi dài.

**Kiểm độ nhạy — kết luận KHÔNG phụ thuộc lát cắt.** Lát cắt "48 bản ghi cuối" (lát duy
nhất khớp dấu vân tay của tài liệu cũ: nhóm tone đúng 39 lượt, cỡ khung đúng
146/146/147) cho `t_rx_first` p50 **131,60 — y hệt**, và lệch hai nhóm 2,3 ms. Hai lát
cắt cho cùng p50, và lệch hai nhóm nằm trong 1,1–2,3 ms. Cả hai đều **rất nhỏ so với
27,7 ms mà RTT đã đổi** giữa hai mạng, nên luận điểm *"`t_rx_first` là hằng số của
board"* đứng vững ở cả hai cách cắt:

> 06/09 → 09/09: `t_rx_first` p50 **133,4 → 131,6 ms** (đổi 1,8 ms) trong khi RTT p50
> **32,4 → 4,65 ms** (đổi 27,7 ms, giảm 7 lần).

### 1d. BỔ SUNG SAU KHI ĐÓNG SỔ — 10/09/2026 · SÀN THIẾT BỊ, cả hai chặng

Đợt 13. Trước hôm nay ô "mic → loa" của `DEVICE-FLOOR.md` **cố ý để trống** và Bảng 3
ghi *"chưa cộng được"*. Giờ có số.

**Nguồn thô:** `docs/benchmark/devout_20260910_p{1,2,3}.json` (từng lượt, ba mẻ độc
lập), `docs/benchmark/device_floor_20260910_v1.jsonl` (25 Turn),
`docs/benchmark/latency_es3c28p_20260910_v1.jsonl` (28 bản ghi pipeline).
**Dụng cụ:** `desktop/scripts/bench_devout.py`.

**Bố trí:** 10 câu bài test **giọng chủ nhân** (lần thu đầu của mỗi câu trong bộ 31 lượt
06/09) phát qua loa laptop cho board nghe; board chạy `--reply pipeline` và đáp ra loa
của nó; mic laptop mở ở **WASAPI exclusive** thu suốt buổi. Ba mẻ, 20/30 câu sinh ra lượt.

**Quy ước phân vị:** `sorted(v)[round(q·(n−1))]` — phân vị gần nhất, không nội suy,
**cùng hàm** với §1b/§1c.

| số | giá trị | n | lát cắt / quy ước |
|---|---|---|---|
| chặng **lên** − m | p50 **177,8** / p95 334,9 ms | 22 click ghép được | **bộ tất cả**; xem cảnh báo hai cụm |
| chặng **xuống** + m | p50 **319,0** / p95 352,0 ms | 18 lượt | gồm cả một điểm rời 1 466 ms |
| **SÀN THIẾT BỊ** = lên + xuống | p50 **525,9** / p95 653,9 ms | 16 lượt | **bỏ điểm rời**; m tự triệt tiêu |
| chặng xuống, trung bình ± sd | 319,5 ± 22,2 ms | 17 lượt | bỏ điểm rời |
| `t_rx_first` mẻ 10/09 | p50 **130,3** / p95 139,9 ms | 25 Turn | trọn lát cắt của ba mẻ |
| `m` — độ trễ đường thu laptop | **20,0 ms** | — | **WASAPI khai báo, KHÔNG phải số đo** |

**Cảnh báo hai cụm ở dòng "chặng lên".** 19 giá trị nằm trong 99,9–212,9 ms; ba giá trị
332,9 / 334,9 / 337,2 ms đứng riêng, sát trần cửa sổ ghép 350 ms, và **có thể là ghép
nhầm**. Bỏ hay giữ đổi **cả hai** phân vị:

| bộ | n | p50 | p95 |
|---|---|---|---|
| tất cả — **dùng trong bài** | 22 | 177,8 | 334,9 |
| bỏ cụm cao | 19 | 164,0 | 207,2 |

Dùng bộ tất cả vì loại ba điểm ấy chỉ có căn cứ *"chúng trông không giống phần còn
lại"*, mà đó không phải căn cứ.

**Bảng 3 — cộng vào baseline:**

| | laptop-only (baseline v3) | + sàn thiết bị | tổng |
|---|---|---|---|
| e2e p50 | 5 129 ms | **526 ms** | **5 655 ms** |
| e2e p95 | 7 649 ms | 654 ms | *cận trên thô* 8 303 ms |

> **Dòng p95 KHÔNG phải p95 của tổng.** p95 của một tổng chỉ bằng tổng hai p95 khi hai
> thành phần đạt đuôi cùng lúc; ở đây chúng độc lập (đuôi pipeline là LLM nghĩ lâu, đuôi
> thiết bị là Wi-Fi vấp). Ghi là **cận trên thô**, và ai trích nó phải trích kèm chữ ấy.
> Dòng p50 cộng được: trung vị của tổng hai đại lượng độc lập lệch nhẹ ≈ tổng hai trung vị.

**Dụng cụ chấm mốc đổi kết quả — cùng dữ liệu, cùng lượt:**

| cách chấm | p50 | p95 |
|---|---|---|
| lọc phối hợp với dòng PCM server đã gửi | **319,0** | 352,0 |
| ngưỡng + thời gian giữ | 875,9 | 10 882,9 |

Chênh **2,7 lần** ở p50. Cách ngưỡng đo *"lúc tiếng vượt ngưỡng"* chứ không phải *"lúc
tiếng bắt đầu"*, và quét độ nhạy cho thấy nó nhảy 615 → 1 910 ms chỉ vì đổi hai tham số
dò. Đây là **một giả tượng đo lường thứ sáu**, cùng họ với năm cái đã có.

**Ba khoản KHÔNG được bỏ khi trích:**

1. Mẻ này chạy `--mic-gain 9.0` (đường loa laptop → mic board hụt ~20 dB). Nhân biên độ
   **không dời mốc thời gian** nên số độ trễ không bị ảnh hưởng, nhưng **transcript của
   mẻ này KHÔNG được đem chấm WER**.
2. `m` = 20,0 ms là **con số driver khai báo**, không phải số đo. Dòng "sàn thiết bị"
   không phụ thuộc vào nó; hai dòng kia thì có.
3. Không có dao động ký → số là **chặn dưới để so tương đối**, không phải giá trị tuyệt
   đối. Sai số nghiêng về phía làm số **xấu đi** (khử ồn nuốt đỉnh, không dời đỉnh sớm lên).

**Threat to validity — dấu thời gian phần mềm trên ESP32.** Smelcerz và cs., *Sensors*
26(17):5555 (2026), đo rằng dấu thời gian lấy bằng phần mềm trên ESP32 lệch **~12 ms** so
với dao động ký. **Bảng 1d KHÔNG dùng mốc nào của board** — mọi mốc đều lấy trên laptop
(`perf_counter`, tức QPC, chung gốc mọi tiến trình) — nên sai số ấy không vào đây. Nó sẽ
vào nếu sau này sửa firmware cho board tự báo mốc, và lúc ấy nó **lớn gấp đôi** jitter
khung Opus 6,1–6,4 ms của chính ta.

### 1e. BỔ SUNG — 11/09/2026 · nhánh open-weight, cổng chạy-lại CÙNG HOST

Đợt 13. Thay cho phép kiểm đổi-host (DeepInfra) đã bỏ: chạy lại **cùng model, cùng
prompt, cùng máy, `seed=0` và `temperature` đều ghim**, sau **bốn ngày** và sau khi dịch
vụ ollama đã tắt đi bật lại.

**Nguồn thô:** `study/langconf/results/rerun_check_qwen2.5-7b.json`.
**Dụng cụ:** `study/langconf/scripts/rerun_check.py` (mẫu 23 lượt, hạt giống 20260911).

| số | giá trị | n | KTC 95 % (Wilson) |
|---|---|---|---|
| **nhãn ngôn ngữ** không đổi | **23/23 = 1,000** | 23 | 0,857 – 1,000 |
| **chữ** trùng từng ký tự | **7/23 = 0,304** | 23 | 0,156 – 0,509 |

Đọc ra, và đây là chỗ phải đọc cho đúng: **mọi tham số ghim được đều đã ghim**, mà chữ
vẫn đổi ở **70 %** số lượt. Cái tất định không phải *văn bản*; cái tất định là *quyết
định*. Cùng hướng với ô STT cục bộ (0/31 trên transcript) nhưng **không cùng độ mạnh** —
và chênh lệch ấy là chuyện của tác vụ (giải mã gần-tất-định so với sinh có lấy mẫu),
không phải chuyện của chỗ đặt.

Cận trên 1,000 của dòng nhãn chỉ cho **0,857** làm cận dưới, nên **không được viết
"tất định"** — viết "không đổi trên 23 lượt; Wilson 0,857–1,000".

### 1f. BỔ SUNG — 11/09/2026 · hai nhánh open-weight, LƯỚI RÚT GỌN

Đợt 13. Trả lời cho hạn chế *"một model API duy nhất"* mà `study/langconf/RESULTS.md` tự
nêu — **không** phải hạn chế số 1 của bài (bài đo tác vụ khác; xem Hạn chế 1).

**Nguồn thô:** `study/langconf/results/main_qwen2.5-7b.jsonl` (667 lượt),
`..._llama3.1-8b.jsonl` (128 lượt), `..._openweight_check.json`.
**Dụng cụ:** `study/langconf/scripts/openweight_check.py`. KTC Wilson 95 %.
**Hạ tầng:** ollama, CPU cục bộ, **Q4_K_M** cả hai nhánh.

| ô (sâu, vị trí nhãn) | hosted (n=400/ô) | `qwen2.5:7b` | `llama3.1:8b` |
|---|---|---|---|
| (2, không nhãn) | **0,002** | **100/134 = 0,746** [0,67–0,81] | **26/26 = 1,000** [0,87–1,00] |
| (2, nhãn ở user) | 0,982 | 130/133 = 0,977 [0,94–0,99] | 26/26 = 1,000 [0,87–1,00] |
| (8, không nhãn) | **0,000** | **69/134 = 0,515** [0,43–0,60] | 20/26 = 0,769 [0,58–0,89] |
| (8, nhãn ở user) | 0,875 | 126/132 = 0,955 [0,90–0,98] | 24/24 = 1,000 [0,86–1,00] |

**Chiều tái lập trên qwen, KTC tách hẳn** ở cả hai độ sâu. **Độ lớn KHÔNG tái lập:** ở ô
quyết định (sâu 2, không nhãn) hosted rơi xuống 0,002 còn qwen giữ 0,746, còn llama không
nhiễm chút nào (26/26).

**Ba chỗ chặn khi trích:**

1. **Lưới rút gọn 6 ô**, không phải 80 ô. Lý do là số học: qwen chạy **0,080 lượt/s** trên
   máy này ⇒ 4 000 lượt ≈ 14 giờ CPU một nhánh.
2. **Nhánh llama còn dở** (128/4 000). KTC mọi ô đều rộng.
3. **Lượng tử hoá lẫn với model.** Hai nhánh local ở Q4_K_M, hosted ở độ chính xác nhà
   cung cấp không công bố. Chênh lệch độ lớn **không tách được** thành "do model" và "do
   lượng tử hoá" — phép tách ấy chính là `host_check.py`, đã bỏ cùng DeepInfra.

**KHÔNG được viết:** *"hiệu ứng nhiễm lịch sử là phổ quát với LLM"*. Ba model, ba mức tổn
thương, một trong ba gần như miễn nhiễm ở sâu 2.

---

## 2. Tầng grounding — tính tất định qua một đêm

Cửa sổ: **13 giờ, qua đêm, giữa hai phiên làm việc** (09/09 21:07 → 10/09 10:08, +07).
Viết đúng câu ấy — **không được viết "24 giờ"**, và cũng đừng làm tròn thành "một ngày".

**Cửa sổ này chỉ cho phép nói *có quan sát được thay đổi trong 13 giờ*.** Không kết luận
gì về **nhịp** đổi nguồn — 13 giờ gồm trọn một đêm, chỉ mục của Google không cập nhật đều
theo giờ, và hai điểm đo không dựng được đường cong.

| số | tổng (n = 30) | Wilson 95 % | `fast-changing` (n = 16) | `slow-changing` (n = 14) |
|---|---|---|---|---|
| đổi đáp án (nguyên văn) | 21/30 = 0,70 | 0,521–0,833 | 14/16 = 0,88 | 7/14 = 0,50 |
| đổi tập tên miền (trên câu **có tra**) | **15/21 = 0,71** | **0,500–0,862** | 9/14 = 0,64 | 6/7 = 0,86 |
| Jaccard tên miền trung bình | **0,51** | — *(trung bình, không phải tỉ lệ)* | 0,55 (n = 14) | 0,42 (n = 7) |
| quyết định *có tra* đổi | **0/30** | **0,000–0,114** *(cận trên 10 % theo quy tắc ba)* | 0/16 | 0/14 |
| trùng khít J = 1,00 / rời hẳn J = 0,00 | 6/21 / 3/21 | — | — |
| hợp tên miền toàn mẻ | 42 → 53, chung 30, J toàn cục 0,46 | — | — |
| **đối chứng âm** — 9 câu KHÔNG tra, đổi lời vịt nói | **7/9 = 0,78** | 0,453–0,937 | — | — |

Đối chứng âm so với nhóm có tra (21/21 = 1,00): Fisher hai phía **p = 0,083**; Wilson
chồng lấn ([0,45–0,94] so với [0,85–1,00]).

**Cảnh báo trích dẫn.** Dòng "đổi đáp án 0,70" **không được dùng** làm bằng chứng cho
tầng grounding — ở `temperature = 0,8` câu chữ đổi ở mọi tầng, kể cả lượt không hề đi
tra. Thước riêng của tầng grounding là **tập tên miền**.

Chiều `fast` / `slow`: **không viết câu nào** — `slow-changing` chỉ có 7 câu đi tra, và
Jaccard của nó (0,42) còn thấp hơn `fast-changing` (0,55), ngược chiều trực giác.

Nguồn: `docs/benchmark/grounding_stability_20260909_run1.jsonl`,
`docs/benchmark/grounding_stability_20260910_run2.jsonl`.

---

## 3. Định tuyến — độ chính xác

### Bảng 2 — khối A (n = 100; mỗi nửa ngôn ngữ n = 25 câu cần tra)

| | n (cần / không) | đúng-dương | **sai-dương** | **sai-âm** | precision | recall (Wilson 95 %) |
|---|---|---:|---:|---:|---:|---|
| tất cả | 50 / 50 | 36 | 3 | 14 | 0,923 | 0,720 (0,583–0,825) |
| tiếng Việt | 25 / 25 | 23 | 0 | 2 | 1,000 | 0,920 (0,750–0,978) |
| tiếng Anh | 25 / 25 | 13 | 3 | 12 | 0,812 | 0,520 (0,335–0,700) |

Nguồn: `docs/benchmark/lookup_accuracy_20260909_v2.jsonl` · bộ câu
`docs/benchmark/lookup_set_v1.jsonl` · giao thức `docs/benchmark/LABELING-PROTOCOL.md`

### Bảng 3 — vùng xám theo `fact_type`

| `fact_type` | gắn nhãn | n | đọc là | Wilson 95 % |
|---|---|---|---|---|
| `fast-changing` | 27/30 | 30 | recall 0,900 | 0,744–0,965 |
| `slow-changing` | 9/20 | 20 | recall 0,450 | 0,258–0,658 |
| `never-changing` | 3/50 | 50 | **sai-dương 0,060** | 0,021–0,162 |

Nguồn: `docs/benchmark/lookup_accuracy_20260909_v2.jsonl`

### Bảng 4 — nhãn `[premise]`, khối B

12/20 (Wilson 0,387–0,781); không câu nào gắn kèm `[lookup]`.
Nguồn: `docs/benchmark/lookup_accuracy_20260909_v2.jsonl` (20 bản ghi khối B).

### Đối chứng bộ tự bịa

Bộ 30 câu tự bịa: sai-âm **0/15**, precision/recall **1,000** — so với sai-âm **14/50**
trên bộ có nhãn bình duyệt. Nguồn: `docs/benchmark/lookup_flag_20260909_v1.jsonl`.

### 3b. ADR-007 — `temperature=0` cho Whisper · `[TRUY ĐƯỢC]` sau khi TÁI LẬP (việc 33)

Mẻ A/B gốc không còn file, nhưng **audio vào thì còn nguyên**, nên chạy lại trên đúng
bộ ấy là **tái lập**, không phải phép đo mới. Script:
`desktop/scripts/bench_stt_determinism.py`, giữ đúng thiết kế của ADR-007 — cùng một
tiến trình, xen kẽ cũ/mới, 3 vòng, hai backend. Không gọi API.

**Ba thứ bắt buộc, ghi ngay đây:** *quy ước phân vị* = gần nhất, không nội suy;
*lát cắt hàng* = mọi lượt của cả 3 vòng, không bỏ lượt nào, n = 30 mỗi ô; *thước WER* =
cả ba thước O/N/D của `PROTOCOL.md`.

| backend | điều kiện | n | `t_stt` p50 | p95 | max | WER-D | WER-N | WER-O |
|---|---|---|---|---|---|---|---|---|
| `base` | cũ (dải fallback 0→1) | 30 | 1 134,2 | **2 506,9** | 8 246,3 | 0,315 | 0,370 | 0,407 |
| `base` | **mới (`temperature=0`)** | 30 | 1 133,2 | **1 494,3** | 1 497,9 | **0,273** | **0,327** | **0,370** |
| `phowhisper-reread` | cũ | 30 | 1 703,7 | **5 514,6** | 5 563,6 | 0,212 | 0,212 | 0,346 |
| `phowhisper-reread` | **mới** | 30 | 1 599,2 | **2 439,8** | 7 907,2 | **0,200** | **0,200** | **0,333** |

#### Con số chính TÁI LẬP ĐƯỢC

> `base` p95 **2 506,9 → 1 494,3 ms = −40,4 %**, so với **−42 %** của ADR-007 — **lệch
> 1,6 điểm phần trăm**.

Và **tất định đo thẳng lần đầu tiên** (ADR-007 chỉ có cột có/không, chưa từng có số):

| backend | cũ | mới |
|---|---|---|
| `base` | **1/10** câu bất ổn — `utt_10.wav` (Wilson 0,018–0,404) | **0/10** (Wilson 0,000–0,278) |
| `phowhisper-reread` | **1/10** câu bất ổn — `utt_10.wav` (Wilson 0,018–0,404) | **0/10** (Wilson 0,000–0,278) |

**KTC ở đây rất rộng vì n = 10 câu.** Không được đọc "0/10" thành "không bao giờ bất
ổn": cận trên 95 % là **27,8 %**. Cái mẻ này chứng minh chắc là **chiều** (1 → 0, và
đúng câu ADR-007 nêu đích danh), không phải độ lớn.

`utt_10.wav` là **"Dừng."** — đúng câu ADR-007 nêu đích danh. Chép nó ra `"You"` ở nhánh
`temperature=0`, và ra nhiều thứ khác nhau ở nhánh cũ. Đây là con số hợp với định nghĩa
tất định dùng suốt bài (*cùng đầu vào → cùng đầu ra*), nên **Bảng 1 dòng STT nên in nó**
chứ đừng chỉ in phần trăm p95.

#### Cơ chế khớp hơn cả ADR-007 mô tả: `temperature=0` cắt ĐUÔI, không cắt giữa

`base` p50 **1 134,2 → 1 133,2 ms** — đứng yên. Ba giá trị cao nhất: nhánh cũ
[1 961 · 2 507 · **8 246**], nhánh mới [1 454 · 1 494 · 1 498]. Mỗi lần fallback là một
lần chép **lại** toàn bộ đoạn audio, nên nó rơi hết vào đuôi. (ADR-007 báo p50 giảm 9 %
và 18 %; ở mẻ này p50 **không giảm**, và điều đó *củng cố* lập luận đuôi chứ không phá.)

#### Chỗ KHÔNG tái lập: số của `phowhisper-reread`

> `phowhisper-reread` p95 **5 514,6 → 2 439,8 = −55,8 %**, so với **−17 %** của ADR-007
> — **lệch 38,8 điểm phần trăm**.

Cùng chiều nhưng khác hẳn độ lớn. Ô ấy là ô **kém ổn định nhất** trong bốn ô: p95 của
nhánh cũ dựa lên hai lượt chậm trong ba mươi ([4 610 · 5 515 · 5 564]), và nhánh mới còn
một ngoại lệ 7 907 ms mà p95 vừa vặn không chạm tới. **Đừng trích con số −55,8 %**; nếu
cần nhắc thì nhắc chiều, không nhắc độ lớn.

#### Đối chứng rỗng — sàn nhiễu p95 của chính máy này

Mẻ đầu của việc 33 **hỏng vì một lý do đáng ghi**: từ khi ADR-007 được thi hành,
`DuckSTTHandler.setup` đặt sẵn `"temperature": 0.0`, nên "không truyền `gen_kwargs`"
**không còn** nghĩa là "như cũ". Mẻ ấy đo **cùng một điều kiện hai lần**.

Hỏng cho mục đích ban đầu, nhưng nó là một **đối chứng rỗng** đúng nghĩa, và được giữ
lại (`stt_determinism_20260910_v2_doichung_rong.jsonl`): hai lần chạy **cùng** điều kiện
cho p95 lệch **−9,0 %** (`base`) và **+10,7 %** (`phowhisper-reread`).

Đó là **sàn nhiễu**, và nó là thứ làm hai con số trên đọc được:

- −40,4 % của `base` lớn gấp **hơn bốn lần** sàn nhiễu → thật.
- −55,8 % của `phowhisper-reread` cũng vượt sàn, nhưng ô ấy có đuôi dày và ADR-007 báo
  −17 % ở cùng ô, nên độ lớn không đáng tin.

**Bài học, ghi vào Phương pháp:** đừng suy ra điều kiện thí nghiệm từ việc **không**
truyền một tham số. Ghi thẳng giá trị cho **cả hai** nhánh và in ra lúc chạy. Đây là lần
thứ năm trong dự án cùng một hình dạng — số trông đúng vì lý do sai (bốn lần trước:
`uri`, chuỗi rỗng 9/9, lát cắt hàng, `pa_inverted`).

Nguồn: `docs/benchmark/stt_determinism_20260910_v2.jsonl` (120 bản ghi) ·
`docs/benchmark/stt_determinism_20260910_v2_doichung_rong.jsonl` (120 bản ghi, đối chứng
rỗng) · audio `docs/benchmark/realvoice_20260904/` · ground truth
`docs/benchmark/stt_realvoice_20260904_scored.json`.

**Vẫn còn một số của ADR-007 không truy được:** WER nhánh cũ của `phowhisper-reread`
(0,218) không có trong file nào, và mẻ tái lập cho 0,212 — gần, nhưng là **số mới**, không
phải xác nhận. Không trích 0,218.

### 3c. ADR-004 — chọn backend STT · `[TRUY ĐƯỢC]` toàn bộ

Lệnh gốc ghi ngay trong ADR-004: `rescore_utts.py logs/utts --refs
..docs/baseline/realvoice_2026-09-06_v2_refs.json --local-candidates --deterministic`.
Bộ 31 WAV, ba thước WER của `docs/benchmark/PROTOCOL.md`.

| số | ADR-004 | file | |
|---|---|---|---|
| `large-v3-turbo` WER | 0,368 | 0,3684 | ✓ |
| `large-v3-turbo` CER · đúng ngôn ngữ | 0,269 · 97 % | 0,2693 · 0,968 | ✓ |
| `large-v3-turbo` `t_stt` p50 / p95 | 21 312 / 23 908 ms | 21 312,2 / 23 907,5 | ✓ |
| `gemini-audio` WER · CER | 0,333 · 0,219 | 0,3333 · 0,2187 | ✓ |
| `gemini-audio` `t_stt` p50 / p95 · đúng ngôn ngữ | 2 624 / 4 211 ms · 100 % | 2 623,6 / 4 210,8 · 1,0 | ✓ |
| bảng cũ bị bác: gemini 97 % / 0,370 · large 94 % / 0,399 | — | `..._v3.json`: 0,3699 / 0,968 · 0,3988 / 0,935 | ✓ |
| ba thước O/N/D của `large-v3-turbo` | 0,458 / 0,415 / 0,368 | `..._v4_owner.json`: 0,4583 / 0,4152 / 0,3684 | ✓ |
| `stt_lang_wrong` giọng thật **6/31 = 19 %** | — | `docs/baseline/latency_desktop_realvoice_2026-09-06_v2.jsonl` | ✓ |

Nguồn: `docs/benchmark/stt_rescore_20260906_v3_fixed.json` (bảng chính),
`stt_rescore_20260906_v3.json` (bảng cũ bị bác), `stt_rescore_20260907_v4_owner.json`
(ba thước O/N/D), `stt_rescore_20260906_v2.json` (mẻ sớm hơn, để đối chiếu).

### 3d. BỔ SUNG SAU KHI ĐÓNG SỔ — 10/09/2026, đợt 11 · giữ vết kiểm toán

`PAPER-NUMBERS.md` đóng sổ 10/09/2026. Dòng dưới đây **thêm sau khi đóng**, theo quyết
định (a) của chủ nhân ở đợt 9, và **chỉ sau khi hai chỗ vênh được truy xong**.

#### Chỗ vênh 1 — `0,711` so với `0,7076`: KHÔNG phải làm tròn, mà là HAI MẺ KHÁC NHAU

| giá trị | xuất hiện ở |
|---|---|
| **0,711** | `stt_rescore_20260906_v2.json` **và** `..._v3.json` — trùng khít ở cả hai |
| **0,7076** | `stt_rescore_20260906_v3_fixed.json` **và** `..._v4_owner.json` — trùng khít ở cả hai |

Đây là chênh lệch giữa mẻ **trước** và **sau** lần sửa v3 → v3_fixed, không phải chuyện
chữ số. Cùng lần sửa ấy còn đưa `gemini-audio` 0,3699 → 0,3333 và đúng-ngôn-ngữ của
`phowhisper-reread` 0,71 → 0,677. ADR-004 trích con số của mẻ **trước** khi sửa.

#### Chỗ vênh 2 — cùng THƯỚC, nhưng phải ghép trong CÙNG MỘT MẺ

Trường `wer` trần trong mọi file **là D-WER**: `WER_VARIANTS` trong `rescore_utts.py`
ánh xạ `("d", None)`, và `None` nghĩa là `normalize()` mặc định của `scoring.py`. Kiểm
bằng số chứ không chỉ bằng code: `wer` của `v3_fixed` **trùng khít** `wer_d` của
`v4_owner` ở **hai** backend độc lập — `phowhisper-reread` 0,7076 và `large-v3-turbo`
0,3684.

⇒ `0,370` và `0,7076` **cùng thước** (D-WER) nhưng **khác mẻ**. Ghép chúng thành một cặp
là đúng cái bẫy đã sập năm lần trong dự án này. Cặp ghép được là cặp **trong cùng một
mẻ**.

#### Dòng bổ sung — mẻ `v3_fixed`, đủ năm cột

| backend | D-WER | CER | đúng ngôn ngữ | `t_stt` p50 / p95 | n |
|---|---|---|---|---|---|
| `gemini-audio` | **0,3333** | 0,2187 | **31/31 = 1,000** (Wilson 0,890–1,000) | 2 623,6 / 4 210,8 ms | 31 |
| `phowhisper-reread` | **0,7076** | 0,5240 | **21/31 = 0,677** (Wilson 0,501–0,814) | 2 011,1 / 3 140,1 ms | 31 |
| `large-v3-turbo` | **0,3684** | 0,2693 | **30/31 = 0,968** (Wilson 0,838–0,994) | 21 312,2 / 23 907,5 ms | 31 |

**Quy ước:** thước = **D-WER** (và CER cùng chuẩn hoá) · lát cắt = trọn bộ 31 lượt, không
loại lượt nào · phân vị `t_stt` = gần nhất, không nội suy.
Nguồn: `docs/benchmark/stt_rescore_20260906_v3_fixed.json`.

**Cặp KHÔNG được ghép:** `0,370` (mẻ v3) với `0,7076` (mẻ v3_fixed). Nếu cần nhắc mẻ cũ
thì nhắc **cả cặp** của nó: gemini 0,3699 / phowhisper 0,711, đúng ngôn ngữ 0,968 / 0,71.

**Lần sửa v3 → v3_fixed dịch chuyển CẢ SÁU backend, không phải ba** (đợt 12, việc 41):
`base` 0,7861→0,7836 · `gemini-audio` 0,3699→0,3333 · `large-v3-turbo` 0,3988→0,3684 ·
`phowhisper-reread` 0,711→0,7076 · `phowhisper + vi+en` 0,711→0,7076 ·
`phowhisper-small` 0,7225→0,7193; và đúng-ngôn-ngữ của mọi backend cục bộ 0,710→0,677.
⇒ **bất kỳ số nào lấy từ mẻ `v3` đều phải kiểm lại**, không riêng ba số đã biết.

#### `21/31 lượt dùng được` — KHÔNG bổ sung

Outline trích "transcript dùng được 21/31 vs 6/31". Trường ấy **không tồn tại** trong bất
kỳ file nào; muốn có phải tự đặt ngưỡng (ví dụ WER < 0,5) rồi đếm — tức **suy ra một ước
lượng điểm**, đúng thứ luật đợt 9 cấm. **Không vào bài.** (Con số 21/31 của bảng đúng
ngôn ngữ ở trên là chuyện khác: nó là `language_accuracy` 0,677 × 31, đọc thẳng từ file.)

**Thước phải ghi kèm — nếu không, số lệch một cách hợp lệ.** Con số 0,368 là **D-WER**.
Cùng file ấy, O-WER là 0,458 và N-WER là 0,415. Trích 0,368 mà không nói "D-WER" thì
người đọc so với O-WER của công trình khác và kết luận sai.

> **ĐÍNH CHÍNH 10/09/2026 (đợt 11) — D-WER KHÔNG phải "bỏ dấu".** Bản trước của dòng này
> ghi *"D-WER (sau chuẩn hoá bỏ dấu)"*. **Sai.** Đọc `desktop/scoring.py::normalize` và
> `docs/benchmark/PROTOCOL.md` §D-WER: `normalize()` **giữ nguyên dấu thanh tiếng Việt** —
> "sai dấu chính là lỗi ta muốn đo". D-WER = N-WER **cộng thêm** hai bước riêng của repo:
> số viết bằng chữ ≡ chữ số, và gộp biến thể tên riêng. Nên **D ≤ N ≤ O**, và D-WER là
> thước **lỏng nhất** trong ba, không phải thước "bỏ dấu".
>
> Định nghĩa đúng để dùng trong bài: *O-WER* = không chuẩn hoá gì (giữ hoa/thường và dấu
> câu); *N-WER* = chữ thường + bỏ dấu câu; *D-WER* = N-WER + số-chữ ≡ chữ-số + gộp biến
> thể tên riêng, **dấu thanh giữ nguyên ở cả ba**.

#### Hệ quả của `D ≤ N ≤ O` — phải viết vào Phương pháp, không chỉ sửa ngoặc đơn

Sửa định nghĩa mới là nửa việc. Vì D-WER là thước **lỏng nhất**:

1. **Mọi con số D-WER của ta là cận dưới của lỗi.** Không phải "một cách đo khác" — là
   **ước lượng lạc quan có hướng**.
2. **Mọi so sánh với công trình báo O-WER đều nghiêng về phía ta.** Ai trích 0,3684 của
   ta cạnh một O-WER của người khác là đang so một cận dưới với một cận trên.
3. Độ lớn của chuyện này **không nhỏ hơn** độ lớn của kết luận: chênh O→D của cùng một
   hệ là **0,090**, còn khoảng cách giữa hai hệ chỉ **0,035** — **gấp 2,6 lần**.

> **Chọn thước quyết định kết luận nhiều hơn chọn hệ.** Một phép so chéo không nêu thước
> thì **vô nghĩa về mặt số học**, chứ không phải chỉ là thiếu chỉn chu.

Nên bài **báo cả ba thước ở mọi bảng WER**, và khi buộc phải nêu một số thì nêu D-WER
**kèm chữ "D-WER"** và kèm câu "đây là cận dưới".


### 3e. BỔ SUNG SAU KHI ĐÓNG SỔ — 10/09/2026, đợt 12 · backend hosted không tái lập được

**Vì sao nó là "đếm" chứ không phải "suy ra":** con số dưới đây có được bằng cách **mở
hai file thô đã nằm trên đĩa và so từng dòng**. Không ước lượng, không mô hình, không
tham số. Đếm không phải là suy — nó cùng hạng với mọi con số khác trong sổ.

| số | giá trị | n | KTC Wilson 95 % | nguồn | quy ước |
|---|---|---|---|---|---|
| transcript đổi giữa hai mẻ — **hosted** (`gemini-2.5-flash` audio) | **5/31 = 0,161** | 31 | **0,071–0,326** | (A) × (B) dưới đây | so trường `hypothesis` **nguyên văn** |
| transcript đổi — **cục bộ** `base` + PhoWhisper re-read | **0/31 = 0,000** | 31 | **0,000–0,110** | như trên | như trên |
| transcript đổi — **cục bộ** `faster-whisper large-v3-turbo` | **0/31 = 0,000** | 31 | **0,000–0,110** | như trên | như trên |
| reference đổi giữa hai mẻ (đối chứng) | **0/31** | 31 | 0,000–0,110 | như trên | so trường `reference` nguyên văn |

(A) `docs/benchmark/stt_rescore_20260906_v3_fixed.json`
(B) `docs/benchmark/stt_rescore_20260907_v4_owner.json`

**ĐIỀU KIỆN ĐO — ngang hàng với n, không phải chú thích:**

- Hai mẻ cách nhau **MỘT NGÀY** (06/09 và 07/09). Người đọc lướt bảng sẽ mặc định hai
  lượt chạy liền nhau; **không được để họ mặc định thế**.
- Cùng audio, cùng bộ 31 file, cùng script chấm.
- **Không mẻ nào ghi lại `model_version`** — cả hai chỉ ghi chuỗi alias
  `gemini-audio/gemini-2.5-flash` (kiểm ở việc 38a). Từ đợt 12, `handlers/stt_gemini.py`
  ghi `response.model_version` và `response.response_id`.

**Quy ước so sánh, ghi đủ để tái lập:** so trường `hypothesis` **nguyên văn, KHÔNG chuẩn
hoá gì trước khi so** — hai chuỗi khác nhau dù chỉ một dấu câu là "đổi". Lý do không
chuẩn hoá: câu hỏi là *cùng đầu vào có cho cùng đầu ra không*, không phải *hai đầu ra có
cùng nghĩa không*; chuẩn hoá trước khi so là trả lời câu khác. Lát cắt: trọn 31 lượt.

#### Ba ràng buộc khi trích con số này

1. **Nó chứng minh ĐƯỜNG BIÊN, không chứng minh CƠ CHẾ.** Cấm viết "sampling
   nondeterminism", "model lấy mẫu ở temperature khác 0", hay bất cứ câu nào chỉ định cơ
   chế. Khoảng cách một ngày khiến **lấy mẫu** và **nhà cung cấp đổi model** chưa tách
   được. (Phép thử tách: chạy lại hai lượt trong **cùng một buổi** — việc 38b.)
2. **`0/31` cục bộ là đối chứng âm CÓ PHẠM VI.** Nó loại được: audio đổi · harness đổi ·
   script chấm đổi. Nó **không** loại được: version phía nhà cung cấp đổi — vì model cục
   bộ đã ghim thì về nguyên tắc không drift được, nên nó không nói gì về chuyện drift.
   Đừng để một đối chứng tốt gánh nhiều hơn nó chịu được (đúng lỗi đã mắc với 0,70 ở
   tầng grounding).
3. **Dùng được ở Abstract/Kết luận — nhưng phải đi CẶP với 2/31 của §3f**, và phải
   phát biểu theo mẫu "không tham số nào ghim được", **không** theo mẫu chỉ định cơ chế.
   Trích 5/31 một mình là mời đúng câu phản biện mà 2/31 sinh ra để giết.

#### Một dòng thuộc thẳng vào luận điểm, không phải chi tiết kỹ thuật

`gemini-2.5-flash` là một **alias**, không phải một version ghim được. Client **không có
cách nào** ghim version từ phía mình. Đó là **cùng một sự kiện cấu trúc** với việc không
ghim được `temperature` phía server: hai lần cùng một thứ — *tham số quyết định đầu ra
nằm ngoài tầm với của người gọi*.

### 3f. BỔ SUNG SAU KHI ĐÓNG SỔ — 10/09/2026, đợt 12 · hosted, hai lượt CÙNG MỘT BUỔI

⚠ **Đây là phép đo MỚI, không phải tái lập của §3e.** Nó đứng dòng riêng, ngày riêng,
**không ghi đè** 5/31. Giữ cả hai.

**CÁCH ĐỌC ĐÃ CHỐT (chủ nhân, đợt 12).** Không đi tìm phép tách nữa, và **không viết
mục này như một hạn chế**. Lý do ở "Vì sao thêm n không chữa được" bên dưới.

**Thiết kế:** cùng 31 WAV, cùng script, cùng máy, hai lượt cách nhau **180 giây**, cùng
một buổi tối 10/09 (lượt 1 ~21:05, lượt 2 21:11 +07). Nguồn:
`docs/benchmark/stt_hosted_repeat_20260910_v1.jsonl` (62 bản ghi).

**Quy ước — đủ cột, kể cả tham số harness làm đổi con số:**

| mục | giá trị |
|---|---|
| trường so sánh | `hypothesis`, **nguyên văn**, không chuẩn hoá gì trước khi so |
| lát cắt hàng | trọn 31 lượt, không loại lượt nào |
| **`timeout_s`** | **4,0 s** — tham số của **harness**, không phải của model. Nó **làm đổi con số**: 2 lượt vượt ngưỡng thành transcript rỗng, một trong hai rơi đúng cặp so, đội số thô từ 2/31 lên 3/31. Ghi ở đây ngang hàng với n, không xuống chú thích |
| tham số client đặt được | không có tham số nào ghim được đầu ra (xem dưới) |

| số | giá trị | n | KTC Wilson 95 % |
|---|---|---|---|
| transcript đổi giữa hai lượt cùng buổi — **thô** | **3/31 = 0,097** | 31 | 0,033–0,249 |
| …trong đó **do lượt gọi HỎNG** (timeout 4 s → transcript rỗng ở một lượt) | **1/31** | 31 | — |
| …**đổi nội dung thật** (cả hai lượt đều trả về chữ) | **2/31 = 0,065** | 31 | **0,018–0,207** |
| lượt gọi hỏng / rỗng trên toàn mẻ | 3/62 | 62 | — |

**Hai lượt đổi nội dung thật là gì:**

| file | lượt 1 | lượt 2 |
|---|---|---|
| `…_004.wav` | "Nhắc anh hợp lúc **3:00** chiều thứ sáu." | "Nhắc anh hợp lúc **3 giờ** chiều thứ sáu." |
| `…_005.wav` | "Nó kết hợp" | "Nó cái thân hình nó" |

#### 2/31 là con số TRẢ LỜI, không phải phép kiểm phụ

Đặt hai con số **cạnh nhau**, cùng hàng, không xếp cái này dưới cái kia:

| điều kiện | đổi nội dung thật | Wilson 95 % |
|---|---|---|
| **cách nhau một ngày** (§3e) | 5/31 = 0,161 | 0,071–0,326 |
| **cách nhau 180 GIÂY** (§3f) | **2/31 = 0,065** | **0,018–0,207** |

**2/31 trong 180 giây MẠNH HƠN 5/31 qua một đêm, không yếu hơn.** Nó giết câu phản biện
rẻ nhất mà bất kỳ người phản biện nào cũng viết được:

> *"5/31 qua một đêm chỉ có nghĩa là họ cập nhật model. Đó là versioning, không phải bất
> định."*

Ở khoảng cách **ba phút** câu ấy hết đứng. Đây là một mục của bài kiểm B8 — **công kích
đã có sẵn câu trả lời in trong bài**, không phải chờ tới vòng phản biện mới trả lời.

Đối chứng §3e vẫn sạch: trong 5 lượt đổi của mẻ một-ngày **không có chuỗi rỗng nào**,
nên 5/31 là 5 lượt đổi nội dung thật, so trực tiếp được với 2/31.

#### Vì sao THÊM n KHÔNG chữa được — đây là vấn đề ĐỊNH DANH, không phải độ chính xác

Việc 38a đã chứng minh chỗ này: `model_version` trả về **đúng cái alias ta gọi**
(`gemini-2.5-flash`), không phải một build id. ⇒ **Không có công cụ nào BÊN TRONG tiến
trình phân biệt được "lấy mẫu" với "đổi build".** Chạy thêm lượt thu hẹp khoảng tin cậy;
nó **không định danh cơ chế**. Thêm n không chữa được loại vấn đề ấy.

Và nếu vẫn muốn con số: để phát hiện chênh 0,065 vs 0,161 ở mức **80 % lực**, cần
**≈ 170 lượt mỗi nhánh** (xấp xỉ chuẩn hai phía; mô phỏng Fisher cho power 0,76 ở
n = 170 và **chỉ 0,41 ở n = 80**) — tức nhiều mẻ mỗi nhánh, và nhánh "cách ngày" tốn
nhiều ngày. **Kể cả thắng, cái thu được là phụ thuộc thời gian, vẫn không phải cơ chế.**

#### Cách phát biểu — KHÔNG viết như một hạn chế

**Không viết:** *"chúng tôi không tách được hai cơ chế."*

**Viết:** từ phía client, hai cơ chế ấy là **cùng một sự kiện** — không có tham số nào
đặt được để đầu ra tái lập, và không có trường nào đọc được để biết mình vừa gọi trúng
build nào. **Việc không phân giải được cái gì xảy ra bên ngoài tiến trình chính là định
nghĩa của đường biên.** Bài đang lập luận về đường biên ấy, nên đây là **bằng chứng**,
không phải lỗ hổng.

- **Câu phải né:** bất cứ câu nào chỉ định cơ chế ("sampling nondeterminism", "model lấy
  mẫu ở temperature khác 0", "nhà cung cấp đã đổi build").
- **Câu được phép:** *cùng đầu vào, cùng mọi tham số client đặt được, đầu ra đổi — trong
  180 giây cũng như qua một ngày.*

#### `model_version` đã ghi được — và nó KHÔNG ghim được version

Từ đợt 12, `stt_gemini.py` ghi `response.model_version`. Mẻ này là lần đầu có nó:

- **60/62 lượt trả về đúng một giá trị: chuỗi `gemini-2.5-flash`** — tức **chính cái
  alias ta gọi**, không phải một build id.
- 2/62 lượt còn lại là **timeout**, không có version. `None` **không phải một version
  thứ hai**.

⇒ Nâng từ suy luận thành **quan sát trực tiếp**: *ghi lại `model_version` KHÔNG làm cho
version ghim được — API trả về alias, và alias vẫn là alias.* Client không có đường nào
biết mình vừa gọi trúng build nào, nên **version drift không loại trừ được bằng dữ liệu
phía client**, kể cả khi ghi đủ trường.

Đó là cùng một sự kiện cấu trúc với `temperature` phía server: **tham số quyết định đầu
ra nằm ngoài tầm với của người gọi** — lần này có bằng chứng trực tiếp thay vì suy ra.

#### Một hạn chế của chính phép đo này, phải khai

`timeout_s = 4,0` là tham số của **harness**, không phải của model. 2/62 lượt vượt ngưỡng
ấy và thành transcript rỗng; một trong hai rơi đúng vào cặp so nên đội con số thô từ 2/31
lên 3/31. Bài **báo cả hai** (thô 3/31 và nội dung thật 2/31) chứ không chọn một — loại
lượt hỏng đi là **chọn mẫu theo kết quả**.

---

## 4. Bảng 2b — lưới 2×3, CẢ SÁU Ô Ở n = 200

Mỗi ô: 25 câu cần tra × 8 lần = **n = 200**; nửa âm cũng n = 200.
**Không ô nào lấy số của mẻ n = 50 cũ.**

| quy tắc | nửa | recall (Wilson 95 %) | **sai-dương** (Wilson 95 %) | precision | J | bal. acc |
|---|---|---|---|---:|---:|---:|
| vi (gốc) | câu vi | 192/200 = 0,960 (0,923–0,980) | 1/200 = 0,005 (0,001–0,028) | 0,995 | +0,955 | 0,978 |
| vi (gốc) | câu en | 102/200 = 0,510 (0,441–0,578) | 21/200 = 0,105 (0,070–0,155) | 0,829 | +0,405 | 0,703 |
| en | câu vi | 174/199 = 0,874 (0,821–0,913) | 1/200 = 0,005 (0,001–0,028) | 0,994 | +0,869 | 0,935 |
| en | câu en | 166/200 = 0,830 (0,772–0,876) | 59/200 = 0,295 (0,236–0,362) | 0,738 | +0,535 | 0,768 |
| vi-v2 | câu vi | 179/200 = 0,895 (0,845–0,930) | 2/200 = 0,010 (0,003–0,036) | 0,989 | +0,885 | 0,943 |
| vi-v2 | câu en | 135/200 = 0,675 (0,607–0,736) | 38/200 = 0,190 (0,142–0,250) | 0,780 | +0,485 | 0,743 |

Gộp hai nửa (n = 400 câu cần tra / 400 câu không cần):

| quy tắc | recall | **sai-dương** | precision | **J** | chênh hai nửa |
|---|---:|---:|---:|---:|---:|
| vi (gốc) | 0,735 | 0,055 | 0,930 | **+0,680** | 0,450 |
| en | 0,852 | 0,150 | 0,850 | **+0,702** | **0,044** |
| vi-v2 | 0,785 | 0,100 | 0,887 | **+0,685** | 0,220 |

Phép so (z hai tỉ lệ):

| phép so | | z | p |
|---|---|---:|---:|
| **ô quyết định** — câu vi, quy tắc vi→en | 0,960 → 0,874 | +3,105 | **0,0019** |
| ô đối xứng — câu en, quy tắc vi→en | 0,510 → 0,830 | −6,805 | **< 0,0001** |
| vi-v2 vs vi, câu vi | 0,895 vs 0,960 | −2,507 | 0,0122 |
| vi-v2 vs en, câu vi | 0,895 vs 0,874 | +0,645 | 0,519 |
| vi-v2 vs vi, câu en | 0,675 vs 0,510 | +3,358 | **0,0008** |
| vi-v2 vs en, câu en | 0,675 vs 0,830 | −3,592 | **0,0003** |

**Đối chứng với Bảng 2:** ô `vi × câu en` ra 0,510 so với 0,520 đã công bố, lệch
**−0,010**. Khớp, nên lưới dùng được.

**Cách phát biểu bắt buộc.** Quy tắc tiếng Anh là **đánh đổi**, không phải trội tuyệt
đối: nó cân bằng hai nửa (chênh 0,450 → 0,044) và trả giá bằng nửa tiếng Việt
(p = 0,0019) cộng sai-dương gộp gần gấp ba (0,055 → 0,150). J gộp của ba bản gần như
bằng nhau ⇒ **dời ngưỡng, không đổi năng lực**. Câu "vi-v2 rơi vào nhóm bản tiếng Anh"
**chỉ đúng trên nửa tiếng Việt**; trên nửa tiếng Anh nó khác cả hai bản (p = 0,0008 và
p = 0,0003) và nằm **ở giữa**.

Nguồn: `docs/benchmark/lookup_rule_lang_20260909_v2_b2.jsonl` (nửa vi, n = 200) ×
`docs/benchmark/lookup_rule_lang_20260910_v3.jsonl` (nửa en, n = 200).
Mẻ n = 50 cũ giữ lại để đối chiếu, **không trích vào bài**:
`lookup_rule_lang_20260909_v1.jsonl`, `lookup_rule_lang_20260909_v2.jsonl`.

### 4b. ADR-008 — ngôn ngữ trả lời · `[ĐO LẠI ĐƯỢC]` nhưng KHÔNG tái lập được

Bảng sáu điều kiện của ADR-008 (15/15 · 12/15 · 12/15 · **2/15** · 7/15 · **15/15**)
đến từ một mẻ A/B dựng tay — ADR chỉ ghi *"chạy A/B thật với Gemini trên đúng 15 câu
tiếng Anh của phiên đó, đúng persona + memory thật"*, **không nêu script, không nêu file
ra**. Đã soi `desktop/logs/` (12 file), `study/langconf/results/`, và toàn bộ
`latency.jsonl` (460 bản ghi): **không mẻ nào có 15 lượt tiếng Anh cho 2/15 hay 15/15**.
Mẻ gần nhất là 45/45 và 38/44, khác hẳn.

Cái còn giữ được: `desktop/logs/latency.jsonl` có 95 bản ghi `source=ui` của phiên giọng
thật 06/09 với `wrong_language` 19/95 — nhưng chúng **không mang `spoken_lang`**, nên
không tách được câu tiếng Anh ra để đếm. Không thay được cho bảng trên.

**Vì sao "đo lại được" phải kèm chữ *có điều kiện*:** hai trong sáu điều kiện cần
**"memory thật"** đúng như trạng thái ngày 06/09. `shared/memory/memory.v1.json` không
vào git (đúng theo `CLAUDE.md`) và đã đổi từ lâu. Chạy lại sẽ cho một phép đo **MỚI**
trên một trạng thái ký ức khác — **không phải tái lập**, và không được trình bày như tái
lập.

### Quyết định (việc 34): **`[BỎ]`**

Chủ nhân chốt phương án 2. **Con số `2/15 → 15/15` không vào bài.**

Lý do bỏ **không phải** vì khó đo lại — đo lại thì rẻ và im lặng. Lý do là **chỗ nó
đứng**: bài này nói về tính tái lập, và một con số không tái lập được, đặt ở bảng trung
tâm của một bài về tái lập, là chỗ tệ nhất có thể đặt nó.

Ba việc đã làm:

1. **Bảng 1 dòng 3: giữ dòng, gỡ số.** Giữ dòng vì tầng ấy có thật và cơ chế có thật —
   bỏ hẳn dòng thì khung ba tầng thủng một tầng và người đọc tưởng ta chưa xét. Ô "bằng
   chứng" ghi *(không mang số — xem Hạn chế 14)*, trạng thái đổi từ `[CÓ SỐ]` sang
   **`[QUYẾT ĐỊNH THIẾT KẾ]`**.
2. **Mục 4 giữ ADR-008** như quyết định thiết kế có ghi chép (kẹp nhãn ngôn ngữ ở lượt
   người dùng), không như kết quả đo.
3. **Hạn chế 14** nói thẳng: *dữ liệu thô của phép đo ngôn ngữ ngày 06/09 không được
   lưu giữ.*

Câu số 3 nghe như tự vạch áo. Trong một bài về tái lập thì nó là **uy tín**: nhóm tác
giả áp chính tiêu chuẩn của mình lên công việc cũ của mình và loại bỏ thứ không đạt.
Viết thẳng, không làm mềm.

Cơ chế **không mất chỗ dựa**: Mục 6bis đem đúng cơ chế ấy đi thử ở nhiệm vụ định tuyến —
dữ liệu đầy đủ, tái lập được — và nó trượt cả hai dự đoán. Đó là chỗ dựa **tốt hơn** chỗ
vừa bỏ, vì nó có file.

---

## 5. Định tuyến — tính tất định

### Bảng 5 — lấy mẫu (2 000 lượt)

| | temperature 0,8 (sản phẩm) | temperature 0 |
|---|---|---|
| câu 100 % nhất quán | 87/100 (Wilson 0,790–0,922) | **100/100** (Wilson 0,963–1,000) |
| flip rate | 3,30 % | **0,00 %** |
| entropy trung bình/câu | 0,0994 bit | **0,0000 bit** |

Cận trên 95 % của tỉ lệ lật ở `temperature=0` ≈ **0,3 %** (0/1000, quy tắc ba).
**7/8 câu bất ổn nhất là tiếng Anh.**
Nguồn: `docs/benchmark/lookup_determinism_20260909_v1.jsonl` (1 999 bản ghi —
1 000 âm / 999 dương).

### Bảng 6 — lịch sử, MỘT cột (recall)

| vị trí trong phiên | recall | Wilson 95 % |
|---|---|---|
| lượt đầu | 87,0 % | 0,790–0,922 |
| sau 3 lượt **không** cần tra | 93,0 % | 0,863–0,966 |
| sau 3 lượt **có** cần tra | 78,0 % | 0,689–0,850 |

n = 100 mỗi ô. Nguồn: `docs/benchmark/lookup_history_20260909_v1.jsonl` (300 bản ghi).

⚠ **Ô 78,0 % đọc theo J / precision, KHÔNG đọc theo mỗi recall.** Nó không phải ô tệ
nhất — nó **dè dặt nhất**, và ở bài toán này sai-âm mới là cái hại. Xem Bảng 6b.

### Bảng 6b — cùng ba vị trí, kèm nửa âm

| vị trí | recall | Wilson 95 % | **sai-dương** | J | bal. acc | precision |
|---|---|---|---|---|---|---|
| lượt đầu | 0,860 | 0,738–0,930 | 0,140 | 0,720 | 0,860 | 0,860 |
| sau 3 lượt **không** cần tra | 0,980 | 0,895–0,996 | 0,227 | 0,753 | 0,877 | 0,815 |
| sau 3 lượt **có** cần tra | 0,820 | 0,692–0,902 | **0,061** | **0,759** | **0,879** | **0,932** |

20 câu `fast-changing` + 20 câu `never-changing`, mỗi bên × 5 lần.
`sau-3-không-tra` vs `sau-3-có-tra`: z = **+3,012**, **p = 0,0026**.
Nguồn: `docs/benchmark/lookup_history_bang6_20260909_v1.jsonl` (299 bản ghi, nửa dương)
× `docs/benchmark/lookup_history_neutral_am_20260909_v1_b2.jsonl` (295 bản ghi, nửa âm).

### Bảng 7 — A/B câu từ chối (600 lượt)

| vị trí | A hằng số (Wilson 95 %) | B xoay vòng (Wilson 95 %) |
|---|---|---|
| lượt đầu | 84/100 (0,756–0,899) | 83/100 (0,745–0,891) |
| sau 3 lượt **không** cần tra | 91/100 (0,838–0,952) | 90/100 (0,826–0,945) |
| sau 3 lượt **có** cần tra | 76/100 (0,668–0,833) | 67/100 (0,573–0,754) |

Hiệu ứng lịch sử trong nhánh: A z = +2,858 (p = 0,0043); **B z = +3,959 (p = 0,0001)**.
Xoay vòng **không xoá được** hiệu ứng, còn mạnh thêm.

⚠ **Bảng này KHÔNG có nửa âm** — 600/600 bản ghi không mang `needs_lookup`. Chỉ được
dùng cho phép so A/B một biến; **không** để kết luận định tuyến tốt lên hay xấu đi.
Nguồn: `docs/benchmark/lookup_ab_refusal_20260909_v1.jsonl`.

### Cần gạt điểm vận hành — lịch sử theo ĐỘ DÀI

| lịch sử trước câu hỏi | recall | **sai-dương** | J | precision |
|---|---|---|---|---|
| không có (lượt đầu) | 0,820 | 0,130 | 0,690 | 0,863 |
| 3 lượt tán gẫu | 0,980 | 0,300 | 0,680 | 0,766 |
| 6 lượt tán gẫu | 1,000 | 0,440 | 0,560 | 0,694 |
| 9 lượt tán gẫu | 1,000 | 0,460 | 0,540 | 0,685 |
| sau 3 lượt bị từ chối | 0,800 | **0,030** | **0,770** | **0,964** |

Recall lên nhưng sai-dương lên nhanh hơn ⇒ **dời ngưỡng, không đổi năng lực**.
Sai-dương 0,460 so với 0,030 = **hơn 15 lần** số lượt tra vô ích trên cùng bộ câu.
Nguồn: `docs/benchmark/lookup_history_neutral_20260909_v1.jsonl` (nửa dương) ×
`docs/benchmark/lookup_history_neutral_am_20260909_v1.jsonl` (nửa âm).

### 5b. BỔ SUNG SAU KHI ĐÓNG SỔ — 10/09/2026, đợt 12 · ba cần gạt, một đường ROC

Khối này vốn chỉ nằm ở `PAPER-OUTLINE.md` §Mục 6ter, **chưa từng vào sổ** — `build_numbers.py`
bắt được lúc đối chiếu. Ghi vào đây vì Mục 6 của bài trích nó.

**Không có phép đo mới nào ở đây.** Mọi giá trị lấy từ ba mẻ đã có trong sổ; cái mới là
**đặt chúng cạnh nhau**.

| cần gạt | thay đổi | recall | **sai-dương** | **J** | nguồn |
|---|---|---|---|---|---|
| **① lấy mẫu** | `temperature` 0,8 → 0 | 0,726 → 0,739 | 0,056 → 0,060 | **+0,670 → +0,679** | `lookup_determinism_20260909_v1.jsonl` |
| **② lịch sử** | lượt đầu → 3 → 6 → 9 lượt tán gẫu | 0,820 → 0,980 → 1,000 → 1,000 | 0,130 → 0,300 → 0,440 → 0,460 | 0,690 → 0,680 → 0,560 → **0,540** | `lookup_history_neutral_*` |
| **②′ lịch sử** | sau 3 lượt bị từ chối | 0,800 | **0,030** | **0,770** | như trên |
| **③ câu chữ quy tắc** | vi → en → vi-v2 (gộp hai nửa) | 0,735 → 0,852 → 0,785 | 0,055 → 0,150 → 0,100 | **+0,680 / +0,702 / +0,685** | `lookup_rule_lang_*` |

Cần gạt ① trước nay chưa ai tính J cho nó; tính từ chính file tất định (file có sẵn cả hai
config: 1 000 âm / 999 dương).

#### Hai tập tỉ số — MỖI tỉ số ghi rõ tính trên tập nào

Trộn hai tập là đúng lỗi §4 của sổ này đã ghi, nên hai bảng đứng riêng.

**TẬP A — bảy cấu hình "bình thường"** (cả hai nhiệt độ · cả ba bản quy tắc, số gộp hai
nửa · lịch sử ở lượt đầu và sau 3 lượt tán gẫu):

| thước | thấp nhất | cao nhất | tỉ lệ |
|---|---|---|---|
| recall | 0,726 | 0,980 | 1,35× |
| **sai-dương** | 0,055 | 0,300 | **5,5×** |
| **J** | 0,670 | 0,702 | **1,05×** |

**TẬP B — mười điểm vận hành** = tập A + ba đầu cực đoan của cần gạt lịch sử (6 lượt tán
gẫu · 9 lượt tán gẫu · sau 3 lượt bị từ chối):

| thước | thấp nhất | cao nhất | tỉ lệ |
|---|---|---|---|
| recall | 0,726 | 1,000 | 1,38× |
| **sai-dương** | 0,030 | 0,460 | **15,3×** |
| **J** | 0,540 | 0,770 | **1,43×** |

Ở **cả hai** tập, sai-dương xê dịch hơn J khoảng **một bậc độ lớn**.

#### Ba chỗ phải nói thật, giữ nguyên khi chuyển sang văn xuôi

1. **J giữa ba cần gạt là so ƯỚC LỆ.** Ba mẻ chạy trên ba bộ câu khác nhau (bộ 100 câu của
   mẻ tất định, bộ 50/50 của lưới quy tắc, bộ 40 câu của mẻ lịch sử). So **trong** từng cần
   gạt thì chính xác; so **giữa** các cần gạt chỉ đọc được như "cùng một khoảng độ lớn".
2. **Một cần gạt ĐỔI được J, và đổi theo chiều XẤU** (tán gẫu 6–9 lượt: 0,690 → 0,540). Nên
   câu "không cần gạt nào đổi năng lực" là **sai**; câu đúng là *không cần gạt nào đổi năng
   lực theo chiều TỐT*.
3. **Điểm J cao nhất (0,770) đến từ cấu hình không ai thiết kế** — nó là **đối chứng** của
   phép thử khác, và lúc đầu còn bị đọc là ô tệ nhất vì recall thấp nhất bảng. **Chưa** thử
   biến nó thành cần gạt cố ý; không viết như thể đã thử.

**Ba tỉ số cũ đã bị gỡ vì trộn tập** (ghi lại để không ai tính ngược rồi tưởng có bản khác):
`1,96×` recall và `92×` sai-dương lấy đáy từ **ô một nửa ngôn ngữ** rồi ghép với đỉnh của tập
lịch sử; ô một nửa ngôn ngữ không phải một điểm vận hành so được. `1,43×` thì đúng nhưng là
số của **tập B**, không phải tập A.

---

## 6. Độ trễ

| số | giá trị | n | nguồn |
|---|---|---|---|
| e2e p50 / p95, baseline v3 | 5 129 / **7 649** ms | 90 | `docs/baseline/latency_desktop_baseline_2026-09-06_v3.jsonl` |
| e2e p50 / p95, giọng thật v2 | 4 824 / 7 483 ms | 31 | `docs/baseline/latency_desktop_realvoice_2026-09-06_v2.jsonl` |
| e2e p50 / p95, replay v3 | 5 418 / 7 986 ms | 31 | `docs/baseline/latency_desktop_replay_2026-09-06_v3.jsonl` |
| e2e thật qua board (vòng lặp hoàn chỉnh chạy được) | — | — | `docs/benchmark/latency_es3c28p_hwtest_20260908.jsonl` |
| grounding: lời gọi thứ hai | 3 186 / 3 999 ms | 15 lượt có tra | `docs/benchmark/grounding_20260909_v1.jsonl` |
| grounding: câu báo trước xuống TTS | **923** / 1 130 ms | như trên | như trên |
| grounding: `t_answer_first` | **4 008** / 5 239 ms | như trên | như trên |
| lượt KHÔNG tra, chữ đầu | 820 / 917 ms | như trên | như trên |
| 15/15 lượt trả về ≥ 1 nguồn (p50 = 3 nguồn) | — | 15 | như trên |

**Hai con số về cùng một lượt, phải báo cả hai:** 4,9× tới câu trả lời thật, nhưng chỉ
**+103 ms** tới lúc người dùng nghe thấy vịt. Phân bố **lưỡng cực**, không lấy trung
bình chung.

Cấu hình lúc đo: `docs/baseline/baseline_config_2026-09-06_v3.json` (v0–v2 cho các mẻ
trước). Chi phí grounding: 1 500 lượt/ngày miễn phí, sau đó $35/1 000 lượt (ADR-010 §4).

### Giả tượng khởi động nguội — đã kiểm, ảnh hưởng **bằng 0**

`intents.schema.validator()` nạp `jsonschema` lười: lần gọi đầu trong một tiến trình
**87,7 ms** (đo lại 10/09 trên cùng máy: 100,8–119,4 ms khi page cache còn ấm;
**455,5 ms** ở lần import đầu sau khởi động). Lần hai 0,001 ms; mỗi `check()` sau đó
0,12 ms.

`bench_latency.py` **KHÔNG** làm nóng validator trước khi bấm giờ, và
`IntentBus.__init__` chỉ gọi `validator()` từ commit `0ade42e` (09/09/2026) — **sau**
mọi mẻ baseline (05/09 và 06/09). Khoản ấy rơi vào quãng `t_llm_first → t_tts_first`
(mốc `t_llm_first` được đánh trước `use_affect` → `bus.send("express")`), chỉ ở **lượt
đầu của mỗi tiến trình**: 3/90 với các file 90 lượt, 1/30–31 với các file còn lại.

| giả định | p50 | p95 | trung bình |
|---|---|---|---|
| 87,7 ms | **0,00 ms** (7/7 file) | **0,00 ms** (7/7 file) | −2,83 … −3,02 ms (≈ 0,06 %) |
| 455,5 ms (cực đoan) | 0,00 ms ở 6/7 file; `2026-09-06_v2` −5,5 ms | 0,00 ms (7/7 file) | −14,7 … −15,7 ms |

**Không sửa dữ liệu, không chạy lại `docs/baseline/`** — chạy lại là mất tính đối chứng.

---

## 7. Kết cục của mọi nhóm số — §7 đã rỗng

**§7 ĐÃ RỖNG.** Không còn nhóm số nào chưa phân loại. Kết cục của cả sáu nhóm:

| nhóm số | nhãn | ở đâu |
|---|---|---|
| device floor mẻ 06/09 — `t_rx_first`, RTT, jitter, cỡ khung | **`[TRUY ĐƯỢC]`** | §1b |
| device floor mẻ 09/09 — nt. + lệch hai nhóm | **`[TRUY ĐƯỢC]`** (vài số đã đổi, RTT p95 gỡ) | §1c |
| ADR-004 — WER/CER/`t_stt` sáu backend, 6/31 | **`[TRUY ĐƯỢC]`** | §3c |
| ADR-007 — bộ 23,2 s và hai WER | **`[TRUY ĐƯỢC]`** | §3b |
| ADR-007 — **p95 −40,4 %** (tái lập) | **`[TRUY ĐƯỢC]`** — đo lại xong 10/09, việc 33 | §3b |
| ADR-008 — 2/15 → 15/15 | **`[BỎ]`** — gỡ khỏi Bảng 1, thô không còn | §4b · Hạn chế 14 |

Hai nhóm ngoài luật, giữ nguyên và đã ghi rõ là ngoài luật:

| số | vì sao ngoài luật |
|---|---|
| nhịp vẽ mặt 21 → 24,5 fps (Mục 2) | quan sát trong SESSION-06, không có file đo. **Nêu như quan sát, không in như số đo của bài.** |
| ViSQA: exact match 62,04 % → 36,30 % (Mục 3) | **số của người khác**, trích theo DOI — luật "phải có file trong `docs/`" không áp cho số trích dẫn |
| **`3/16` — thước cũ quy oan cho LLM** (Mục 4) | **thiếu cả n lẫn KTC, và không truy được về file nào trong `docs/`.** Theo luật ⇒ **KHÔNG ĐƯỢC VÀO BÀI.** Đây không phải chỗ thiếu câu chữ — đừng để `[[TODO]]` mờ rồi lúc viết đè lại tưởng chỉ cần diễn đạt lại |

**Cả hai số từng chờ quyết định nay đã chốt:** dòng 2 (STT) đo lại xong và thành
`[TRUY ĐƯỢC]` (việc 33); dòng 3 (ngôn ngữ trả lời) đã `[BỎ]` (việc 34). Không còn dòng
nào trong Bảng 1 ở trạng thái chờ.

---

## 8. Kiểm tra năm thứ — mỗi số vào bài phải có đủ

Luật đóng sổ: **giá trị · n · khoảng tin cậy (nếu là tỉ lệ) · đường dẫn file trong
`docs/` · quy ước (phân vị · lát cắt hàng · thước WER — cái nào áp dụng)**. Thiếu bất kỳ
thứ nào thì hoặc bổ sung, hoặc gỡ số khỏi bài. Không ngoại lệ.

| nhóm số | giá trị | n | KTC | file | quy ước |
|---|---|---|---|---|---|
| device floor 06/09 (§1b) | ✓ | ✓ 47 | — *(không phải tỉ lệ)* | ✓ | ✓ phân vị + lát cắt |
| device floor 09/09 (§1c) | ✓ | ✓ 59 | — | ✓ | ✓ phân vị + lát cắt |
| grounding một đêm (§2) | ✓ | ✓ 30 / 21 / 9 | ✓ Wilson | ✓ | ✓ lát cắt (toàn mẻ) |
| Bảng 2 · 3 · 4 (§3) | ✓ | ✓ | ✓ Wilson | ✓ | ✓ lát cắt (khối A / khối B) |
| ADR-007 tái lập (§3b) | ✓ | ✓ 30/ô, 10 câu | ✓ Wilson | ✓ | ✓ cả ba: phân vị · lát cắt · thước WER |
| ADR-004 backend STT (§3c) | ✓ | ✓ 31 | — *(WER không phải tỉ lệ nhị phân)* | ✓ | ✓ thước WER (D-WER) ghi rõ |
| Bảng 2b lưới 2×3 (§4) | ✓ | ✓ 200/ô | ✓ Wilson cả recall lẫn sai-dương | ✓ | ✓ lát cắt (25 câu × 8 lần) |
| Bảng 5 · 6 · 6b · 7 · cần gạt (§5) | ✓ | ✓ | ✓ Wilson | ✓ | ✓ lát cắt |
| độ trễ + giả tượng 88 ms (§6) | ✓ | ✓ 90 / 31 | — | ✓ | ✓ phân vị `_pct` |

**Ba chỗ cố ý để trống KTC, và lý do:** Jaccard tên miền là **trung bình**, không phải
tỉ lệ nhị phân; WER là tỉ số lỗi trên độ dài tham chiếu, KTC nhị thức không áp được; các
mốc độ trễ là phân vị của một phân phối, không phải tỉ lệ. Ba chỗ ấy ghi "—" chứ không
bỏ trống.

**Hai chỗ KTC rộng phải đọc kỹ:** `0/30` của grounding cho cận trên **10 %** (quy tắc
ba) — dùng con số ấy, đừng dùng "0 %". Và `0/10` của tất định STT cho cận trên **27,8 %**
— mẻ ấy chứng minh **chiều**, không chứng minh độ lớn.

---

## 9. Đã cắt khỏi bài này — liệt kê để lần sau không ai đi tìm lại

| cắt cái gì | vì sao | còn lại gì |
|---|---|---|
| **So wake word khoá-nhà-cung-cấp vs tự-huấn-luyện** ("Hi Jolly" WakeNet vs "Hi Ducky" microWakeWord) | đòi nhiều vòng huấn luyện Colab + một lần build/flash; Mục 5–7 tự chúng đã đủ dày. **Cắt vì đủ, không phải vì làm không được** | ràng buộc nền tảng vẫn nêu **một câu** ở Mục 2 (model đúc sẵn khoá theo nhà cung cấp; tên riêng thì $1 000 hoặc 20 000 mẫu). Khảo sát rủi ro ở ADR-013 §9–§13 |
| **Chặng xuống server → loa** (Bảng 2 và 3 của `DEVICE-FLOOR.md`) | firmware v2.3.0 không báo ngược `t_dev_ack` (rỗng 47/47) nên không đo từ xa được | chặng **lên** có số và tái lập được qua hai mạng (§1b, §1c). Hạn chế 12 |
| **Loopback vật lý mic → loa** | bắt buộc phát tiếng ra loa board, nằm ngoài phạm vi bài | `latency_es3c28p_hwtest_20260908.jsonl` đủ để nói vòng lặp hoàn chỉnh chạy được |
| **`2/15 → 15/15` của ADR-008** | thô không còn; hai trong sáu điều kiện cần ký ức đúng ngày 06/09, mà `memory.v1.json` không vào git và đã đổi → chạy lại là phép đo **mới** | Bảng 1 giữ **dòng**, gỡ **số**. Mục 4 giữ ADR-008 như *quyết định thiết kế*. Cơ chế có chỗ dựa tốt hơn ở Mục 6bis — đo được, tái lập được. Hạn chế 14 |
| **Nửa âm 600 lượt của Bảng 7** | mẻ gốc chỉ chạy nửa dương (600/600 bản ghi không mang `needs_lookup`) | Bảng 7 chỉ dùng cho phép so A/B một biến. Bảng 6b và mẻ việc 18 (đều có nửa âm) mới trả lời câu "tốt lên hay xấu đi". Hạn chế 13 |
| **Con số `−55,8 %` của `phowhisper-reread`** (§3b) | ô kém ổn định nhất: p95 nhánh cũ dựa lên 2 lượt chậm trong 30; ADR-007 báo −17 % ở cùng ô | trích **chiều**, không trích độ lớn |
| **Con số `RTT p95 109,2 ms`** của mẻ 09/09 | **không tồn tại trong dữ liệu** — mọi bản ghi của phiên mang `rtt_p50` = 4,65 | phát biểu đúng: RTT trong phiên là **hằng số 4,65 ms**. §1c |
| **Ba tỉ số `1,96×` · `92×` · `1,43×`** (bản cũ của Mục 6ter) | trộn hai tập: lấy đáy từ ô một nửa ngôn ngữ rồi ghép với đỉnh của tập lịch sử | hai bảng tỉ số tách theo tập A / tập B, Mục 6ter |

**Ba nhóm số ngoài luật, giữ nguyên và đã ghi rõ là ngoài luật:** nhịp vẽ mặt
21 → 24,5 fps (SESSION-06, không có file đo — nêu như *quan sát*, không in như số đo);
ViSQA 62,04 % → 36,30 % (**số của người khác**, trích theo DOI); và WER nhánh cũ
`phowhisper-reread` 0,218 của ADR-007 (không có trong file nào — **không trích**).

---

---

## 10. BỔ SUNG SAU KHI ĐÓNG SỔ — 12/09/2026, đợt 24 · κ INTRA-RATER (test–retest)

Vòng gán nhãn thứ hai do **chính người gán vòng một** thực hiện, trên bộ đã làm mù
(`docs/benchmark/lookup_set_vi_blind.csv`, cột `needs_lookup_vong2`). Đây là
**intra-rater (test–retest) reliability** — **KHÔNG** phải inter-rater; cùng một người,
hai lượt.

**Script:** `desktop/scripts/kappa.py`
**Kết quả máy đọc được:** `docs/benchmark/kappa_vi_20260912.json`

### 10a. Con số vào bài

| đại lượng | giá trị | n | quy ước / nguồn |
|---|---|---|---|
| **κ (Cohen), nhị phân** | **0,880** | 50 cặp | *cần tra* / *không cần tra*; khối A của bộ mù |
| **KTC 95 % cho κ** | **[0,721 – 1,000]** | 50 cặp | **bootstrap trên cặp**, B = 10 000, **seed = 20260912** |
| **đồng thuận thô** | **0,940** | 50 cặp | 47/50 khớp |
| **số câu bất đồng** | **3/50** | — | Q016 · Q027 · Q036 |
| **biên vòng 1** | cần tra **25** (50 %) · không **25** (50 %) | 50 | — |
| **biên vòng 2** | cần tra **26** (52 %) · không **24** (48 %) | 50 | — |
| **κ 4 lớp** (`fact_type` × nhãn) | 0,907 · thô 0,940 | 50 | phân tầng, **không** đọc như gán bốn lớp độc lập |

**Vì sao in cả ba con số cạnh nhau (κ · thô · biên):** nghịch lý kappa. Khi biên lệch
mạnh, κ tụt dù đồng thuận thô cao, nên một con số κ trần không đọc được. Ở đây biên hai
vòng **gần cân và gần nhau** (25/25 so với 26/24) ⇒ κ **không** bị méo, đọc thẳng được.
Ghi ra để người đọc tự kiểm, không bắt tin.

**Vì sao bootstrap chứ không dùng công thức tiệm cận:** n = 50 với **chỉ 3 chỗ bất đồng**
⇒ phân phối của κ ở đây rời rạc và lệch, đúng vùng mà sai số chuẩn tiệm cận nói dối.
Cận trên của KTC **chạm 1,000**, và đó là tính chất thật của mẫu chứ không phải lỗi: một
phần mẫu bootstrap rút trúng 0 chỗ bất đồng ⇒ κ = 1. 10 000/10 000 mẫu dùng được, 0 mẫu
suy biến.

**⛔ KHÔNG dán nhãn Landis–Koch** (*"substantial"*, *"almost perfect"*) lên con số này.
Ngưỡng ấy tuỳ tiện và người phản biện IR biết. In số, KTC, thô, biên — để người đọc tự đọc.

**⛔ κ đo NHẤT QUÁN, không đo HỢP LỆ.** Một người hiểu sai định nghĩa theo cùng một kiểu
hai lần vẫn cho κ cao. Câu trong Hạn chế phải nói thẳng điều này.

### 10b. Bất đồng theo `fact_type` — **KHÔNG có mẫu hình hệ thống**

| `fact_type` | bất đồng | tổng | tỉ lệ |
|---|---|---|---|
| `fast-changing` | 0 | 15 | 0,0 % |
| `never-changing` | 2 | 25 | 8,0 % |
| `slow-changing` | 1 | 10 | 10,0 % |

**Đọc đúng bảng này:** 8 % và 10 % **cách nhau đúng một câu**. Với **3** chỗ bất đồng
trên cả bộ, không có tập trung nào để nói tới. Giả thuyết đi vào đợt này — *"bất đồng sẽ
dồn vào `slow-changing`, vùng xám của Mục 5"* — **không được dữ liệu đỡ**, và ghi lại đây
như một giả thuyết bị bác bỏ chứ không sửa lặng lẽ.

⇒ **Không viết câu nào vào Phương pháp** về `fact_type` kém ổn định. Viết là đọc nhiễu
thành tín hiệu.

Ba câu bất đồng, đọc từng câu:

| id | `fact_type` | v1 → v2 | ghi chú |
|---|---|---|---|
| Q016 | `slow-changing` | 1 → 0 | *"Tuyến metro nào ở TP.HCM đang chạy?"* — vòng 1 **đã tự đánh dấu `borderline`**. Câu biên thật, và nó tự khai là biên |
| Q027 | `never-changing` | 0 → 1 | *"Nguyễn Trãi viết Bình Ngô đại cáo trong hoàn cảnh nào?"* |
| Q036 | `never-changing` | 0 → 1 | *"Giao thức TCP khác UDP ở điểm nào?"* |

### 10c. Tiền đề sai — bất đồng về **LOẠI câu**, đếm riêng

Khối B của bộ mù là **10 câu tiền đề sai** (`needs_premise_vong1 = True`, không câu nào
có nhãn `lookup` ở vòng 1). Vòng 2 khai tiền đề sai bằng cách **để trống nhãn kèm ghi chú**.

| | |
|---|---|
| vòng 1 xếp tiền đề sai | **10** |
| vòng 2 **cũng nhận ra** | **6/10** |
| vòng 2 **bỏ sót** (gán nhãn thường `0`) | **4/10** — Q011 · Q041 · Q050 · Q060 |
| vòng 2 kêu tiền đề sai mà vòng 1 thì không | **0** |

**Đây KHÔNG vào κ**, và không được gộp vào κ: κ ở §9a tính trên **khối A** (50 câu *có*
nhãn ở vòng 1). Hai con số đo hai thứ khác nhau — một cái là *nhãn có lặp lại không*, cái
kia là *loại câu có được nhận ra không*.

⚠ **Một cái bẫy của chính `kappa.py`, ghi lại vì nó suýt giấu con số 4/10:** dòng
*"⚠ N câu CHƯA gán"* in ra **0**, và con số 0 ấy đúng theo nghĩa hẹp nhưng gây hiểu nhầm.
Vòng lặp kiểm `needs_lookup_vong1` **trước** rồi mới kiểm vòng 2, nên câu nào vòng 1 không
có nhãn thì `continue` sớm và **không bao giờ** tăng biến ấy. Mười câu khối B nằm ngoài
phép tính mà bộ đếm vẫn báo 0. Phải dựng **bảng chéo đầy đủ** mới thấy. Cùng một hình
dạng lỗi mà Mục 9b của bài liệt kê: một bộ đếm trả lời đúng **một câu hỏi khác** với câu
người đọc nó tưởng.

### 10d. Nhãn vòng 2 là **dữ liệu đo**

`docs/benchmark/lookup_set_vi_blind.csv` nay mang cột `needs_lookup_vong2` đã điền. Nó
**chưa** nằm trong gói dữ liệu công khai `v1.0` (đẩy 12/09, trước khi có vòng 2). Vào
`v1.1` khi nào chủ nhân quyết đẩy tiếp.

---

**`PAPER-NUMBERS.md` đóng sổ 10/09/2026**, và mọi mục có nhãn *BỔ SUNG SAU KHI ĐÓNG SỔ* ở trên là phần thêm sau, mỗi mục ghi rõ ngày. Mọi con số trong bài truy được về một file
trong `docs/benchmark/` hoặc `docs/baseline/`, kèm n, KTC nếu là tỉ lệ, và quy ước.

## 11. BỔ SUNG SAU KHI ĐÓNG SỔ — 23/09/2026, đợt 27f · MẺ ĐĂNG KÝ TRƯỚC M1–M7 (16–23/09)

Mọi số trong mục này sinh bằng máy từ các file dưới đây, ngày chấm 2026-09-23T13:36:04.
Luật chấm: docs/benchmark/PREREG_M1-M4_20260916.md §A04.3–A04.5 + A06. Mốc mù (A04.5): 2026-09-17T07:48:33+07:00, commit 015c0e7.

| thứ | file |
|---|---|
| M3 grounding | `docs/benchmark/M3_20260916_v1.jsonl` (425 bản ghi, tất cả `ok`) |
| M6 oracle | `docs/benchmark/M6_20260918_v1.jsonl` (20 lần, tất cả `ok`) |
| chấm M6/M7 | `docs/benchmark/M6_M7_cham_20260923.json` |
| lỗi thoáng qua | `docs/benchmark/M1_20260916_v1.errors.jsonl` và hai file cùng dạng của M3, M6 |

### 11a. M3 — grounding qua 14 mốc cách nhau 12 h · đường cong PHẲNG, không suy giảm

So từng mốc với **mốc 1**. Cột *giờ thực đo* in cạnh giờ danh nghĩa theo I-15 và I-19: mốc 4 và mốc 5
chạy muộn vì máy ngủ, nên số của chúng đo ở giờ thực, không phải giờ danh nghĩa.

| j | mốc (danh nghĩa) | giờ thực đo | `lookup` đổi | domain-set đổi | text đổi |
|---|---|---|---|---|---|
| 1 | 2026-09-16 21:00 | 21:00:03 | 0/30 | 0/30 | 0/30 |
| 2 | 2026-09-17 09:00 | 09:00:00 | 1/30 | 20/30 | 21/30 |
| 3 | 2026-09-17 21:00 | 21:00:10 | 1/30 | 18/30 | 21/30 |
| 4 | 2026-09-18 09:00 | 10:46:35 | 1/30 | 20/30 | 21/30 |
| 5 | 2026-09-18 21:00 | 21:37:33 | 0/30 | 19/30 | 20/30 |
| 6 | 2026-09-19 09:00 | 09:00:00 | 2/30 | 19/30 | 21/30 |
| 7 | 2026-09-19 21:00 | 21:00:00 | 1/30 | 20/30 | 21/30 |
| 8 | 2026-09-20 09:00 | 09:00:00 | 1/30 | 20/30 | 21/30 |
| 9 | 2026-09-20 21:00 | 21:00:01 | 1/30 | 19/30 | 21/30 |
| 10 | 2026-09-21 09:00 | 09:00:00 | 1/30 | 19/30 | 21/30 |
| 11 | 2026-09-21 21:00 | 21:00:00 | 1/30 | 17/30 | 20/30 |
| 12 | 2026-09-22 09:00 | 09:00:00 | 0/30 | 21/30 | 21/30 |
| 13 | 2026-09-22 21:00 | 21:00:00 | 1/30 | 21/30 | 21/30 |
| 14 | 2026-09-23 09:00 | 09:00:00 | 0/30 | 20/30 | 21/30 |

Mốc 1 so chính nó là 0/30 ở cả ba cột (kiểm tra vệ sinh). Từ **mốc 2 trở đi không có xu hướng theo
thời gian**: domain-set đổi dao động 17–21/30 và text đổi 20–21/30 suốt 13 mốc trải 6,5 ngày.
Bất ổn xuất hiện **ngay ở khoảng cách 12 h đầu tiên** rồi đứng yên; nó không tích luỹ theo thời gian.
Theo prereg, curve là **mô tả**, không khớp mô hình suy giảm nào.

### 11a-bis. Chỉ trên 20 câu CÓ tra ở mốc 1 (mốc 14 so mốc 1)

| quan sát | đổi | tỉ lệ | KTC 95 % |
|---|---|---|---|
| domain-set | 19/20 | 0,950 | Wilson 0,764–0,991 |
| text trả lời | 20/20 | 1,000 | Wilson 0,839–1,000 |

### 11a-ter. Đối chứng âm `probe-nosearch` (A01.3) — GIỮ TÁCH khỏi mẫu số curve

Mẫu số của curve là **360 = 12 mốc × 30 câu** dữ liệu; 5 bản ghi probe dưới đây là
**đối chứng âm riêng**, không bao giờ cộng vào 360. Chúng chạy với `search=False` để kiểm ranh giới
*search tới model ⇔ `grounded=True` có `n_sources > 0`*:

| task_id | `lookup` | `grounded` | `n_sources` |
|---|---|---|---|
| `M3|probe-nosearch|vi-fast-001` | True | False | 0 |
| `M3|probe-nosearch|vi-fast-002` | True | False | 0 |
| `M3|probe-nosearch|vi-fast-003` | True | False | 0 |
| `M3|probe-nosearch|vi-fast-004` | True | False | 0 |
| `M3|probe-nosearch|vi-fast-005` | True | False | 0 |

Cả 5 câu: `lookup` vẫn bật mà `grounded` tắt và `n_sources` = 0 — ranh giới đúng
chiều, không có grounding lén.

### 11b. M6 — biên flake(artefact) − flake(decision), 4 ô

**Nhãn đơn vị (bắt buộc):** mọi số ở bảng này là *k of n tests flaky across 19 runs* — đếm **test**,
gộp qua 19 lần chạy so với golden `M6|lan01`. Đừng đọc lẫn với bảng 11b-bis, nơi
đơn vị là *k of n tests failing in run r* — đếm test **trong một lần chạy**.

| ô | loại | decision: test flaky / 19 lần | artefact: test flaky / 19 lần | biên art − dec | KTC 95 % (Newcombe) |
|---|---|---|---|---|---|
| `routing-hosted` | delegated | 10/40 | 40/40 | 0,750 | 0,575–0,858 |
| `routing-local` | pinnable | 0/40 | 0/40 | 0,000 | −0,088–0,088 |
| `stt-hosted` | delegated | 0/23 | 1/23 | 0,043 | −0,104–0,210 |
| `stt-local` | pinnable | 0/23 | 0/23 | 0,000 | −0,143–0,143 |

**Đọc cho đúng, một lần, để Discussion không hứa quá:** ở `routing-hosted`, bộ decision **cũng
flake** — 10/40 tests flaky across 19 runs, không phải 0. Kết quả của M6 là **biên** 0,750 với
KTC 0,575–0,858, nghĩa là *decision-level assertions flake ÍT HƠN*, **không** phải *không flake*.
Câu 'assert the decision, log the artefact' phải đọc như một đánh đổi đo được, không như lời hứa
tuyệt đối. Hai ô pinnable (`routing-local`, `stt-local`) có 0/40 và 0/23 nên biên bằng 0 và KTC phủ
cả hai phía — ở đó M6 không phân biệt được hai bộ oracle, và điều đó cũng phải in.

### 11b-bis. M6 tách theo KHOẢNG CÁCH tới golden — không báo một con số gộp

Luật (chốt 23/09): lần chạy cách golden 22 phút vì máy ngủ (I-15) báo **riêng** với 18 lần theo lịch.
**Nhãn đơn vị:** mọi số ở bảng này là *k of n tests failing in run r* — đếm test **trong một lần
chạy**, mẫu số 252 = 126 test × 2 bộ oracle. KHÁC đơn vị của bảng 11b.

| lần | giờ chạy | cách golden | decision: test hỏng / 252 | artefact: test hỏng / 252 |
|---|---|---|---|---|
| 2 | 2026-09-18 10:25:11 | 0,37 h | 0 | 31 |
| 3 | 2026-09-18 11:45:32 | 1,71 h | 3 | 36 |
| 4 | 2026-09-18 15:30:21 | 5,46 h | 1 | 33 |
| 5 | 2026-09-18 21:23:12 | 11,34 h | 3 | 32 |
| 6 | 2026-09-19 01:32:21 | 15,49 h | 0 | 34 |
| 7 | 2026-09-19 05:30:31 | 19,46 h | 3 | 31 |
| 8 | 2026-09-19 11:30:30 | 25,46 h | 2 | 32 |
| 9 | 2026-09-19 15:32:07 | 29,49 h | 4 | 33 |
| 10 | 2026-09-19 19:30:31 | 33,46 h | 3 | 33 |
| 11 | 2026-09-20 01:30:31 | 39,46 h | 1 | 30 |
| 12 | 2026-09-20 05:30:30 | 43,46 h | 2 | 34 |
| 13 | 2026-09-20 11:30:42 | 49,47 h | 3 | 35 |
| 14 | 2026-09-20 15:30:30 | 53,46 h | 1 | 33 |
| 15 | 2026-09-20 19:30:30 | 57,46 h | 4 | 34 |
| 16 | 2026-09-21 01:30:32 | 63,46 h | 1 | 33 |
| 17 | 2026-09-21 05:30:30 | 67,46 h | 1 | 32 |
| 18 | 2026-09-21 11:30:30 | 73,46 h | 1 | 37 |
| 19 | 2026-09-21 15:30:30 | 77,46 h | 2 | 35 |
| 20 | 2026-09-21 19:30:30 | 81,46 h | 2 | 35 |

**Lần 2, cách golden 0,37 h (22 phút):** decision fail **0**, artefact fail **31**/252.
**18 lần còn lại, cách golden 1,71–81,46 h:** decision fail 0–4, artefact fail 30–37.

Đây là bằng chứng **bảo thủ**, thuộc Results chứ không phải Threats: ở khoảng cách 22 phút — ngắn hơn
lịch đăng ký một bậc — bộ artefact đã hỏng 31 test còn bộ decision hỏng 0. Bất ổn
của artefact không cần thời gian để xuất hiện, nên việc máy ngủ làm lịch không đều **không** tạo ra kết quả này.

### 11c. M7 — ma trận dự đoán, 15 đơn vị chấm

Đúng **9** · sai **4** · không phân định **2** · thiếu lực không tính **3** · loại theo A06 **11** · chưa có cặp mù **0**.

| ô | tầng | quan sát | pinnability | dự đoán | nguồn | k/n | KTC 95 % (Wilson) | phán quyết |
|---|---|---|---|---|---|---|---|---|
| 1 | STT | nhãn ngôn ngữ | delegated | ổn định | S1 | 0/31 | 0,000–0,110 | không phân định (thiếu lực) |
| 1 | STT | nhãn ngôn ngữ | delegated | ổn định | S2 | 0/110 | 0,000–0,034 | đúng |
| 1 | STT | nhãn ngôn ngữ | delegated | ổn định | S3 | 0/205 | 0,000–0,018 | đúng |
| 2 | STT | transcript | delegated | không | S1 | 3/31 | 0,034–0,249 | sai |
| 2 | STT | transcript | delegated | không | S2 | 13/110 | 0,070–0,192 | sai |
| 2 | STT | transcript | delegated | không | S3 | 9/205 | 0,023–0,081 | sai |
| 3 | STT | nhãn ngôn ngữ | pinnable | ổn định | S1 | 0/31 | 0,000–0,110 | không phân định (thiếu lực) |
| 3 | STT | nhãn ngôn ngữ | pinnable | ổn định | S2 | 0/110 | 0,000–0,034 | đúng |
| 3 | STT | nhãn ngôn ngữ | pinnable | ổn định | S3 | 0/205 | 0,000–0,018 | đúng |
| 4 | STT | transcript | pinnable | ổn định | S1 | 0/31 | 0,000–0,110 | không phân định (thiếu lực) |
| 4 | STT | transcript | pinnable | ổn định | S2 | 0/110 | 0,000–0,034 | đúng |
| 4 | STT | transcript | pinnable | ổn định | S3 | 0/205 | 0,000–0,018 | đúng |
| 5 | routing | lookup | delegated t=0.8 | ổn định | M2 | 1/100 | 0,002–0,054 | đúng |
| 5 | routing | lookup | delegated t=0.8 | ổn định | M6 | 2/40 | 0,014–0,165 | không phân định |
| 6 | routing | text thô | delegated t=0.8 | không | M2 | 80/100 | 0,711–0,867 | đúng |
| 6 | routing | text thô | delegated t=0.8 | không | M6 | 34/40 | 0,709–0,929 | đúng |
| 7 | routing | lookup | delegated t=0.0 | ổn định | M2 | 0/100 | 0,000–0,037 | đúng |
| 8 | routing | text thô | delegated t=0.0 | không | M2 | 13/100 | 0,078–0,210 | không phân định |
| 9 | routing | lookup | pinnable qwen 7b | ổn định | M2 | 0/100 | 0,000–0,037 | đúng |
| 9 | routing | lookup | pinnable qwen 7b | ổn định | M6 | 0/40 | 0,000–0,088 | đúng |
| 10 | routing | text thô | pinnable qwen 7b | ổn định | M2 | 1/100 | 0,002–0,054 | đúng |
| 10 | routing | text thô | pinnable qwen 7b | ổn định | M6 | 0/40 | 0,000–0,088 | đúng |
| 11 | ngôn ngữ trả lời | nhãn | pinnable 7b | ổn định | M4 | 1/50 | 0,004–0,105 | không phân định |
| 12 | ngôn ngữ trả lời | reply_text | pinnable 7b | ổn định | M4 | 9/50 | 0,098–0,308 | sai |
| 13 | ngôn ngữ trả lời | nhãn | pinnable 3b | ổn định | M4 | 1/50 | 0,004–0,105 | không phân định |
| 14 | ngôn ngữ trả lời | reply_text | pinnable 3b | ổn định | M4 | 4/50 | 0,032–0,188 | không phân định |
| 15 | grounding | lookup | delegated | ổn định | M3 | 0/30 | 0,000–0,114 | không phân định (thiếu lực) |
| 16 | grounding | domain-set | delegated | không | M3 | 20/30 | 0,488–0,808 | đúng |
| 17 | grounding | text | delegated | không | M3 | 21/30 | 0,521–0,833 | đúng |

**4 đơn vị NGƯỢC dự đoán — in nguyên, không giấu:**

- **ô 2 (STT, transcript, delegated), nguồn S1** — dự đoán *không*, đo được 3/31 = 0,097, Wilson 0,034–0,249.
- **ô 2 (STT, transcript, delegated), nguồn S2** — dự đoán *không*, đo được 13/110 = 0,118, Wilson 0,070–0,192.
- **ô 2 (STT, transcript, delegated), nguồn S3** — dự đoán *không*, đo được 9/205 = 0,044, Wilson 0,023–0,081.
- **ô 12 (ngôn ngữ trả lời, reply_text, pinnable 7b), nguồn M4** — dự đoán *ổn định*, đo được 9/50 = 0,180, Wilson 0,098–0,308.

Phép kiểm (c) *depth*: hỗ trợ **2**, bác **1**, không phân định **0** trên 3 nhóm:

- *delegated × decision* → **hỗ trợ (c)** (ô 1/S1 0/31, ô 1/S2 0/110, ô 1/S3 0/205, ô 5/M6 2/40)
- *delegated × artefact* → **bác (c)** (ô 2/S3 9/205, ô 6/M6 34/40)
- *caller-pinnable × artefact* → **hỗ trợ (c)** (ô 4/S1 0/31, ô 4/S2 0/110, ô 4/S3 0/205, ô 10/M2 1/100, ô 10/M6 0/40)

### 11d. Lỗi thoáng qua — `error` đếm 0 nhưng KHÔNG phải không có lỗi

`status` in `error 0` vì mọi task cuối cùng đều `ok`. Ba file `*.errors.jsonl` giữ các lần thử HỎNG đã
được thử lại thành công; prereg đòi in tỉ lệ *task từng lỗi* cạnh kết quả, nên chúng phải được đếm:

| file | số dòng | mã lỗi |
|---|---|---|
| `docs/benchmark/M1_20260916_v1.errors.jsonl` | 2 |  |
| `docs/benchmark/M3_20260916_v1.errors.jsonl` | 1 |  |
| `docs/benchmark/M6_20260918_v1.errors.jsonl` | 2 |  |
| **tổng** | **5** | đều là 503 UNAVAILABLE hoặc 504 DEADLINE_EXCEEDED từ phía Gemini |

Không dòng nào là lỗi logic của hệ được đo; tất cả là lỗi mạng hoặc dịch vụ thoáng qua, thử lại là qua.
### 11e. Loại *thiếu lực* và 11 đơn vị bị A06 loại — cả hai ĐĂNG KÝ TRƯỚC, không nghĩ ra sau

Câu hỏi đúng phải hỏi: *thiếu lực* có phải rổ thứ tư nghĩ ra sau khi nhìn số không? **Không.**
A04.5 ghi trước, kèm ngưỡng và kèm **đích danh các ô** sẽ rơi vào đó, trích nguyên văn:

> **Kiểm lực trước số.** Dự đoán *ổn định* với $0/n$ chỉ đạt cận trên Wilson ≤ 10 % khi $n \ge 35$
> ($0/31$ → 11,0 %; $0/30$ → 11,3 %; $0/35$ → 9,9 %). Đơn vị $n < 35$ **không thể** được chấm *đúng*
> cho dự đoán ổn định: S1 (ô 1, 3, 4) và M3 (ô 15) in ra với nhãn **thiếu lực**, **không** vào mẫu
> số; vẫn tính *sai* nếu rơi vào vùng sai (sai vẫn quan sát được). Ô dự đoán *không ổn định* không bị
> ràng buộc này. S2 không dùng cho M7.

Ba đơn vị mang nhãn ấy trong kết quả — ô 1/S1, ô 3/S1, ô 4/S1, tất cả $n = 31 < 35$ — **đúng bằng
danh sách A04.5 nêu trước**. Ô 15/M3 cũng thiếu lực ($n = 30$) nhưng đã bị A06 loại khỏi mẫu số vì
lý do khác (pilot), nên không đếm lần hai. Không có đơn vị nào ngoài danh sách đăng ký rơi vào loại này.

Phần bù cũng phải in: A04 chỉ có **ba** phán quyết (đúng / sai / không phân định). *Thiếu lực* không
phải phán quyết thứ tư — nó là **điều kiện vào mẫu số**, áp trước khi chấm, và đơn vị thiếu lực vẫn
bị tính **sai** nếu rơi vào vùng sai. Ba đơn vị S1 đều $0/31$, tức không có cái nào được cứu bởi nhãn này.

**11 đơn vị A06 loại, mỗi đơn vị một dòng lý do** (`LOAI_A06` trong `desktop/scripts/cham_m6_m7.py`):

| ô | nguồn | lý do loại |
|---|---|---|
| 5 | M2 | cấu hình M2 hosted đã có số pilot dựng mô hình (A06.3) |
| 6 | M2 | cấu hình M2 hosted đã có số pilot dựng mô hình (A06.3) |
| 7 | M2 | cấu hình M2 hosted đã có số pilot dựng mô hình (A06.3) |
| 8 | M2 | cấu hình M2 hosted đã có số pilot dựng mô hình (A06.3) |
| 9 | M2 | suy máy móc từ ô artefact cùng nguồn (A06.1): decision tính từ artefact |
| 9 | M6 | suy máy móc từ ô artefact cùng nguồn (A06.1): decision tính từ artefact |
| 11 | M4 | suy máy móc từ ô artefact cùng nguồn (A06.1): decision tính từ artefact |
| 13 | M4 | suy máy móc từ ô artefact cùng nguồn (A06.1): decision tính từ artefact |
| 15 | M3 | cấu hình M3 đã có số pilot dựng mô hình (A06.3) |
| 16 | M3 | cấu hình M3 đã có số pilot dựng mô hình (A06.3) |
| 17 | M3 | cấu hình M3 đã có số pilot dựng mô hình (A06.3) |

Chứng minh loại **trước** khi có số: A06 commit `a078d37` lúc **2026-09-17T11:33:34+07:00**; bản ghi
M6 sớm nhất là **2026-09-18T10:02:46+07:00**, tức sau đó **22,5 giờ**. Mốc mù A04.5 là commit
`015c0e7` lúc **2026-09-17T07:48:33+07:00**, và script lọc theo `ts` của lượt sau, không lọc tay:
`khong_mu` rỗng và `chua_co_cap_mu` = 0, nghĩa là mọi cặp tính điểm đều có lượt sau nằm sau mốc mù.

### 11f. Ô 12 — decoding ĐÃ ghim đủ mà artefact vẫn đổi 9/50: bác thật, không phải lỗi cấu hình

Trước khi gọi ô 12 là *ma trận sai*, phải loại giả thuyết rẻ tiền: có phải chỉ ghim trọng số mà quên
ghim bộ giải mã? Đọc cấu hình **thật sự gửi tới Ollama** (`plan.json` khoá `params.options`, và
`OllamaExec.manifest` ghi `tham_so_gui`), không suy đoán:

| tham số | giá trị | ghim ở đâu |
|---|---|---|
| `temperature` | `0.0` | `plan.json` → `params.options` |
| `seed` | `0` | `plan.json` → `params.options` |
| `num_predict` | `100` | `plan.json` → `params.options` |
| `num_thread` | `6` | `tham_so_gui` trong manifest, **giống nhau ở mọi bản ghi** |
| `think` | `false` | `tham_so_gui` |
| trọng số | digest `845dbda0ea48…` | giống hệt ở cả hai mốc của cả 9 cặp đổi |

Manifest M4 có ba bộ tham số vì tập còn **probe** cố ý đổi cấu hình — 5 bản ghi `seed 0 / temp 0,0`
(điều kiện chính), 2 bản `seed 1`, 2 bản `temp 0,8`. Các cặp chấm ô 12 chỉ lấy mốc `t0` so `t24h`
của `qwen2.5:7b`, đều thuộc điều kiện chính; probe không lẫn vào.

**Nên đây là bác thật.** Và nó không phải cắt cụt ở `num_predict`: cả hai phía đều `done_reason =
stop`, và nội dung là **viết lại hẳn**, không phải một câu bị cắt ngắn. Ba ví dụ:

| cặp | t0 | t24h |
|---|---|---|
| `078cc5e1…` | *For example, virtual reality can simulate field trips to places like museums…* | *For example, virtual reality can transport students to historical sites…* |
| `697711806949a46d` (3b) | *Enrolling on a gap year course abroad can indeed enhance your profile…* | *Indeed, taking a gap year to study or work abroad can often enhance your credentials…* |
| `9aae4a2d…` (3b) | trả lời bằng tiếng Hàn | trả lời bằng tiếng Anh — đây cũng là 1/50 đổi `lang_label` |

Đối chiếu hai model: `qwen2.5:7b` đổi `reply_text` **9/50** và `lang_label` **1/50**; `qwen2.5:3b`
đổi `reply_text` **4/50** và `lang_label` **1/50**. Quyết định bền hơn artefact ở cả hai, đúng chiều
luận điểm chính — cái sai là dự đoán *ổn định tuyệt đối* cho artefact của model ghim, không phải
thứ tự decision/artefact.

**Ô 12 KHÔNG được chấm lại.** Nó vẫn là dự đoán **sai**; phần trên là giải thích hậu kiểm, ghi riêng,
không nhét ngược vào prereg. Điều phải nói ở Discussion: ma trận coi *caller-pinnable* là thuộc tính
của **trọng số**, trong khi thực tế nó là thuộc tính của **toàn bộ tham số tới được model** — và ngay
cả khi bộ tham số ấy đã ghim đủ, vẫn còn một trục ma trận không có. Bài đã có sẵn bằng chứng cùng
chiều ở ngay §I: pilot ghi *an open-weight model run locally with seed and temperature pinned changed
its text on 16/23 repeats … while the language decision those texts encode changed on 0/23*. Tức
**dự đoán ô 12 mâu thuẫn với chính quan sát mở đầu của bài**, và số đo 9/50 đứng về phía pilot.

### 11g. Rà câu *tích luỹ theo thời gian* trong bản dựng — 0 chỗ phải sửa

M3 phẳng, nên mọi câu nói drift tăng dần theo ngày sẽ sai theo dữ liệu của chính bài. Quét toàn bộ
`Submission TSE/latex/sections`, `supplement/sections` và `abstract.tex` theo các mẫu *accumulate,
grow over, increase with time, degrade, decay, widen, over the days*:

- Mọi chỗ `decay` / `degrade` trong `01-introduction.tex` và `11-results.tex` đều nói về **độ sâu**
  (*reproducibility decays with depth*, *degrade with the depth of the stage*), không nói về thời gian.
- `supplement/04-response-language.tex` *accumulates its own past behaviour as context* — nói về lịch
  sử hội thoại nhiều lượt, không phải trôi theo ngày.
- `supplement/06-routing-determinism.tex` *let small-talk history accumulate* — tham số vận hành.
- `supplement/05-routing-accuracy.tex` *did not degrade* — nói về lực phát hiện ở n = 50 so n = 200.
- `s08-threats-detail.tex` đã viết sẵn đúng chiều: *reported as a curve and **not fitted to a decay model***.

**Không câu nào phải viết lại, không chạm §STOP 5.** Việc còn lại thuộc bước 3: thêm phát biểu
khẳng định điều đã đo — *instability appears at the shortest separation we measured and does not grow
over 6,5 days* — vào Results, rồi §I / abstract / Conclusion trỏ theo.

### 11h. Bảng đối chiếu máy đọc — khoá vòng giữa sổ cái và `numbers.json`

Có **hai** đường cùng đi từ cùng bộ file đo: `build_muc11.py` sinh mục 11 này, và `dem_me_27f()`
trong `build_numbers.py` sinh `paper/numbers.json` rồi thành macro. Hai đường tính độc lập, nên
phải có thứ buộc chúng bằng nhau — nếu không, sổ và bài trôi khỏi nhau mà không cổng nào thấy.
Bảng dưới là bản máy đọc của mục 11; `tests/test_muc11_khop_numbers.py` so từng dòng với
`numbers.json` (chuẩn hoá dấu phẩy thập phân), và `build_numbers.py --check` gọi nó.

| key | giá trị |
|---|---|
| `m3.milestones` | `14` |
| `m3.questions` | `30` |
| `m3.retrieving` | `20` |
| `m3.domain_changed` | `19` |
| `m3.text_changed` | `20` |
| `m3.domain_lo` | `17` |
| `m3.domain_hi` | `21` |
| `m3.text_lo` | `20` |
| `m3.text_hi` | `21` |
| `m6.margin` | `0,750` |
| `m6.margin_lo` | `0,575` |
| `m6.margin_hi` | `0,858` |
| `m6.dec_flaky` | `10` |
| `m6.art_flaky` | `40` |
| `m6.n_tests` | `40` |
| `m6.short_dec` | `0` |
| `m6.short_art` | `31` |
| `m6.tests_per_run` | `252` |
| `m7.correct` | `9` |
| `m7.wrong` | `4` |
| `m7.undecided` | `2` |
| `m7.total` | `15` |
| `m7.excluded` | `11` |
| `m7.underpowered` | `3` |

