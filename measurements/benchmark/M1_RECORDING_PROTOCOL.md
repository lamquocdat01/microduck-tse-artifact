# M1 — protocol thu 69 utterance real-voice mới (tầng chính, rv2)

**Viết 16/09/2026 (đợt 27b), TRƯỚC khi thu. v2 cùng ngày sau kiểm máy — xem mục Bộ câu.** Chép protocol phiên 06/09 (bộ rv1, 31 WAV —
`docs/baseline/README.md` §"Giọng thật trên v2"), chỉ đổi **bộ câu**. Bộ câu **đã duyệt** (v2, sau
ba kiểm tra máy của chủ nhân); đổi câu nào sau này phải sửa `M1_rv2_sentences.json`, chạy lại
`m1_kiem_bo_cau.py`, và làm TRƯỚC khi thu — không sửa sau khi thu.

## Vì sao 23 câu × 3, không phải 10 câu cũ × 7

rv1 đọc 10 câu, mỗi câu ~3 lần. Đọc lại đúng 10 câu ấy thêm 7 lần thì 100 utterance chỉ
mang 10 nội dung, và tỉ lệ "transcript đổi" sẽ là tỉ lệ của 10 câu, không phải của 100.
23 câu mới × 3 lần giữ đúng **nhịp** của rv1 (một câu đọc ~3 lần liền) mà tăng số **nội
dung** lên 33.

## Cách thu (giống 06/09)

1. Chạy app desktop như thường (`python app.py`), backend nào cũng được — WAV sau VAD tự lưu
   vào `desktop/logs/utts/<stamp>_NNN.wav` (gitignore, không rời máy).
2. Mic: tai nghe/mic dùng ở 06/09 nếu còn (doctor 16/09 thấy mặc định *Headset (EarPods)*).
   Phòng yên, giọng nói thường, không cố đọc rõ hơn lúc dùng thật.
3. Đọc **theo khối**: câu 1 ba lần liền, rồi câu 2 ba lần, … tới câu 23. Mỗi lần đọc là một
   lượt (chờ vịt trả lời hoặc ngắt), để VAD cắt đúng một utterance.
4. Đọc hỏng (vấp, ho, VAD cắt đôi) ⇒ **đọc thêm một lần** ngay trong khối, và ghi **số thứ tự
   file** hỏng vào *Ghi chép phiên* dưới. Không xoá WAV nào.
5. Đặt tên — số lần đọc nằm trong tên file:
   ```
   python desktop\scripts\m1_dat_ten_rv2.py --stamp <stamp> --bo <các số hỏng>          # xem trước
   python desktop\scripts\m1_dat_ten_rv2.py --stamp <stamp> --bo <các số hỏng> --chep   # chép
   ```
   Chép (không di chuyển) sang `desktop/logs/utts_rv2/rv2_sNN_rK.wav` (NN = câu 01..23, K = lần
   đọc 1..3), không bao giờ ghi đè; số file ≠ 69 thì dừng. Ghi `docs/benchmark/M1_rv2_manifest.json`.
