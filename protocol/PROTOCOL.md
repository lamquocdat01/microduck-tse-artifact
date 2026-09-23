# PROTOCOL — giao thức đo

Hai giao thức, không liên quan nhau, để chung một chỗ vì cả hai đều là "cách đo phải
cố định trước khi đo, không phải sau khi thấy số":

- **§A. Chuẩn hoá văn bản khi chấm WER** — 07/09/2026, áp cho mọi bảng WER.
- **§B. Loopback vật lý đo chặng mic → loa của thiết bị** — 09/09/2026, áp cho mọi số
  trong `DEVICE-FLOOR.md` có nhắc chặng xuống.

---

# §A — chuẩn hoá văn bản khi chấm WER

Ngày: 07/09/2026. Áp dụng cho mọi bảng WER trong repo này kể từ hôm nay.

## Vì sao có tài liệu này

Vu, Nguyen & Nguyen, **"Vietnamese Automatic Speech Recognition: A Revisit"**,
*Findings of the Association for Computational Linguistics: EACL 2026*, tr. 6557–6568.
<https://aclanthology.org/2026.findings-eacl.345> · code: <https://github.com/Qualcomm-AI-research/PhoASR>

Bảng 6 của họ, **cùng audio, cùng model**:

| model | O-WER | N-WER | chênh |
|---|---|---|---|
| whisper-small (chưa tinh chỉnh) | 70,16 | 64,07 | 1,1× |
| ChunkFormer-large-vi (25K) | 32,43 | **6,89** | 4,7× |
| **PhoWhisper-small (844h)** | **33,90** | **8,97** | **3,8×** |
| wav2vec2 (469h) | 51,15 | 14,10 | 3,6× |
| PhoASR-whisper-small-469h | 12,46 | 8,69 | 1,4× |
| PhoASR-whisper-small-3100h | **11,70** | 8,20 | 1,4× |

Hai điều phải rút ra:

1. **Chênh 3,8 lần chỉ do chuẩn hoá văn bản.** Báo một thước là mời người phản biện
   quy toàn bộ khoảng cách của ta về chuẩn hoá chứ không phải về âm học.
2. **Thứ hạng ĐỔI ĐƯỢC giữa hai thước.** Trong chính bảng trên: ChunkFormer thua
   PhoASR-3100h ở O-WER (32,43 vs 11,70) nhưng **thắng** ở N-WER (6,89 vs 8,20).
   Nên "đổi thước có đổi kết luận không" là câu hỏi phải TRẢ LỜI BẰNG SỐ, không phải
   câu hỏi tu từ.

## Ba thước, chạy song song, không cái nào thay cái nào

`desktop/scoring.py`. Cả ba dùng chung Levenshtein hai hàng và cùng cách gộp corpus
(cộng dồn lỗi rồi chia tổng độ dài tham chiếu, **không** lấy trung bình WER từng câu).

### O-WER — `normalize_ower()`

Nguyên văn định nghĩa của họ (§5.1, tr. 6563):

> **Orthographic WER (O-WER)**: This is calculated using the raw, unnormalized text,
> preserving the original capitalization and punctuation. It offers a strict measure
> of the model's ability to produce well-formatted output.

Cài đặt: **không chuẩn hoá gì**, chỉ gộp khoảng trắng để tách được token.

### N-WER — `normalize_nwer()`

> **Normalized WER (N-WER)**: Before calculating WER, both the predicted and reference
> texts are normalized by converting them to lowercase and removing all punctuation.
> This approach emphasizes core lexical accuracy, disregarding formatting differences.

Cài đặt, theo đúng thứ tự:

1. `unicodedata.normalize("NFC", text)` — **xem cảnh báo bên dưới**;
2. `.lower()`;
3. `re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)` — bỏ mọi ký tự không phải chữ,
   chữ số, gạch dưới hay khoảng trắng. Đây là đúng cài đặt trong code của họ
   (`src/phoasr_data_pipeline/text.py::normalize_for_compare`);
