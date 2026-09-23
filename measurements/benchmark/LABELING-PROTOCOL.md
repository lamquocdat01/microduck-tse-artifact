# Giao thức gán nhãn bộ câu hỏi định tuyến tra cứu

Ngày viết: **09/09/2026**. Viết **TRƯỚC** khi gán một nhãn nào — nếu viết sau thì
việc gán thành hồi cứu, và người phản biện sẽ bắt đúng chỗ đó.

Bộ dữ liệu sinh ra từ tài liệu này: `docs/benchmark/lookup_set_v1.jsonl`.
Sinh bằng `desktop/scripts/build_lookup_set.py`.

## 1. Vì sao không tự bịa bộ câu hỏi

Bộ 30 câu ngày 09/09 (`lookup_flag_20260909_v1.jsonl`) do chính người viết luật
trong persona gán nhãn. Nó cho precision/recall 1,000 — con số đẹp mà không chứng
minh được gì, vì hai bên cùng một cách hiểu (ghi ở `ADR-010` §5).

Thay bằng **FreshQA**: Vu et al., *FreshLLMs: Refreshing Large Language Models with
Search Engine Augmentation*, Findings of ACL 2024,
<https://aclanthology.org/2024.findings-acl.813>, repo `freshllms/freshqa`,
**giấy phép Apache-2.0** (đã kiểm 09/09/2026 trước khi dùng).

Cái ta mượn là **định nghĩa đã qua bình duyệt**, không phải chỉ mấy câu hỏi. Thay
vì phải tự bảo vệ tiêu chí của mình, chỉ cần trỏ tới định nghĩa của họ.

## 2. FreshQA thực tế có cấu trúc gì — sửa một hiểu nhầm

Bản tải 09/09/2026 (bảng cập nhật hằng tuần) có **600 câu**, và **không** phải bốn
loại song song như thường được tóm tắt. Nó là **lưới 3 × 2**, hai chiều vuông góc:

| cột | giá trị | số câu |
|---|---|---|
| `fact_type` | `never-changing` / `slow-changing` / `fast-changing` | 225 / 220 / 155 |
| `false_premise` | `FALSE` / `TRUE` | 451 / 149 |

Nghĩa là một câu có thể **vừa** `fast-changing` **vừa** tiền đề sai. Điều này khớp
đúng với thiết kế nhãn của ta: `[lookup]` và `[premise]` được phép cùng xuất hiện.

Cột khác dùng tới: `split` (TEST 500 / DEV 100), `num_hops`, `effective_year`.

## 3. Ánh xạ sang nhãn của ta

### 3.1 `needs_lookup` — câu này có cần tra cứu ngoài không

| `fact_type` | `needs_lookup` | ghi chú |
|---|---|---|
| `fast-changing` | **true** | đáp án đổi trong vài ngày/tuần |
| `slow-changing` | **true** | đáp án đổi trong vài năm — **đánh dấu `borderline: true`** |
| `never-changing` | **false** | đáp án tĩnh |

`slow-changing` là vùng xám và **giữ lại, không vứt đi**. Đó là chỗ bộ định tuyến
sẽ lung lay nhất, tức chỗ số liệu nói được nhiều nhất.

### 3.2 `needs_premise` — câu này có tiền đề sai không

`needs_premise = (false_premise == TRUE)`, lấy thẳng từ FreshQA.

### 3.3 Ca tiền đề sai thì `needs_lookup` KHÔNG chấm

Đặt `needs_lookup: null` cho mọi câu có `needs_premise: true`.

Lý do: hành vi đúng với một tiền đề sai là **phản bác**, và tra cứu không chữa được
— nó chỉ làm model tìm ra thứ gì gần gần rồi hợp lý hoá cái tiền đề. Nhưng vịt gắn
thêm `[lookup]` để nói "em cần kiểm chứng mới chắc" cũng **không sai**. Chấm nó là
đúng hay sai đều áp đặt một lựa chọn mà chính FreshQA không quy định.

Nên các câu này chấm riêng, chỉ trên `needs_premise`.

## 4. Cỡ mẫu và cân bằng

**120 câu, chia hai khối tách bạch.**

Khối A — chấm định tuyến `[lookup]`, **100 câu**, tiền đề đều ĐÚNG:

| | tiếng Anh | tiếng Việt | `needs_lookup` |
|---|---|---|---|
| `never-changing` | 25 | 25 | false |
| `fast-changing` | 15 | 15 | true |
| `slow-changing` | 10 | 10 | true (`borderline`) |
| **cộng** | **50** | **50** | 50 true / 50 false |