6. `python desktop\scripts
6. `python desktop\scripts\run_m_all.py status` — dòng M1 hết "chờ đầu vào" cho tầng chính.
   Runner tự nhận trong ≤ 30 s khi **đủ 69** file đúng tên; không cần khởi động lại. Tầng chính
   (31 rv1 + 69 rv2 + probe) chạy **cùng một đợt**.

## Bộ câu — v2 (đã duyệt, đã qua kiểm máy)

Nguồn duy nhất: `docs/benchmark/M1_rv2_sentences.json`. Kiểm: `python desktop\scripts\m1_kiem_bo_cau.py` (rc=0).

**v1 (23 câu đã duyệt 16/09, bản trước của file này) CHƯA ĐẠT** khi kiểm 16/09:
- (a) số từ trung bình 7,17 so với pilot 5,42 (lệch 1,75 > 1,0) — bộ mới dài hơn, tức dễ hơn cho ASR;
- (b) *"Switch to English."* gần trùng chữ *"Switch to Vietnamese."* (ratio 0,72); *"Đổi sang tiếng
  Việt đi em."* trùng NGHĨA với câu ấy (máy không bắt được, soát tay).
Đối chứng dương của công cụ kiểm: chạy trên chính bộ pilot ⇒ đỏ 10/10 câu.

**v2** (rút ngắn, thay hai câu trùng; phần còn lại giữ nội dung v1):

| | pilot (31 utt) | v2 (69 utt) | ngưỡng |
|---|---|---|---|
| tỉ lệ tiếng Việt | 61,3 % | 60,9 % | ± 10 điểm |
| số từ trung bình / trung vị | 5,42 / 6 | 5,00 / 5 | ± 1,0 |
| câu ≤ 2 từ | 19,4 % | 13,0 % | ± 10 điểm |
| có từ khó ASR (luật chung) | 71,0 % | 60,9 % | ≥ 1/3 và ≥ pilot − 15 |
| gần trùng pilot | — | 0 (ratio max 0,51) | ratio < 0,6, Jaccard < 0,5 |

⚠ Một trong 14 câu "khó" là *"Nhỏ tiếng lại **một** chút"* — luật đếm số viết chữ, nhưng "một chút"
khó ASR thì yếu. Bỏ nó: 13/23 = 57 %, vẫn trong ngưỡng.

**v3** (17/09 — việc 120.1, làm bù ở đợt 27d): câu 9 thay bằng *"Nhắn Zalo cho anh Tuấn."* (từ vay
mượn + tên riêng); 22 câu còn lại giữ nguyên; luật đếm **không** đổi (áp y hệt cho pilot).
`m1_kiem_bo_cau.py` rc = 0: vi 60,9 % vs 61,3 %; từ TB 5,00 vs 5,42; ≤ 2 từ 13,0 % vs 19,4 %;
có từ khó 60,9 % vs 71,0 % (14/23, giờ 14 câu đều khó thật); gần trùng 0 (ratio max 0,51).

⚠ **AMENDMENT 04 (17/09): KHÔNG thu giọng thật theo bộ này nữa.** Bộ v3 là văn bản cho tầng **S3**
(tổng hợp, `docs/benchmark/M1_s3_manifest.json`). Bảng dưới là **v3**.

| # | câu | lang |
|---|---|---|
| 1 | Mai bảy giờ anh bay ra Hà Nội. | vi |
| 2 | Gọi cho chị Hằng lúc năm giờ. | vi |
| 3 | Anh ngủ có bốn tiếng. | vi |
| 4 | Được rồi. | vi |
| 5 | Đọc lại câu vừa rồi. | vi |
| 6 | Họp ở tầng mười hai. | vi |
| 7 | Mở nhạc Trịnh Công Sơn. | vi |
| 8 | Cuối tháng nộp báo cáo quý ba. | vi |
| 9 | Nhắn Zalo cho anh Tuấn. | vi |
| 10 | Anh thích cà phê sữa đá. | vi |
| 11 | Hủy hẹn chiều thứ Tư. | vi |
| 12 | Tiếp tục. | vi |
| 13 | Anh chạy bộ thứ Ba và thứ Năm. | vi |
| 14 | Sài Gòn hôm nay có mưa không? | vi |
| 15 | What time is my next meeting? | en |
| 16 | Back up the database on Friday. | en |
| 17 | Please speak more slowly. | en |
| 18 | How many new emails? | en |
| 19 | Cancel that. | en |
| 20 | Flight VN two four seven. | en |
| 21 | Summarize the last three messages. | en |
| 22 | Open Google Maps. | en |
| 23 | That's all, thanks. | en |

WAV giọng thật **không** vào repo công khai (`paper/data-package/EXCLUDED.md` §1).

## Ghi chép phiên

*(điền khi thu: ngày giờ, mic, stamp, số thứ tự các lượt hỏng)*