4. gộp khoảng trắng.

**KHÔNG làm ba việc sau, vì họ không làm:** không quy số viết bằng chữ về chữ số
("ba giờ" ≠ "3 giờ", vẫn tính là lỗi) · không chuẩn hoá biến thể tên riêng ·
**không bỏ dấu thanh**.

> ### ⚠ Bước NFC là bắt buộc, và đây là chỗ ta đi chệch code của họ
>
> `normalize_for_compare` của họ **không** gọi NFC. Với chuỗi ở dạng NFD, dấu thanh
> tiếng Việt là ký tự tổ hợp (Unicode category `Mn`), **không khớp `\w`**, nên regex
> bỏ dấu câu xoá sạch dấu thanh. Đo trên chính máy này:
>
> ```
> NFC -> 'Nhắc anh họp lúc ba giờ chiều thứ Sáu'
> NFD -> 'Nha c anh ho p lu c ba gio chie u thu Sa u'
> ```
>
> Dấu thanh tiếng Việt **mang nghĩa** — ADR-002 tồn tại vì `base` chép "nghỉ giải lao"
> thành "nghỉ dài lâu". Mất dấu là mất phép đo. Nên NFC là điều kiện tiên quyết, không
> phải tuỳ chọn. Ghi rõ ở đây để ai so số với bài gốc biết ta khác họ đúng một bước, và
> vì sao.

### D-WER — `normalize()` (thước cũ của repo, giữ nguyên)

N-WER **cộng thêm** hai bước riêng của repo này:

- **số viết bằng chữ ≡ chữ số** (`NUMBER_WORDS`). Lý do ban đầu: `gemini-audio` chép
  "ba giờ chiều thứ Sáu" thành "3 giờ chiều thứ sáu", và WER phạt 0,22 cho riêng quy
  ước chính tả ấy.
- **biến thể tên riêng** (`NAME_VARIANTS`: `vịt` → `vit`).

Nên **D-WER là thước LỎNG NHẤT trong ba cái**: `D ≤ N ≤ O` trên cùng transcript.

### Hệ quả quan trọng: số cũ của repo KHÔNG phải O-WER

Trước hôm nay repo chỉ có một cột WER, và cột đó là **D-WER**. Con số 0,708 (Whisper)
so với 0,333 (Gemini) ở ADR-004 **đã được đo sau chuẩn hoá**, thậm chí chuẩn hoá mạnh
hơn N-WER. Vì vậy phản biện "khoảng cách của các anh chỉ là chuẩn hoá" **không áp cho
cột cũ** — nhưng ta vẫn phải in cả ba cột thì mới chứng minh được điều đó.

Ví dụ trên một câu (ref `Nhắc anh họp lúc ba giờ chiều thứ Sáu.`, hyp
`Nhắc anh họp lúc 3 giờ chiều thứ sáu`):

| thước | ref sau chuẩn hoá | WER |
|---|---|---|
| O-WER | `Nhắc anh họp lúc ba giờ chiều thứ Sáu.` | 0,222 |
| N-WER | `nhắc anh họp lúc ba giờ chiều thứ sáu` | 0,111 |
| D-WER | `nhắc anh họp lúc 3 giờ chiều thứ 6` | 0,000 |

## Cách chạy

```powershell
cd desktop
.\.venv\Scripts\python.exe scripts\rescore_utts.py logs\utts `
    --refs ..\docs\baseline\realvoice_2026-09-06_v2_refs.json `
    --local-candidates --deterministic --out logs\rescore_v4_owner_nwer.json
```

`--deterministic` ghim `temperature=0` (ADR-007). Bắt buộc khi so thước với thước:
không ghim thì faster-whisper lấy mẫu ngẫu nhiên ở câu ngắn, và ta sẽ không phân biệt
được "đổi thước làm đổi số" với "chạy lại làm đổi số".

`report()` tự chạy `check_rank_change()`. Thứ hạng backend đổi giữa hai thước bất kỳ
→ in **"DỪNG VÀ BÁO CHỦ NHÂN — ADR-004 phải xem lại"**.

