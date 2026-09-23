> **CÁC BỘ SỐ Ở ĐÂY LÀ READ-ONLY.** Đã đóng băng: không sửa, không ghi đè, không chạy
> lại bất kỳ file `.jsonl`/`.csv`/`.json` nào. Muốn đo lại thì **tạo bộ mới** (ngày khác,
> hậu tố mới) và để nguyên các bộ cũ làm mốc so sánh — đúng như v2 (2026-09-06) đã làm
> với v1 (2026-09-05).
>
> Bộ hiện hành: **v3 (2026-09-06, `gemini-audio`) — mic giả 90 lượt, mục cuối file.**
> Bộ giọng thật chính thức vẫn là **31 lượt trên v2** (chưa thu lại trên v3).
> v1 và v2 giữ nguyên làm mốc so sánh.
>
> Các bộ trả lời những câu khác nhau, **đừng trộn vào một bảng**:
> **replay v3** (mục cuối) = so sạch nhất — cùng 31 file audio giọng người, cùng đường
> mic, hai pipeline; **bench mic giả v3** = latency ổn định trên 90 lượt;
> **giọng thật v2** = mốc Whisper trên chính 31 file ấy; **v1** = mốc gốc.

> **Ghi chú sửa ground truth (06/09).** `realvoice_2026-09-06_v2_refs.json` lượt #17
> ban đầu gán nhầm câu tiếng Anh; thực tế chủ nhân đọc lại câu tiếng Việt số 5. Phát
> hiện khi kiểm nhiễm test set: hai model độc lập (`gemini-audio`, `large-v3-turbo`)
> cùng chép ra câu 5. Đã sửa refs; mọi bảng WER trong file này dùng bản đã sửa. Chi
> tiết và bài học: `docs/ADR-004` mục "Kiểm nhiễm test set".

# Baseline desktop-only — 2026-09-05

Điều kiện đối chứng (control condition) cho phần desktop: **không robot, không thiết bị
ngoài**, toàn bộ vòng thoại chạy trên một laptop Windows. Mọi số đo về sau (device floor
của ES3C28P, rồi bản chạy trên phần cứng thật) so ngược về đây.

Hai bộ số:

| bộ | mic | ngày giờ thật | n | dùng để |
|---|---|---|---|---|
| **v1** (`latency_desktop_baseline_2026-09-05_v1.jsonl`) | giả lập (câu mẫu → TTS → PCM → VAD) | 2026-09-05 19:22 → 19:42 | 90 (3 bộ × 30) | mốc chính, lặp lại được |
| **realvoice** (`latency_desktop_realvoice_2026-09-05.jsonl`) | micro thật, người nói thật | **2026-09-06 09:49 → 09:57** | 30 (sau warm-up) | kiểm chứng mic giả có lệch mic thật không |
| v0 (`..._v0.jsonl`) | giả lập | 2026-09-05 16:58 → 17:25 | 90 | **KHÔNG DÙNG** — xem §6 |

> **Ghi chú về ngày trong tên file.** Bộ giọng thật thực ra chạy **sáng 2026-09-06**, không
> phải 09-05. Tên file giữ `2026-09-05` để đi cùng một gói baseline với v1 (cùng git hash,
> cùng `.env`, cùng máy). Khi trích dẫn thì ghi đúng dấu thời gian trong trường `ts` của
> từng dòng.

---

## 1. Cấu hình `.env` lúc đo (7 biến quyết định pipeline)

| biến | giá trị | ảnh hưởng |
|---|---|---|
| `STT_BACKEND` | `phowhisper` (chuẩn hoá thành `phowhisper-reread`) | Whisper `base` nhận diện + PhoWhisper đọc lại câu tiếng Việt |
| `STT_MODEL` | `base` | model nhận diện / tiếng Anh |
| `STT_MODEL_VI` | `models/phowhisper-base-ct2` | model đọc lại tiếng Việt |
| `LLM_BACKEND` | `gemini` | LLM chạy ở xa, không tranh CPU |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `TTS_BACKEND` | `vieneu` | VieNeu phát theo dòng; Kokoro chỉ dùng cho câu trả lời tiếng Anh |
| `TTS_VOICE_VI` | `Trúc Ly` | giọng tiếng Việt |

Các biến còn lại ở mặc định: `TTS_VOICE_EN=af_heart`, `DUCK_PROFILE=duck`,
`DUCK_LANGUAGE=auto`, `DUCK_BODY=avatar`, `EXPRESS_MODE=` (rỗng → `tag`),
`AUDIO_INPUT_DEVICE=` và `AUDIO_OUTPUT_DEVICE=` (rỗng → thiết bị mặc định của Windows).
Bản chụp đầy đủ: `baseline_config_2026-09-05_v1.json`.

## 2. Phiên bản model và thư viện

Python 3.11.9 (CPython), venv `desktop/.venv`.

| gói | phiên bản | | gói | phiên bản |
|---|---|---|---|---|
| speech-to-speech | 0.2.12 | | numpy | 2.4.6 |
| faster-whisper | 1.2.1 | | transformers | 5.16.1 |
| ctranslate2 | 4.8.2 | | soundfile | 0.14.0 |
| torch | 2.14.0 | | onnxruntime | 1.29.0 |
| vieneu | 3.4.0 | | sounddevice | 0.5.6 |
| kokoro | 0.9.4 | | python-dotenv | 1.2.3 |
| google-genai | 2.22.0 | | | |

Model: Whisper `base` (CTranslate2), PhoWhisper-base đã chuyển sang CT2
(`models/phowhisper-base-ct2`), VieNeu-TTS giọng *Trúc Ly*, Kokoro giọng `af_heart` /
`bm_fable`, Silero VAD (đi kèm `speech-to-speech`).

## 3. Máy

| | |
|---|---|
| CPU | 11th Gen Intel Core i7-1185G7 @ 3.00 GHz — 4 nhân / 8 luồng, base 2995 MHz |
| RAM | 31,71 GB |
| OS | Microsoft Windows 11 Pro 10.0.26200 (build 26200) |
| Nguồn | cắm điện (pin đầy, không sạc), power scheme **Balanced**, Max Processor State 100 % ở cả AC lẫn DC |
| GPU | không có GPU NVIDIA — mọi model chạy CPU |

## 4. Git

Commit lúc đo: **`944a4d50c035799c433ccea3bd65eba6691398df`** (nhánh `master`).

Working tree lúc đó có sửa đổi chưa commit — quan trọng nhất là
`desktop/scripts/bench_latency.py` (harness đo, xem §6). Pipeline và model **không đổi**.

---

## 5. Kết quả

