# Kiểm chứng xung nhịp CPU — 2026-09-05

**Kết luận: (a) WMI báo sai. Xung nhịp thực dao động bình thường và turbo lên tới 3902 MHz. Baseline v1 hợp lệ.**

Báo cáo này bác bỏ cảnh báo tôi đưa ra khi tổng kết baseline v1, rằng "CPU bị ghim ở
1198 MHz (40% xung nhịp)". Cảnh báo đó dựa trên `Win32_Processor.CurrentClockSpeed`,
và con số ấy không phải tần số thật.

---

## 1. Phương pháp

Máy: 11th Gen Intel Core i7-1185G7, base 2995 MHz (`Win32_Processor.MaxClockSpeed`),
4 nhân / 8 luồng.

Lấy mẫu **mỗi 1 s trong 60 s**, chia ba pha: 15 s nghỉ → 30 s chạy tải 1 core
(`python spin.py`, vòng `while True: pass`) → 15 s nghỉ.

```powershell
Get-Counter '\Processor Information(_Total)\% Processor Performance',
            '\Processor Information(_Total)\% Processor Utility',
            '\Processor Information(_Total)\% of Maximum Frequency' `
            -SampleInterval 1 -MaxSamples 60
```

Xung thực = `MaxClockSpeed × % Processor Performance / 100`.

Song song, một job riêng đọc `Win32_Processor.CurrentClockSpeed` mỗi giây **cùng
thời điểm**, để so trực tiếp hai nguồn trên cùng một khoảng thời gian.

Dữ liệu thô:
- `cpu_verify_perfcounter_2026-09-05.csv` — 60 mẫu perf counter
- `cpu_verify_wmi_2026-09-05.csv` — 29 mẫu WMI cùng lúc

---

## 2. Kết quả

### 2.1 Xung nhịp thực theo perf counter

| pha | xung p50 | min | max | `% Processor Utility` p50 |
|---|---|---|---|---|
| nghỉ (0–14 s) | **3711 MHz** | 3365 | 3865 | 27.4% |
| tải 1 core (15–44 s) | **3362 MHz** | 3218 | 3745 | 38.5% |
| nghỉ (45–59 s) | **3720 MHz** | 3475 | 3902 | 28.1% |

Toàn bộ 60 mẫu: min 3218, max 3902, trung bình 3537 MHz.

`% Processor Performance` nằm trong khoảng **108–130%**, tức CPU chạy **trên** base
clock 2995 MHz suốt phép đo — turbo boost hoạt động bình thường. Xung nhịp hạ nhẹ
khi có tải (3711 → 3362) đúng như hành vi turbo thông thường: turbo đơn nhân lúc
rảnh cao hơn turbo khi tải kéo dài. Đây là dao động, không phải trần cứng.

Tải có hiệu lực thật: `% Processor Utility` tăng từ 27.4% lên 38.5% (+11 điểm ≈ 1
trong 8 luồng), rồi trở về 28.1% sau khi thả.

### 2.2 WMI đo cùng lúc

| nguồn | n | min | max | p50 |
|---|---|---|---|---|
| perf counter (xung thực) | 60 | 3218 | 3902 | ~3537 |
| `Win32_Processor.CurrentClockSpeed` | 29 | **1198** | **1198** | **1198** |

**0/29 mẫu WMI khác 1198.** Hai nguồn đo cùng một CPU, cùng một phút, lệch nhau
gần 3×.

### 2.3 Vì sao WMI ra đúng 1198

Counter `% of Maximum Frequency` đứng yên ở **40** trong cả 60 mẫu. Và:

```
2995 MHz × 40 / 100 = 1198.0 MHz
```

Khớp chính xác tới từng số. `CurrentClockSpeed` chỉ đang phản chiếu counter legacy
`% of Maximum Frequency`, chứ không đọc tần số thật. Trên CPU Intel đời mới dùng
Speed Shift / HWP, hệ điều hành không còn điều khiển p-state trực tiếp nữa, nên
counter legacy này trả về một giá trị cố định vô nghĩa. `% Processor Performance`
mới là counter phản ánh tần số thực.

### 2.4 Đối chiếu cấu hình nguồn

| mục | giá trị | |
|---|---|---|
| Power scheme | `381b4222-…` Balanced | |
| **Maximum processor state** | **AC = 100%, DC = 100%** (`0x64`) | không có trần |
| Minimum processor state | AC = 5%, DC = 5% | mặc định |
| `Win32_Battery.BatteryStatus` | 2 = đang chạy điện lưới | |
| `PowerOnline` / `Charging` / `Discharging` | True / False / False | cắm sạc, pin đầy |
| `DischargeRate` | 0 mW | không xả pin |
| Pin | 100% | |

Không có giới hạn nào ở tầng power plan, và máy không hề thiếu điện.

### 2.5 Mục chưa chạy được

`powercfg /energy /duration 30` **cần quyền administrator**, phiên này không có:

```
This command requires administrator privileges and must be executed from an elevated command prompt.
```

Nếu muốn chạy để soi mục "Platform Power Management" / "Processor Idle/Throttle",
mở PowerShell với quyền admin rồi:

```powershell
powercfg /energy /duration 30 /output "$env:USERPROFILE\energy-report.html"
```

Ba bằng chứng ở 2.1–2.4 đã đủ để kết luận, nên mục này không đổi được kết quả.

---

## 3. Kết luận và hệ quả

**Phương án (a).** Xung nhịp thực dao động 3218–3902 MHz, tức **trên base clock**,
turbo hoạt động, không có trần tần số, không thiếu nguồn. Số 1198 MHz là hiện vật
của một counter legacy.

Hệ quả:

1. **Baseline v1 hợp lệ.** Nó chạy trên CPU ở tốc độ đầy đủ. Cảnh báo "toàn bộ
   baseline đang đo một máy chạy ở 40% tốc độ" trong báo cáo v1 là **sai** — cần
   bỏ khỏi bất kỳ bản thảo nào đã trích nó.
2. **Không cần chạy v2** vì lý do xung nhịp. Việc đổi power plan sang High
   performance cũng không còn là điều kiện tiên quyết, vì Maximum processor state
   vốn đã là 100% và CPU vốn đã turbo.
3. **RTF 1.45 của Kokoro là số thật**, đo ở xung nhịp đầy đủ. Nghĩa là Kokoro
   thật sự tổng hợp chậm hơn thời gian thực trên con CPU này, và giả thuyết về
   `tts ≈ 3 s` (Kokoro không stream trong câu, khác VieNeu) vẫn đứng vững — thậm
   chí đứng vững hơn, vì không còn cách đổ lỗi cho throttle nữa.
4. **File `cpu_clock_2026-09-05_v1_WMI-KHONG-TIN-CAY.csv`** (247 mẫu lấy trong lúc
   chạy v1) đã được đổi tên để đánh dấu: nó là dữ liệu WMI, **không dùng được** làm
   số đo tần số. Giữ lại chỉ để truy vết.

## 4. Ghi chú cho lần sau

Đo tần số CPU trên Windows thì dùng `% Processor Performance` (nhân với base clock),
đừng dùng `Win32_Processor.CurrentClockSpeed` hay `% of Maximum Frequency`. Cách
kiểm tra nhanh xem con số có đáng tin không: nếu nó bằng đúng một tỉ lệ tròn của
base clock và không nhúc nhích dù tải thay đổi, thì đó là counter legacy chứ không
phải phép đo.