## Cái tài liệu này KHÔNG quy định

- Giao thức của họ chỉ nói về **chuẩn hoá văn bản khi chấm**. Nó không nói gì về cách
  chọn ground truth, cách ghép WAV với câu mẫu, hay ngưỡng tin cậy — những cái đó ở
  `ADR-004`, `ADR-007`, `ADR-009`.
- Phần lớn bài của họ là về **dựng bộ dữ liệu** (pipeline 7 bước, num2word, forced
  alignment). Ta không dùng phần đó; ta chỉ lấy đúng định nghĩa hai thước ở §5.1.


---

# §B — loopback vật lý: đo chặng mic → loa

Ngày: 09/09/2026. Áp cho mọi số của chặng xuống trong `docs/benchmark/DEVICE-FLOOR.md`.
Cài đặt: `desktop/scripts/bench_loopback.py`.

## Vấn đề nó giải

`t_dev_ack` **rỗng ở mọi lượt**: firmware v2.3.0 của board ES3C28P không gửi ngược
`tts state=start`. Nên mọi mốc phía server đều dừng ở **lúc byte rời server**, và
phần Wi-Fi chiều xuống + board giải mã + I2S đẩy ra loa **không đo được từ xa**. Đây
là chặng cuối cùng còn thiếu của bảng device floor.

## Điểm mấu chốt: vì sao KHÔNG cần đồng bộ đồng hồ

**Một file ghi âm duy nhất chứa CẢ tín hiệu kích thích LẪN tiếng board đáp.** Khoảng
cách giữa hai đỉnh trong file ấy chính là độ trễ vòng.

Đó là một **hiệu của hai mốc đo trên cùng một đồng hồ**, không phải hiệu của hai đồng
hồ khác nhau. Nên không có sai số đồng bộ nào để mà cãi — và đó là lý do phương pháp
này dùng được với một cái điện thoại đặt cạnh board, chẳng cần thiết bị gì đắt hơn.

Cùng lý lẽ ấy cho phần trừ đi: `t_tx_first − t_rx_speech_first` cũng là một **hiệu**,
đo trên đồng hồ của server. Cộng trừ hai hiệu đo trên hai đồng hồ khác nhau vẫn hợp
lệ; chỉ cần hai đồng hồ chạy đúng **nhịp**, mà thạch anh nào cũng đúng nhịp tới cỡ
ppm. Cái không được phép làm là so hai **mốc tuyệt đối** của hai đồng hồ chưa đồng bộ.

## Bắt buộc

1. **Chế độ `--reply tone`.** Server đáp bằng một âm cố định khi VAD chốt; xử lý phía
   server gần như bằng 0, nên cái đo được là **sàn thiết bị**, không lẫn STT/LLM/TTS.
2. **CẤM `--reply echo`** — và `tone` cũng KHÔNG miễn nhiễm; câu này đã viết sai một
   lần, sửa ngày 09/09. AEC chưa từng chạy trên board — ES8311 không có kênh tham
   chiếu (ADR-013 §10.2). `echo` phát lại đúng cái mic vừa nghe nên vòng lặp vừa tự
   nuôi vừa **lớn dần**. `tone` **không lớn dần** (âm ra không phụ thuộc âm vào) nhưng
   vẫn **tự kích hoạt lại**: chỉ cần tiếng loa vượt ngưỡng VAD của mic là vòng chạy
   mãi ở biên độ không đổi. Đo 09/09: chu kỳ 2–3 giây, `audio_ms` hằng số 780 ms, và
   ở âm lượng 85 thì RMS đỉnh 15 000–22 500 — nghe rõ bằng tai.

   Nên bắt buộc chạy với **`--cooldown-ms >= 3000`** (tone dài 1,5 s) và để âm lượng
   board vừa đủ cho mic ngoài nghe thấy. Ngưỡng an toàn là **âm lượng**, không phải
   chế độ trả lời.