Quy ước: mọi mốc tính từ **lúc VAD báo dứt lời** (`t_vad_end ≡ 0`). "Tầng riêng" là hiệu
hai mốc liền kề: `stt = t_stt`, `llm = t_llm_first − t_stt`, `tts = t_tts_first − t_llm_first`,
`out = t_audio_out − t_tts_first`. p95 lấy theo nearest-rank, cùng công thức với
`desktop/scripts/bench_latency.py` để số ở đây so thẳng được với báo cáo của script.

### 5.1 v1 — mic giả, 3 bộ × 30 lượt

| bộ | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out p50/p95 | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| vi | 30 | 2553 / 5268 | 1129 / 2166 | 532 / 1609 | 2 / 19 | **4540 / 10951** |
| en | 30 | 1515 / 2524 | 1069 / 2098 | 2677 / 4954 | 2 / 3 | **5578 / 8009** |
| mix | 30 | 2075 / 3337 | 1094 / 1992 | 514 / 4564 | 1 / 3 | **4832 / 7210** |
| **cả 90** | 90 | 2092 / 4805 | 1094 / 2098 | 1229 / 4746 | 2 / 4 | **5095 / 7672** |

(ms. 0 lượt lỗi, 0 lượt thiếu mốc. Đúng ngôn ngữ 90/90.)

Ba lượt đuôi kéo p95 lên, ghi ra đây để không ai tưởng đó là hành vi thường:

| bộ | lượt | e2e | chỗ nghẽn |
|---|---|---|---|
| vi | 2 | 23 082 ms | tầng `tts` **19 258 ms** — VieNeu kẹt một lần duy nhất trong cả 90 lượt |
| vi | 7 | 10 951 ms | tầng `stt` 8 288 ms |
| en | 16 | 12 032 ms | `stt` 6 620 ms + `tts` 4 253 ms |

Độ dài câu vào: `audio_s` p50 2,21 s (vi 2,78 / en 2,21 / mix 2,11).

### 5.2 realvoice — micro thật, 30 lượt sau warm-up

| nhóm | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out p50/p95 | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| tất cả | 30 | 1914 / 4345 | 1200 / 2326 | 444 / 2746 | 2 / 3 | **4301 / 7929** |
| `stt_lang=vi` | 12 | 2624 / 3484 | 1328 / 2264 | 418 / 502 | 2 / 3 | **4570 / 5431** |
| `stt_lang=en` | 18 | 1576 / 3361 | 1143 / 2326 | 474 / 2746 | 2 / 3 | **3684 / 6114** |

(ms. `audio_s` p50 1,92 s. Min e2e 2796 ms, max 8248 ms — **không lượt nào vượt 10 s**,
khác hẳn đuôi của v1.)

**Đúng ngôn ngữ: 14/30.** 16 lượt có `wrong_language=true`. Cả 16 đều cùng một dạng:
**`stt_lang=en` → `reply_lang=vi`** — Whisper nghe ra tiếng Anh, rồi vịt trả lời bằng
tiếng Việt. Trong 18 lượt được nhận là tiếng Anh, chỉ 2 lượt được đáp bằng tiếng Anh.