Khối B — chấm nhãn `[premise]`, **20 câu**, tiền đề đều SAI: 10 tiếng Anh + 10
tiếng Việt, rải trên cả ba `fact_type`.

**Cân bằng ngôn ngữ là bắt buộc**, không phải trang trí: hệ này song ngữ và ngôn
ngữ đã là một phát hiện lớn của dự án (ADR-008 — lịch sử hội thoại thắng system
prompt ở việc chọn ngôn ngữ, 2/15 so với 15/15). Bộ thử lệch tiếng Anh thì bỏ phí
mất mạch mạnh nhất đang có.

## 5. Nửa tiếng Việt: dựng NATIVE, không dịch máy

**Không dịch FreshQA sang tiếng Việt.** Một câu `fast-changing` của Mỹ dịch sang
tiếng Việt vẫn là câu hỏi về nước Mỹ — nó đo khả năng đọc tiếng Việt, không đo được
gì về ngữ cảnh Việt Nam.

Dựng mới theo **đúng ba `fact_type` và cùng cách hiểu `false_premise`**, chủ đề
Việt Nam: tuyển sinh đại học, giá cả trong nước, lịch sự kiện, tin trong nước, địa
lý và lịch sử Việt Nam.

Ca đã hỏng thật của dự án — *"tuyển sinh tiến sĩ Đại học Khoa học Tự nhiên"* —
là mẫu `fast-changing` tiếng Việt hoàn hảo, đưa vào bộ.

Tiêu chí cụ thể cho người gán nửa tiếng Việt, áp dụng theo đúng thứ tự:

1. **Đáp án có đổi theo thời gian không, và nhanh cỡ nào?**
   Đổi trong vài ngày/tuần → `fast-changing`. Đổi trong vài năm → `slow-changing`.
   Không đổi → `never-changing`.
2. **Câu hỏi có khẳng định sẵn điều gì không?** Có, và điều đó sai hoặc không có
   căn cứ → `false_premise: TRUE`.
3. **Có kiểm chứng được bằng một nguồn nêu ra được không?** Không nêu được nguồn
   nào thì câu hỏi đó không dùng — bỏ, đừng đoán nhãn.

## 6. Ai gán, và hạn chế phải nói ra

| khối | nguồn nhãn | người gán |
|---|---|---|
| tiếng Anh | FreshQA (`fact_type`, `false_premise`) | nhóm tác giả FreshQA, đã bình duyệt |
| tiếng Việt | dựng mới theo §5 | **một người duy nhất** — Claude Opus 5, phiên 09/09/2026 |

**Hạn chế, ghi thẳng vào bài, không lờ đi:**

- Nửa tiếng Việt do **một người gán**, không có lượt gán thứ hai, nên **không có
  Cohen's kappa**. Muốn con số này đứng vững thì cần chủ nhân gán lại độc lập một
  lượt nữa, hoặc một người thứ hai. Chỗ trống ấy để nguyên trong `PAPER-OUTLINE.md`,
  không lấp bằng chữ.
- Nửa tiếng Anh **không** cùng người gán với nửa tiếng Việt. So sánh giữa hai ngôn
  ngữ vì thế trộn hai nguồn nhãn — phải nói ra khi diễn giải.

## 7. Ngày gán nhãn là một phần của dữ liệu

Mỗi dòng mang `labeled_at`. **"Cần tra cứu" phụ thuộc thời điểm**: câu hôm nay cần
tra, sang năm có thể đã nằm trong dữ liệu huấn luyện của model. Bảng FreshQA cũng
cập nhật hằng tuần và có cột `next_review` vì đúng lý do đó.

Không có ngày thì một năm sau không ai nói được bộ này còn hiệu lực hay không.

## 8. Định dạng mỗi dòng `lookup_set_v1.jsonl`

```json
{
  "id": "en-fast-003",
  "lang": "en",
  "question": "…",
  "needs_lookup": true,
  "needs_premise": false,
  "borderline": false,
  "fact_type": "fast-changing",
  "source": "freshqa",
  "source_id": "…",
  "annotator": "freshqa-authors",
  "labeled_at": "2026-09-09",
  "block": "A"
}
```

`needs_lookup` là `null` ở khối B (§3.3). `source` là `freshqa` hoặc `microduck-vi`.