3. **Kích thích là tiếng CLICK ngắn, dứt khoát**, không phải giọng nói. Cần sườn lên
   sắc để định vị đỉnh; giọng nói lên biên độ thoai thoải qua cả trăm ms, sai số định
   vị lúc đó to ngang thứ đang đo. Click là ồn trắng lọc thông cao 6 ms, không phải
   một hình sin ngắn — hình sin thì đỉnh của nó là đỉnh của sóng mang, lệch tới nửa
   chu kỳ.
4. **Thu ở 48 kHz.** Một mẫu = 20,8 µs, thừa mịn cho thứ đang đo.
5. **Lặp ≥10 lần. Báo p50/p95, KHÔNG báo trung bình.** Một lượt Wi-Fi vấp là đủ hỏng
   trung bình ở n = 12.

## Phân rã

    Δ_vòng      hiệu hai đỉnh trong file thu — mic → server → loa, ĐỦ CẢ VÒNG
    Δ_server    t_tx_first − t_rx_speech_first, phần server tự ghi được
                (cõng cả 700 ms SILENCE_END_MS mà VAD phải chờ)
    Δ_còn lại   Δ_vòng − Δ_server = chặng lên + chặng xuống
    chặng lên   ước lượng: nửa khung Opus (30 ms) + rtt_p50/2
    chặng xuống Δ_còn lại − chặng lên   ← con số cần

`t_rx_speech_first` là mốc **khung đầu tiên CÓ TIẾNG**, không phải `t_rx_first`. Ở
`mode=auto` board phát liên tục nên khung đầu của lượt thường là im lặng, và khoảng
cách giữa hai mốc là quãng chờ người ta mở miệng — nó không thuộc về độ trễ thiết bị.
Trừ nhầm mốc là cộng cả quãng chờ ấy vào chặng xuống.

## Ghép lượt thu với lượt log — và điều kiện để phép ghép ấy đúng

Ghép theo **thứ tự**: click thứ k đi với lượt thứ k. Ghép theo mốc tuyệt đối thì lại
phải đồng bộ đồng hồ — đúng cái vừa tránh được.

**Nhưng phép ghép này chỉ đúng khi mỗi click sinh ĐÚNG MỘT lượt**, và giả định ấy đã bị
bác ngày 09/09: board tự kích hoạt nên 20 click ra 48 lượt. Ghép theo thứ tự lúc đó cho
ra một bảng **trông hoàn toàn bình thường và sai từ dòng đầu** — mỗi Δ ghép nhầm với
tiếng tone của lượt trước.

Nên trước khi ghép, **phải kiểm**: số lượt ghi thêm trong `device_floor.jsonl` phải
bằng số click đã phát, và không lượt nào mang `cooldown: true`. Lệch thì bỏ cả mẻ, đừng
cắt phần chung — phần chung cũng đã lệch pha rồi.

## Phải ghi kèm, không được bỏ

- **Mic gì.** Mic điện thoại và mic laptop đều hợp lệ; mic laptop thì tự động hoá được
  nên lặp được nhiều lần, và số lần lặp mới là thứ quyết định p95 có đáng tin không.
- **Khử ồn của hệ điều hành có chen vào đường thu không.** Nó có thể **nuốt** đỉnh thứ
  hai, không thể **dời** đỉnh ấy sớm hơn — nên sai số nghiêng về phía làm số xấu đi,
  không phải đẹp đi.
- **Số ra là CHẶN DƯỚI**, dùng để so tương đối giữa các cấu hình, **không phải giá trị
  tuyệt đối**. Không có thiết bị đo chuẩn thì không được phát biểu như thể có.

## Số phân tán bất thường thì nghi gì trước

**Nghi tiếng vọng phòng trước, đừng nghi board trước.** Đỉnh thứ hai có thể lẫn phản
xạ tường, sườn lên nhoè ra và mốc chấm trôi theo. Thử lại ở chỗ ít vọng hơn trước khi
kết luận bất cứ điều gì về thiết bị.