> **Sửa lại 06/09/2026.** Bản đầu của đoạn này viết "tất cả đều là người nói tiếng Việt,
> STT nghe nhầm ra tiếng Anh". **Sai.** Chấm lại bằng `spoken_lang` (ngôn ngữ người nói,
> suy từ transcript + bộ câu mẫu của `realvoice.py`) thì 16 lượt ấy tách làm hai:
>
> - **3 lỗi STT** (#5, #6, #28) — tiếng Việt rất ngắn bị nghe thành `en`. Ba lượt này vịt
>   **đáp đúng tiếng Việt**, tức thước cũ quy oan cho LLM.
> - **13 lỗi LLM** (#13, #16–#27) — **tiếng Anh thật** (người nói đang đọc chính bộ câu
>   tiếng Anh, mỗi câu ba lần), bị chép méo (`"BSD paper"`, `"dengan kebukaan"`, `"a Zuck
>   about SAP"`) rồi bị đáp bằng tiếng Việt.
>
> Theo ngôn ngữ người nói: STT sai **3/15** câu tiếng Việt và **0/15** câu tiếng Anh; LLM
> sai **0/15** câu tiếng Việt và **13/15** câu tiếng Anh. Tức lỗi chính nằm ở **LLM cãi
> lệnh ngôn ngữ**, không phải ở STT chọn sai — nguyên nhân và cách sửa ở `docs/ADR-008`;
> hệ quả cho quyết định STT ở `docs/ADR-004` (mục ĐÓNG). Không dòng `.jsonl` nào bị sửa —
> chỉ sửa câu diễn giải này.

Đây là **số về chất lượng nhận dạng và về việc tuân lệnh ngôn ngữ, không phải về latency**;
nó không làm hỏng bộ latency nhưng nó *có* làm lệch tầng `tts` — xem §5.3. Bộ v1 mic giả
sạch 90/90 vì câu vào do chính TTS của hệ thống sinh ra.

### 5.3 realvoice − v1: tách "chi phí driver audio + VAD thật"

Ghép cặp **theo ngôn ngữ STT nhận ra**, vì tầng `stt` phụ thuộc ngôn ngữ rất mạnh
(PhoWhisper đọc lại câu tiếng Việt → vi luôn đắt hơn en ~1 s):

| tầng | VI: bench → realvoice | Δ | EN: bench → realvoice | Δ |
|---|---|---|---|---|
| **stt** | 2553 → 2624 | **+71** | 1515 → 1576 | **+61** |
| llm | 1129 → 1328 | +200 | 1069 → 1143 | +74 |
| tts | 532 → 418 | −114 | 2677 → 474 | **−2203** ⚠ |
| out | 2 → 2 | +0 | 2 → 2 | +0 |

**Kết quả: chi phí driver audio + VAD thật ở tầng `stt` ≈ +60…+70 ms p50**, và con số này
nhất quán ở cả hai ngôn ngữ (+71 vi, +61 en) — đó là lý do tin được. So với e2e p50 ~4,3 s
thì nó là **1,5 %**: mic giả trong `bench_latency.py` đo thay được cho mic thật.

`llm` và `out` xấp xỉ nhau như kỳ vọng (+74…+200 ms ở `llm` là nhiễu mạng của Gemini; `out`
đúng bằng nhau vì cả hai đều đánh mốc lúc chunk đầu rời hàng đợi).

**⚠ Tầng `tts` KHÔNG xấp xỉ — báo theo yêu cầu, và đây là hiện vật của phép so, không phải
hiện tượng thật.** Cột EN lệch −2203 ms vì hai nhóm dùng **hai backend TTS khác nhau**: bộ
`en` của v1 trả lời tiếng Anh → Kokoro (không stream, p50 2863 ms), còn 18 lượt
`stt_lang=en` của realvoice thì **16 lượt bị vịt đáp bằng tiếng Việt** (xem §5.2) nên đi
VieNeu (stream, p50 439 ms). So cùng backend thì hết lệch:

| backend | v1 (n) | realvoice (n) | Δ p50 |
|---|---|---|---|
| VieNeu | 493 ms (48) | 439 ms (28) | −54 ms |
| Kokoro | 2863 ms (42) | 4004 ms (2) | +1141 ms — **n=2, không kết luận được** |

Chỉ 2/30 lượt giọng thật đi qua Kokoro, nên bộ realvoice **không** kiểm chứng được nhánh
tiếng Anh. Muốn có số đó thì phải chạy lại với người nói tiếng Anh rõ hơn (hoặc khoá
`DUCK_LANGUAGE=en`).

**Giới hạn của phép đo này — đọc trước khi trích dẫn.** Đồng hồ bắt đầu ở `t_vad_end`
(`start_turn(vad_audio.created_at_s)`), tức là **lúc VAD đã cắt xong câu**, ở *cả hai* bộ;
và `t_audio_out` đánh dấu lúc chunk đầu rời hàng đợi ra loa, không phải lúc tai nghe được.
Nghĩa là độ trễ thu của driver vào, thời gian VAD chờ đuôi im lặng, và độ trễ đệm của
driver ra đều **nằm ngoài** cửa sổ đo ở cả hai bộ. Con số +60…+70 ms ở trên chỉ là phần còn
lại: âm thanh mic thật (ồn hơn, độ dài khác) đi qua đúng cùng một Whisper. **Chi phí driver
audio đầy đủ vẫn chưa đo được** — đó là việc của bước "protocol đo" tiếp theo, phải đóng
vòng bằng loopback vật lý chứ không bằng mốc phần mềm.

Một chú ý nữa khi so hai bộ: **thời lượng câu gần như không ảnh hưởng tới `t_stt`**. Hồi quy
`t_stt = a + b·audio_s` cho R² ≈ 0,00–0,09 ở mọi nhóm — khớp với kết luận của SESSION-03
rằng Whisper luôn đệm lên 30 giây. Vì vậy **đừng chuẩn hoá bằng RTF** khi so hai bộ này;
`audio_s` p50 có lệch (2,21 s so với 1,92 s) nhưng lệch đó không sinh ra chênh lệch `t_stt`.
Cũng vì vậy phép so gộp cả bộ là sai: gộp lại thì `stt` ra **−197 ms** (realvoice *nhanh
hơn*), thuần tuý vì tỉ lệ vi/en của hai bộ khác nhau (v1 50/50, realvoice 40/60).

---

## 6. Vì sao **không** dùng v0

`latency_desktop_baseline_2026-09-05_v0.jsonl` giữ lại để truy vết, **không được trích dẫn
làm baseline**. Lỗi nằm ở harness đo, không ở pipeline:

1. **Loa giả không được rút hàng đợi liên tục.** `t_audio_out` đánh dấu lúc chunk đầu bị
   *lấy ra* khỏi hàng đợi; nếu không có thread rút đều thì mốc đó phản ánh lịch của harness
   chứ không phải của pipeline. **1 lượt (`en` #26) không bao giờ nhận được `t_audio_out`**
   nên mất luôn `end_to_end_ms` — triệu chứng lộ ra của đúng lỗi này.
2. **Lượt sau bơm vào trước khi lượt trước chốt sổ.** Trong v0 có **19/87 lần** lượt kế tiếp
   bắt đầu chưa đầy 1,0 s sau khi lượt trước kết thúc, chỗ ngắn nhất chỉ **0,03 s** — tức là
   TTS và phát của lượt trước vẫn đang ăn CPU khi lượt sau bắt đầu tính giờ. Trên máy 4 nhân
   15 W thì đó là đúng thứ ADR-005 chứng minh là nút thắt lớn nhất.

Hậu quả đo được: v0 báo `vi` p50 **3565 ms**, v1 báo **4540 ms** cho cùng câu, cùng model,
cùng máy, cách nhau 2 giờ. Chênh gần 1 giây đó là do harness, và v0 lệch về phía *lạc quan*.

v1 sửa cả bốn chỗ: thread riêng rút hàng đợi loa liên tục; `finish()` chờ `t_audio_out`
landing (timeout 60 s → ghi lỗi); chỉ bơm câu kế tiếp sau khi **có sentinel VÀ `finish()` đã
ghi**; nghỉ 1,0 s giữa hai lượt. Kết quả: 90/90 lượt đủ mốc, khoảng nghỉ thực tế min 1,05 s.

---

## 7. Hai chú thích phải đọc kèm mọi con số ở đây

### 7.1 Kokoro không stream

VieNeu phát **theo dòng ở mức frame** — chunk đầu ra khi câu chưa tổng hợp xong. Kokoro phải
**tổng hợp trọn câu rồi mới có mẫu đầu**. Vì thế tầng `tts` của hai backend không so trực
tiếp được:

* VieNeu `tts` p50 **493 ms** (n=48, v1) — gần như hằng số, p95 1539 ms.
* Kokoro `tts` p50 **2863 ms** (n=42, v1), p95 4888 ms — và nó **tăng theo độ dài câu trả
  lời**, vì đó là thời gian tổng hợp cả câu.

Hệ quả: bộ `en` của v1 có e2e p50 cao nhất (5578 ms) **không phải** vì tiếng Anh chậm — tầng
`stt` của nó nhanh nhất bảng (1515 ms) — mà vì Kokoro. Bất kỳ so sánh vi/en nào bỏ qua chỗ
này đều sai. Tối ưu streaming cho Kokoro là việc có thật, nhưng **xếp sau** khi đã có số
device floor (xem `PLAN.md`).

### 7.2 WMI báo sai xung nhịp CPU

Trong lúc đo v1 có một job đọc `Win32_Processor.CurrentClockSpeed` mỗi giây; nó báo **1198
MHz** đều đặn qua 247 mẫu, và tổng kết v1 bản đầu đã kết luận nhầm là "CPU bị ghim ở 40 %
xung nhịp". **Kết luận đó SAI và đã bị bác bỏ.** Đo lại dưới tải bằng
`\Processor Information(_Total)\% Processor Performance`: xung thật **3218–3902 MHz**, trên
cả base 2995 MHz — turbo chạy bình thường, Max Processor State 100 % ở cả AC lẫn DC.

Nghĩa là **baseline v1 hợp lệ, đo lúc CPU chạy hết tốc độ**. Bằng chứng đầy đủ:
`cpu_verify_2026-09-05.md` + hai CSV đi kèm. File
`cpu_clock_2026-09-05_v1_WMI-KHONG-TIN-CAY.csv` giữ nguyên tên cảnh báo — đừng dùng nó để
kết luận gì về xung nhịp.

Bài học đã ghi vào `PLAN.md` §5: một lần đọc bộ đếm lúc nhàn rỗi không nói được gì về lúc
chạy tải.

---

## 8. Danh mục file

| file | nội dung |
|---|---|
| `latency_desktop_baseline_2026-09-05_v1.jsonl` | 90 lượt mic giả — **bộ mốc chính** |
| `latency_desktop_realvoice_2026-09-05.jsonl` | 30 lượt giọng thật (`source="ui"`), tách từ `desktop/logs/latency.jsonl` |
| `baseline_config_2026-09-05_v1.json` | bản chụp .env / package / máy / git / harness của v1 |
| `latency_desktop_baseline_2026-09-05_v0.jsonl` | bộ hỏng, giữ để truy vết — **không dùng** (§6) |
| `baseline_config_2026-09-05_v0.json` | bản chụp của bộ v0 |
| `cpu_verify_2026-09-05.md` | báo cáo kiểm chứng xung nhịp (§7.2) |
| `cpu_verify_perfcounter_2026-09-05.csv` | 60 mẫu perf counter — nguồn đáng tin |
| `cpu_verify_wmi_2026-09-05.csv` | 29 mẫu WMI cùng lúc, để đối chiếu |
| `cpu_clock_2026-09-05_v1_WMI-KHONG-TIN-CAY.csv` | 247 mẫu WMI lúc chạy v1 — **không tin cậy** |

Cách đọc lại số: `python desktop/scripts/bench_latency.py` (không có `--run`) tổng kết
`desktop/logs/latency.jsonl`; các file ở đây cùng schema nên chép sang đường dẫn đó là tổng
kết được, **nhưng đừng ghi đè file gốc trong thư mục này**.

---

# Baseline v2 — 2026-09-06

**Bộ v1 ở trên không bị đụng tới.** v2 là bộ mới, đo sau ba thay đổi, để so theo tầng.
File: `latency_desktop_baseline_2026-09-06_v2.jsonl` + `baseline_config_2026-09-06_v2.json`.
Cùng máy, cùng model, cùng harness, cùng quy trình (warm-up mix 2 lượt không tính,
rồi vi/en/mix × 30, ký ức bench xoá trước mỗi bộ, console tắt).

## Ba thay đổi giữa v1 và v2

| # | thay đổi | ở đâu |
|---|---|---|
| 1 | **`DUCK_LANGUAGE=auto` → `vi+en`** — Whisper chỉ chọn giữa hai thứ tiếng vịt nói được | `.env` (**thay đổi `.env` duy nhất**) |
| 2 | **`temperature=0`** cho faster-whisper, giữ ba ngưỡng; thêm `stt_logprob` / `stt_low_conf` | `docs/ADR-007` |
| 3 | **Nhãn ngôn ngữ gắn vào lượt người dùng** thay vì chỉ ở system prompt | `docs/ADR-008` |

Kèm theo (không đổi hành vi đo): thước đo ngôn ngữ tách `stt_lang_wrong` khỏi
`wrong_language` theo `spoken_lang`, và pipeline lưu WAV mọi lượt vào `logs/utts/`
(bench tắt). Model **không đổi**.

## Bảng theo tầng

Đơn vị ms. Quy ước mốc và cách tính p95 giống hệt phần v1 ở trên.

| bộ | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| **v1** vi | 30 | 2553 / 5268 | 1129 / 2166 | 532 / 1609 | 2 | **4540 / 10951** |
| **v2** vi | 30 | 2479 / **2967** | 1092 / 2308 | 390 / **541** | 1 | **4074 / 5249** |
| **v1** en | 30 | 1515 / 2524 | 1069 / 2098 | 2677 / 4954 | 2 | **5578 / 8009** |
| **v2** en | 30 | **1171 / 1374** | 1043 / 2306 | 2366 / 3851 | 2 | **4566 / 7385** |
| **v1** mix | 30 | 2075 / 3337 | 1094 / 1992 | 514 / 4564 | 1 | **4832 / 7210** |
| **v2** mix | 30 | 1753 / 3670 | 1026 / 2173 | 395 / 2904 | 1 | **4120 / 6843** |
| **v1** cả 90 | 90 | 2092 / 4805 | 1094 / 2098 | 1229 / 4746 | 2 | **5095 / 7672** |
| **v2** cả 90 | 90 | **1761 / 2941** | 1070 / 2283 | 528 / 3597 | 2 | **4324 / 6890** |

Chênh lệch v2 − v1 (p50 / p95):

| bộ | stt | llm | tts | **e2e** |
|---|---|---|---|---|
| vi | −74 / **−2301** | −37 / +143 | −142 / −1068 | **−467 / −5703** |
| en | −344 / −1150 | −26 / +208 | −310 / −1103 | **−1013 / −624** |
| mix | −322 / +333 | −68 / +181 | −119 / −1660 | **−712 / −367** |
| **cả 90** | **−331 / −1864** | −24 / +185 | −701 / −1148 | **−771 / −782** |

Đọc bảng:

- **Chỗ được nhiều nhất là ĐUÔI, và đúng ở tầng `stt`.** p95 của `stt` giảm
  4805 → 2941 ms cho cả 90 lượt, riêng bộ `vi` giảm 5268 → 2967. Đây là ADR-007:
  mỗi lần temperature fallback là một lần chép LẠI toàn bộ đoạn audio, nên nó dồn
  hết vào đuôi. Bỏ fallback thì đuôi xẹp.
- **e2e p95 của bộ `vi` giảm 5,7 giây** (10951 → 5249). Phần lớn là do lượt
  23 082 ms của v1 biến mất — lượt đó VieNeu kẹt 19 s một lần duy nhất trong 90
  lượt, nên đây là "v1 xui" nhiều hơn là "v2 giỏi". Đừng quảng cáo con số này.
- **`llm` p95 xấu đi một chút ở cả ba bộ** (+143…+208 ms). Nhãn ngôn ngữ thêm
  ~10 token vào lượt người dùng, nhưng phần lớn là nhiễu mạng Gemini: p50 của
  `llm` thì lại tốt lên (−24…−68 ms). Không có tín hiệu nào nói ADR-008 tốn kém.
- **`stt` p50 của bộ `en` giảm 344 ms** (1515 → 1171). Đây là chỗ `vi+en` có thể
  đang giúp, nhưng **không tách được** khỏi ảnh hưởng của `temperature=0` bằng bộ
  số này — hai thay đổi đi cùng một lúc. Đo tách thì phải chạy thêm hai bộ nữa.
- **`mix` là bộ duy nhất có p95 `stt` xấu đi** (+333 ms). n=30, một lượt đuôi là
  đủ; không đủ bằng chứng để gọi là hồi quy.

## Ngôn ngữ — thước đo mới

v2 có `spoken_lang` nên tách được lỗi STT khỏi lỗi LLM (xem `docs/ADR-008`):

| bộ | lỗi STT | lỗi LLM | transcript đáng ngờ |
|---|---|---|---|
| vi | 0/30 | 0/30 | 0 |
| en | 0/30 | 0/30 | 0 |
| mix | 0/30 | 0/30 | 0 |
| **cả 90** | **0/90** | **0/90** | **0** |

0 lượt lỗi harness, 0 lượt thiếu mốc, 0 outlier.

Nhớ rằng đây là **mic giả**: câu vào do chính TTS của hệ thống đọc ra nên phát âm
chuẩn, không ồn phòng. Bài khó là giọng thật — v1 giọng thật có 3/30 lỗi STT và
13/30 lỗi LLM. Con số 0/90 ở đây nói "cấu hình mới không thụt lùi", **không** nói
"đã hết lỗi ngôn ngữ".

## Một lỗi bắt được trong lúc chạy v2, và đã sửa

Lần chạy đầu, bộ `en` báo **6/30 lỗi LLM**. Soi ra thì lời thoại là tiếng Anh thật:

    "Hello! My name is Vịt. You can call me Duck in English too!"

nhưng `reply_lang` bị chốt `vi`, và `reply_lang` chọn engine TTS — nên câu tiếng
Anh bị **VieNeu đọc bằng giọng tiếng Việt**. Nguyên nhân: `_language_for()` chốt
ngôn ngữ từ **mảnh ĐẦU TIÊN** của câu trả lời (TTS cần biết engine ngay để phát
sớm), mà mảnh đầu `"Hello! My name is Vịt."` cho lingua **vi 0,503 / en 0,497** —
đúng một cú tung đồng xu. Cả câu thì lingua chốt en 0,940.

Dây chuyền dẫn tới đây: bỏ "Quack" mở đầu (phiên trước) làm model đổi cách viết tên
— v1 đáp *"Quack, my name is Vit!"* (không dấu → `en`), v2 đáp *"My name is Vịt."*
(có dấu → lật). Một tên riêng có dấu đủ lật cả câu.

Sửa: bộ nhận diện chỉ được **lật** ngôn ngữ đã ra lệnh cho lượt khi nó chắc
(`OVERRIDE_CONFIDENCE = 0,75`). Ngưỡng chọn từ số đo — mảnh mơ hồ 0,503; câu tiếng
Anh thật 0,88–0,995; câu tiếng Việt thật 1,000 — nên 0,75 tách sạch. Không có ngôn
ngữ đã ra lệnh thì vẫn theo chữ như cũ.

**Bộ `en` trong file v2 là lần chạy LẠI sau khi sửa** (13:32). `vi` và `mix` giữ
nguyên lần chạy đầu: cả hai vốn đã 0/30 lỗi, và nhánh "lật ngôn ngữ đã ra lệnh"
chưa từng kích hoạt ở chúng. Số `tts` p50 của bộ `en` vì thế cũng đúng trở lại
(2366 ms = Kokoro) thay vì 1614 ms của lần chạy nhiễm lỗi, khi 6 lượt đi nhầm
sang VieNeu.

## Danh mục file thêm

| file | nội dung |
|---|---|
| `latency_desktop_baseline_2026-09-06_v2.jsonl` | 90 lượt v2 (bộ `en` là bản chạy lại 13:32) |
| `baseline_config_2026-09-06_v2.json` | bản chụp .env / package / máy / git / thay đổi so với v1 |
| `latency_desktop_realvoice_2026-09-06_v2.jsonl` | **31 lượt giọng thật trên v2** — bộ giọng thật chính thức |
| `realvoice_2026-09-06_v2_refs.json` | câu mẫu của từng file WAV (đọc theo khối, câu 6 bốn lần) |

## Giọng thật trên v2 — 2026-09-06 14:43 → 14:51

`latency_desktop_realvoice_2026-09-06_v2.jsonl` (31 lượt) +
`realvoice_2026-09-06_v2_refs.json` (câu mẫu của từng file WAV).
**Đây là bộ giọng thật chính thức**; bộ 05/09 giữ lại làm mốc so sánh.

Lần đầu có audio: `logs/utts/20260906_134002_001..031.wav`. Chủ nhân đọc **theo khối**
— mỗi câu ba lần liên tiếp, riêng câu 6 bốn lần → **31 lượt, không phải 30**. Vì thế
`--prompts --repeat 3` (ghép theo vòng S1…S10 lặp 3) **không dùng được** cho phiên này;
ground truth ghép tường minh bằng `--refs`, file kèm trong thư mục này.

### Ngôn ngữ — chấm theo `spoken_lang`

| nhóm | n | lỗi STT | lỗi LLM | transcript đáng ngờ |
|---|---|---|---|---|
| tất cả | 31 | **6/31** | 6/31 | 6 |
| nói tiếng Việt | 18 | **6/18** | 6/18 | 2 |
| **nói tiếng Anh** | 13 | **0/13** | **0/13** | 4 |

**Sáu lượt "lỗi LLM" là cùng sáu lượt "lỗi STT"** — chủ nhân nói tiếng Việt, Whisper
chốt `en`, vịt đáp tiếng Anh đúng theo thứ nó được bảo. **Không có lỗi LLM độc lập nào.**
Vẫn đếm chúng vào cột LLM vì người dùng nghe thấy sai thật, nhưng nguyên nhân là STT.

Đối chiếu với giọng thật trên v1 (05/09): **13/15 câu tiếng Anh bị đáp bằng tiếng Việt**.
Nay **0/13**. Đó là ADR-008, đo trên giọng thật chứ không phải mic giả.

Sáu lượt STT hỏng đều là câu tiếng Việt **ngắn hoặc khó**, và Whisper chép chúng ra
những thứ tiếng vịt không hề nói:

| # | câu mẫu | Whisper chép | nghe ra | p |
|---|---|---|---|---|
| 3 | Anh tên là Đạt, làm ở Suntory PepsiCo. | `ante la letra más entre el méxico` (tiếng Tây Ban Nha) | en | 0,08 |
| 11 | Ngắn thôi. | `Yeah, hold.` | en | 0,24 |
| 15 | Quên chuyện họp thứ Sáu đi. | `One to half this hour` | en | 0,69 |
| 29 | Dừng. | `Январд` (chữ Kirin) | en | 0,03 |
| 30 | Dừng. | `ยัง` (chữ Thái) | en | 0,11 |
| 31 | Dừng. | `dân` | en | 0,14 |

**`DUCK_LANGUAGE=vi+en` không chặn được chuyện này.** Chế độ ấy chỉ giới hạn *nhãn*
ngôn ngữ (chọn giữa vi và en trong `_best_of_two`); phần **giải mã** vẫn chạy với
`language=None` nên Whisper tự do chép ra tiếng Tây Ban Nha, Kirin, Thái. Nhãn thì
đúng là vi hoặc en — chỉ có điều chọn nhầm cái en.

Năm trong sáu lượt có `stt_lang_p ≤ 0,24`, và 6/31 lượt bị `stt_low_conf`. Tín hiệu
để chặn thì **có**; chưa ai dùng nó.

### Latency theo tầng

| bộ | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| giọng thật **v1** (05/09) | 30 | 1914 / 4345 | 1200 / 2326 | 444 / 2746 | 2 | **4301 / 7929** |
| **giọng thật v2** | 31 | **1354 / 2050** | 1051 / 2186 | 2503 / 4650 | 2 | **4824 / 7185** |
| v2 · nói vi | 18 | 1881 / 2115 | 1056 / 2189 | 296 / 4636 | 2 | 4339 / 7185 |
| v2 · nói en | 13 | 1258 / 1354 | 1041 / 1261 | 4205 / 4650 | 2 | 6384 / 7099 |
| bench v2 (mic giả) | 90 | 1761 / 2941 | 1070 / 2283 | 528 / 3597 | 2 | 4324 / 6890 |

Chênh lệch (p50 / p95):

| | stt | llm | tts | **e2e** |
|---|---|---|---|---|
| giọng thật: v2 − v1 | **−561 / −2295** | −149 / −140 | **+2060 / +1904** | **+524 / −744** |
| v2: giọng thật − bench | −408 / −891 | −19 / −96 | +1975 / +1053 | +500 / +296 |
| — riêng vi | −599 / −851 | −36 / −119 | −94 / +4095 | +265 / +1937 |
| — riêng en | +87 / −20 | −3 / −1045 | +1839 / +800 | +1819 / −286 |

Ba điều đọc ra:

- **Tầng `stt` tốt lên rõ: p50 −561 ms, p95 −2295 ms.** Đây là ADR-007 (`temperature=0`)
  hiện ra trên giọng thật, không chỉ trên mic giả.
- **Tầng `tts` xấu đi +2060 ms, và đó là CÁI GIÁ CỦA VIỆC SỬA ĐÚNG.** Ở v1, 13/15 câu
  tiếng Anh bị đáp bằng tiếng Việt nên đi VieNeu (phát theo dòng, ~440 ms). Nay chúng
  được đáp đúng bằng tiếng Anh nên đi **Kokoro, thứ không stream** — tầng `tts` của
  riêng nhóm nói tiếng Anh là **4205 ms p50**, kéo e2e của nhóm ấy lên **6384 ms**.
  Nói cách khác: **e2e p50 xấu đi 524 ms vì vịt bắt đầu trả lời đúng ngôn ngữ.** Đây là
  lý do bằng số để làm Kokoro streaming, việc đã xếp hàng trong `PLAN.md`.
- **Mic giả vẫn đo thay được cho mic thật ở tầng `stt`** (en: +87 ms p50), đúng như kết
  luận của v1. Chỗ lệch lớn là `tts`, và lệch vì thành phần ngôn ngữ của hai bộ khác
  nhau chứ không phải vì engine chậm đi.

`audio_s` p50 1,89 s (min 0,70 — max 4,03).

### Chấm lại cùng 31 file WAV bằng ba backend

`python scripts/rescore_utts.py logs/utts --refs docs/baseline/realvoice_2026-09-06_v2_refs.json`

| điều kiện | đúng ngôn ngữ | WER | CER | WER vi | WER en | t_stt p50/p95 |
|---|---|---|---|---|---|---|
| `base` | 71 % | 0,798 | 0,571 | 0,806 | 0,787 | 1529 / 3183 |
| **`phowhisper-reread`** *(mặc định)* | **71 %** | **0,711** | 0,530 | 0,645 | 0,787 | 1712 / 2521 |
| `phowhisper` + `vi+en` | 71 % | 0,711 | 0,530 | 0,645 | 0,787 | 1723 / 2208 |
| **`gemini-audio`** | **97 %** | **0,387** | **0,261** | 0,344 | 0,438 | 2560 / 2956 |

**Đây là số quyết định mà ADR-004 chờ từ 04/09, và nó lật ngược kết luận.** Trên giọng
tổng hợp `phowhisper-reread` đạt WER 0,200; trên giọng thật là **0,711** — gấp 3,5 lần.
WER 0,711 nghĩa là bảy trong mười từ sai: vịt đang đoán từ rác. `gemini-audio` giảm còn
0,387 và đúng ngôn ngữ 97 % so với 71 %.

`vi+en` **không cải thiện gì** so với `auto` trên bộ này (trùng khít từng số) — nó chỉ
đổi cách chọn nhãn, mà chỗ hỏng nằm ở phần giải mã.

Lưu ý khi so với số của phiên chạy thật: pipeline lúc chạy chỉ sai **6/31** nhãn ngôn
ngữ, còn chấm lại rời rạc thì `phowhisper-reread` sai **9/31**. Khác nhau vì
`_clean_language()` có nước cuối "theo lượt trước", mà chấm lại thì mỗi điều kiện được
reset `last_language`. Tức bộ nhớ ngữ cảnh đang cứu được 3 lượt.

**Hệ quả: `docs/ADR-004` mở lại** — cả hai điều kiện mở lại ghi trong đó đều thoả
(`stt_lang_wrong` 19 % > 10 %; WER 0,711 > 0,35).

---

# Baseline v3 — 2026-09-06 (BẢN CHÍNH THỨC)

`latency_desktop_baseline_2026-09-06_v3.jsonl` + `baseline_config_2026-09-06_v3.json`.
Mic giả, warm-up mix 2 lượt không tính, rồi vi/en/mix × 30. Cùng máy, cùng harness,
cùng quy trình như v1/v2. Bộ v1 và v2 giữ nguyên làm mốc.

## Đổi gì so với v2

| # | thay đổi | ở đâu |
|---|---|---|
| 1 | **`STT_BACKEND=phowhisper` → `gemini-audio`** | `.env` (thay đổi `.env` duy nhất) |
| 2 | **Cổng tin cậy**: `stt_lang_p ≤ 0,3` hoặc `low_confidence` → hỏi lại, không gửi LLM | `docs/ADR-009` |
| 3 | **Fallback 4 s**: lỗi/quá hạn → Whisper cho đúng lượt đó, ghi `stt_fallback` | `docs/ADR-009` |
| 4 | WER chuẩn hoá số↔chữ và tên riêng (chỉ ảnh hưởng cách CHẤM, không ảnh hưởng pipeline) | `scoring.normalize()` |

## Bảng theo tầng

| bộ | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| **v2** vi | 30 | 2479 / 2967 | 1092 / 2308 | 390 / 541 | 1 | **4074 / 5249** |
| **v3** vi | 30 | 2726 / 3048 | 1047 / 2090 | 260 / 376 | 1 | **4137 / 5008** |
| **v2** en | 30 | 1171 / 1374 | 1043 / 2306 | 2366 / 3851 | 2 | **4566 / 7385** |
| **v3** en | 30 | 2823 / 5058 | 975 / 2283 | 2094 / 3309 | 2 | **6231 / 8258** |
| **v2** mix | 30 | 1753 / 3670 | 1026 / 2173 | 395 / 2904 | 1 | **4120 / 6843** |
| **v3** mix | 30 | 2874 / 3655 | 1043 / 2214 | 278 / 2431 | 1 | **5176 / 6923** |
| **v2** cả 90 | 90 | 1761 / 2941 | 1070 / 2283 | 528 / 3597 | 2 | **4324 / 6890** |
| **v3** cả 90 | 90 | **2805 / 3655** | 1039 / 2207 | 337 / 2808 | 1 | **5129 / 7649** |

Chênh lệch v3 − v2 (p50 / p95):

| bộ | stt | llm | tts | **e2e** |
|---|---|---|---|---|
| vi | **+247 / +82** | −45 / −218 | −131 / −166 | **+63 / −241** |
| en | **+1652 / +3684** | −68 / −23 | −273 / −542 | **+1665 / +873** |
| mix | +1121 / −15 | +17 / +40 | −117 / −472 | **+1056 / +80** |
| **cả 90** | **+1044 / +714** | −31 / −76 | −191 / −789 | **+805 / +760** |

Đọc bảng:

- **Giá phải trả đúng như dự đoán: `stt` p50 +1044 ms.** Ước tính trước khi chạy là
  ~+850 ms (từ chênh lệch p50 trên 31 WAV: gemini 2 624 so với phowhisper 2 011 ms);
  thực tế cao hơn một chút vì trên pipeline còn thêm phần gói WAV và đường mạng.
- **Nhánh tiếng Việt gần như không đổi (`stt` +247 ms), nhánh tiếng Anh chịu hết
  (+1652 ms).** Đúng như ADR-004 đã cảnh báo: `gemini-audio` phẳng theo ngôn ngữ
  (~2,8 s cho cả hai), nên nó lấy đi đúng chỗ Whisper đang nhanh — tiếng Anh trước đây
  chỉ tốn 1 171 ms vì không phải đọc lại bằng PhoWhisper.
- **`stt` p95 của bộ `en` vọt +3684 ms** (1 374 → 5 058). Đây **không** phải Gemini
  chậm: đó là 2 lượt rơi vào **fallback** — hết hạn 4 s rồi chạy Whisper thêm ~1,1 s.
  Nhìn `t_stt` của ba lượt fallback đều nằm quanh 5 100 ms, rất khớp.
- **`e2e` p50 bộ `vi` chỉ +63 ms.** Tầng `stt` đắt thêm 247 ms nhưng `tts` rẻ đi
  131 ms, gần như bù trừ. Tiếng Việt gần như miễn phí khi đổi backend.
- **`llm` và `tts` tốt lên nhẹ ở hầu hết ô.** Không có thay đổi nào nhắm vào hai tầng
  đó; đây là nhiễu, và một phần vì transcript sạch hơn nên câu trả lời ngắn hơn.

## Cổng, fallback, ngôn ngữ

| | vi | en | mix | cả 90 |
|---|---|---|---|---|
| lỗi STT (`stt_lang_wrong`) | 0/30 | 0/30 | 0/30 | **0/90** |
| lỗi LLM (`wrong_language`) | 0/30 | 0/30 | 0/30 | **0/90** |
| transcript đáng ngờ | 0 | 0 | 0 | 0 |
| **`stt_fallback`** | 0 | 2 | 1 | **3/90 = 3,3 %** |
| `asked_again` (cổng chặn) | 0 | 0 | 0 | **0/90** |

0 lượt lỗi harness, 0 lượt thiếu mốc.

**Tỉ lệ fallback 3,3 %** — thấp hơn mức ~5 % ước tính từ p95 của `gemini-audio`
(4 211 ms so với hạn 4 000 ms). Giá của một lần fallback đo được:
`t_stt` p50 **5 120 ms** so với **2 801 ms** khi Gemini chạy được, tức **+2 319 ms**.
Ngưỡng xét lại đặt ở ADR-004 là 10 %; 3,3 % nằm dưới, nên **giữ hạn 4 s**.

**Cổng không kích hoạt lần nào (0/90).** Đúng như thiết kế: mic giả phát âm chuẩn nên
không có lượt nào rỗng hay quá ngắn. Số có ý nghĩa của cổng nằm ở giọng thật —
xem mục "Giọng thật trên v2" ở trên (chặn 11/31 trên transcript Whisper) và
`docs/ADR-009` (chặn 1/31 trên transcript Gemini, bắt bằng tín hiệu "quá ngắn").

## Cái bảng này KHÔNG nói

**Đừng đọc v3 như bằng chứng đổi backend là đúng.** Bảng này đo trên **mic giả** —
giọng do chính TTS của hệ thống đọc ra, phát âm chuẩn, không ồn phòng. Ở điều kiện ấy
Whisper vốn đã tốt (v2 sạch 0/90 lỗi ngôn ngữ), nên đổi sang Gemini **chỉ thấy phần
tốn thêm**, không thấy phần được.

Bằng chứng đổi backend nằm ở **giọng thật**: `phowhisper-reread` cho WER **0,711** và
chỉ **6/31** lượt có transcript dùng được, so với `gemini-audio` WER **0,370** và
**21/31** dùng được. Hai bộ số ấy đo hai chuyện khác nhau và **không được để chung một
bảng**: v3 trả lời "đổi backend tốn thêm bao nhiêu mili-giây", còn bộ giọng thật trả
lời "đổi backend có đáng không".

## Danh mục file thêm

| file | nội dung |
|---|---|
| `latency_desktop_baseline_2026-09-06_v3.jsonl` | 90 lượt v3 — **bộ mic giả chính thức** |
| `baseline_config_2026-09-06_v3.json` | bản chụp .env / package / máy / git / thay đổi so với v2 |

---

# Replay — 31 WAV giọng thật chạy lại trên v3 (2026-09-06)

`latency_desktop_replay_2026-09-06_v3.jsonl` (31 lượt).
`python scripts/bench_latency.py --run --wav-dir logs/utts --refs docs/baseline/realvoice_2026-09-06_v2_refs.json`

**Đây là phép so sạch nhất của cả dự án tới giờ.** Cùng **một bộ audio giọng người**,
đi qua **đúng đường mic thật** (kể cả VAD, nên `t_vad_end` có nghĩa), chỉ khác nguồn
audio đến từ file thay vì micro. Nó bỏ được cái dễ của giọng TTS mà bench mic giả có,
và lặp lại được — thứ mà một phiên nói thật không có.

Câu mẫu đi kèm từng bản ghi (`ref`), nên `latency._score_language()` chấm luôn WER/CER
vào log. Không còn bước ghép log với file refs bằng tay — đó chính là chỗ đã một lần
gán nhầm câu mẫu cho lượt #17.

## Chất lượng — cùng 31 file, hai pipeline

| | WER | CER | WER p50 | lượt dùng được | lỗi ngôn ngữ STT |
|---|---|---|---|---|---|
| **giọng thật v2** (`phowhisper-reread`) | 0,678 | 0,475 | 0,857 | **6/31** | **6/31** |
| **replay v3** (`gemini-audio`) | **0,339** | **0,265** | **0,250** | **20/31** | **0/31** |

- **Đúng ngôn ngữ STT 31/31 và LLM 29/29** (trên các lượt có trả lời). Whisper trên
  cùng bộ audio sai 6/31.
- **WER giảm một nửa** (0,678 → 0,339) và số lượt có transcript dùng được **tăng hơn
  ba lần** (6 → 20).
- **Kiểm chéo phép đo:** chấm lại offline bằng `rescore_utts.py` cho `gemini-audio`
  WER **0,333**; chạy qua pipeline thật ra **0,339** — lệch 0,006. Hai đường đo độc
  lập (một cái đọc thẳng WAV, một cái đi qua VAD + hàng đợi) cho cùng một con số, nên
  con số ấy đáng tin.

## Cổng và fallback — lần đầu thấy chúng chạy trên giọng thật

| | |
|---|---|
| `asked_again` (cổng chặn) | **2/31** |
| `stt_fallback` (lùi Whisper) | **2/31** |

| lượt | chuyện gì xảy ra |
|---|---|
| `..._029.wav` | Gemini trả transcript **rỗng** cho 1,09 s audio → cổng bắt bằng tín hiệu "quá ngắn" → hỏi lại bằng `en` |
| `..._012.wav` | Gemini **quá hạn 4 s** → lùi Whisper (`t_stt` 5 022 ms) → Whisper chép "Gắn thôi" với `logprob` thấp → **cổng cũng chặn** → hỏi lại bằng `vi` |
| `..._004.wav` | Gemini quá hạn → lùi Whisper (`t_stt` 5 172 ms), transcript đủ tốt nên đi tiếp |

Lượt `012` là ca đáng giá nhất: **hai lớp bảo vệ nối tiếp nhau đúng như thiết kế** —
mạng hỏng thì Whisper gánh, Whisper nghe không chắc thì hỏi lại, và người dùng nhận
được một câu hỏi lại thay vì một câu trả lời bịa. Bản ghi của nó không có
`end_to_end_ms`, đúng quy ước "lượt hỏi lại không phải lượt trả lời".

## Latency theo tầng

| bộ | n | stt p50/p95 | llm p50/p95 | tts p50/p95 | out | **e2e p50/p95** |
|---|---|---|---|---|---|---|
| **replay v3** (gemini) | 29 | 2911 / 3756 | 1053 / 2395 | 288 / 3994 | 2 | **5418 / 8007** |
| replay · nói vi | 17 | 2867 / 3756 | 1070 / 2395 | 240 / 311 | 1 | 4777 / 5547 |
| replay · nói en | 12 | 3153 / 3639 | 1034 / 1124 | 2888 / 3994 | 2 | 7207 / 8007 |
| bench mic giả v3 (gemini) | 90 | 2805 / 3655 | 1039 / 2207 | 337 / 2808 | 1 | 5129 / 7649 |
| giọng thật v2 (Whisper) | 31 | 1354 / 2050 | 1051 / 2186 | 2503 / 4650 | 2 | 4824 / 7185 |

*(n=29 vì 2 lượt bị cổng chặn không có e2e.)*

Chênh lệch (p50 / p95):

| | stt | llm | tts | **e2e** |
|---|---|---|---|---|
| replay − bench mic giả v3 | **+105 / +101** | +14 / +188 | −49 / +1186 | **+289 / +358** |
| replay − giọng thật v2 (Whisper) | **+1557 / +1705** | +2 / +208 | −2214 / −656 | **+594 / +822** |

Đọc bảng:

- **Mic giả đo thay được cho giọng thật, và nay còn đúng hơn trước.** Tầng `stt` chỉ
  lệch **+105 ms p50**. Với `gemini-audio` điều này hợp lý: thời gian một lượt gần như
  hoàn toàn là đường mạng, không phụ thuộc audio dễ hay khó — khác hẳn Whisper, nơi
  giọng người làm model phải làm việc nhiều hơn.
- **Giá thật của việc đổi backend, đo trên CÙNG audio: `stt` +1 557 ms, `e2e` +594 ms.**
  Đây là con số nên trích dẫn, không phải +1 044 ms của bench mic giả (bộ đó khác cả
  audio lẫn tỉ lệ ngôn ngữ).
- **Tầng `tts` giảm 2 214 ms so với v2** — không phải TTS nhanh lên. Ở v2, 6 lượt
  tiếng Việt bị nghe nhầm thành tiếng Anh nên vịt đáp tiếng Anh và phải dùng Kokoro
  (không stream). Nay nghe đúng 31/31 nên chúng về VieNeu (stream, 240 ms). **Sửa đúng
  STT làm tầng TTS rẻ đi** — hiệu ứng bậc hai, không nhìn bảng thì không thấy.
- **Nhánh tiếng Anh vẫn là chỗ đắt nhất**: `e2e` p50 **7 207 ms**, trong đó `tts`
  chiếm 2 888 ms vì Kokoro không stream. Đây là lý do bằng số, đo trên giọng thật, cho
  việc Kokoro streaming đã xếp hàng trong `PLAN.md`.

## Danh mục file thêm

| file | nội dung |
|---|---|
| `latency_desktop_replay_2026-09-06_v3.jsonl` | 31 lượt phát lại WAV giọng thật qua pipeline v3 |
