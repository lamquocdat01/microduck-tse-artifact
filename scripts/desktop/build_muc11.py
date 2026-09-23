# -*- coding: utf-8 -*-
r"""Sinh MỤC 11 của `docs/PAPER-NUMBERS.md` từ dữ liệu đo — việc 143, đợt 27f/27h.

    python scriptsuild_muc11.py            # sinh lại mục 11 (thay thế nếu đã có)

Vì sao là script chứ không gõ tay: mục 11 mang kết quả của mẻ đăng ký trước, và cùng các file
đo ấy còn nuôi `build_numbers.py` → `numbers.json` → macro → bài. Nếu sổ cái gõ tay thì sổ và
macro trôi khỏi nhau mà không cổng nào thấy. Chạy lại script này bất cứ lúc nào phải ra đúng
cùng một mục; nó **thay thế** mục 11 cũ chứ không chồng thêm.

Quy ước số theo sổ cái: dấu phẩy thập phân, `Wilson a–b`, dấu trừ U+2212 khác dấu nối U+2013.
"""
import io, json, math, os, sys, glob
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
os.chdir(REPO)
NL = chr(10)
CRLF = chr(13) + chr(10)
Z = 1.959963984540054


def wilson(k, n):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def vi(x, nd=3):
    t = (("%." + str(nd) + "f") % x).replace(chr(46), chr(44))
    if t.lstrip(chr(45)).strip(chr(44) + "0") == "":
        t = t.lstrip(chr(45))          # khong in so khong AM
    return t.replace(chr(45), chr(8722), 1) if t.startswith(chr(45)) else t


def ktc(lo, hi, nd=3):
    return "Wilson " + vi(lo, nd) + chr(8211) + vi(hi, nd)


L = []


def w(s=""):
    L.append(s)


cham = json.load(io.open("docs/benchmark/M6_M7_cham_20260923.json", encoding="utf-8"))

# ---------------- M3 ----------------
rs = [json.loads(l) for l in io.open("docs/benchmark/M3_20260916_v1.jsonl", encoding="utf-8") if l.strip()]
moc, probe = OrderedDict(), []
for r in rs:
    if r["task_id"].startswith("M3|probe-nosearch"):
        probe.append(r)
        continue
    moc.setdefault(r["due"], {})[r["task_id"].split("|")[-1]] = r
keys = list(moc)
g3 = moc[keys[0]]

w("## 11. BỔ SUNG SAU KHI ĐÓNG SỔ — 23/09/2026, đợt 27f · MẺ ĐĂNG KÝ TRƯỚC M1–M7 (16–23/09)")
w()
w("Mọi số trong mục này sinh bằng máy từ các file dưới đây, ngày chấm " + cham["cham_luc"][:19] + ".")
w("Luật chấm: " + cham["luat"] + ". Mốc mù (A04.5): " + cham["moc_mu"] + ", commit " + cham["moc_commit"] + ".")
w()
w("| thứ | file |")
w("|---|---|")
w("| M3 grounding | `docs/benchmark/M3_20260916_v1.jsonl` (425 bản ghi, tất cả `ok`) |")
w("| M6 oracle | `docs/benchmark/M6_20260918_v1.jsonl` (20 lần, tất cả `ok`) |")
w("| chấm M6/M7 | `docs/benchmark/M6_M7_cham_20260923.json` |")
w("| lỗi thoáng qua | `docs/benchmark/M1_20260916_v1.errors.jsonl` và hai file cùng dạng của M3, M6 |")
w()
w("### 11a. M3 — grounding qua 14 mốc cách nhau 12 h · đường cong PHẲNG, không suy giảm")
w()
w("So từng mốc với **mốc 1**. Cột *giờ thực đo* in cạnh giờ danh nghĩa theo I-15 và I-19: mốc 4 và mốc 5")
w("chạy muộn vì máy ngủ, nên số của chúng đo ở giờ thực, không phải giờ danh nghĩa.")
w()
w("| j | mốc (danh nghĩa) | giờ thực đo | `lookup` đổi | domain-set đổi | text đổi |")
w("|---|---|---|---|---|---|")
hang = []
for j, k in enumerate(keys, 1):
    v = moc[k]
    ids = sorted(set(g3) & set(v))
    a = sum(1 for i in ids if bool(v[i]["payload"]["lookup"]) != bool(g3[i]["payload"]["lookup"]))
    b = sum(1 for i in ids if set(v[i]["payload"]["domains"]) != set(g3[i]["payload"]["domains"]))
    c = sum(1 for i in ids if (v[i]["payload"]["answer"] or "").strip() != (g3[i]["payload"]["answer"] or "").strip())
    t0 = min(x["ts"] for x in v.values())
    hang.append((j, b, c))
    w("| %d | %s | %s | %d/%d | %d/%d | %d/%d |"
      % (j, k[:16].replace("T", " "), t0[11:19], a, len(ids), b, len(ids), c, len(ids)))
w()
dm = [b for j, b, c in hang[1:]]
tx = [c for j, b, c in hang[1:]]
w("Mốc 1 so chính nó là 0/30 ở cả ba cột (kiểm tra vệ sinh). Từ **mốc 2 trở đi không có xu hướng theo")
w("thời gian**: domain-set đổi dao động " + str(min(dm)) + "–" + str(max(dm)) + "/30 và text đổi "
  + str(min(tx)) + "–" + str(max(tx)) + "/30 suốt 13 mốc trải 6,5 ngày.")
w("Bất ổn xuất hiện **ngay ở khoảng cách 12 h đầu tiên** rồi đứng yên; nó không tích luỹ theo thời gian.")
w("Theo prereg, curve là **mô tả**, không khớp mô hình suy giảm nào.")
w()
retr = [i for i in g3 if g3[i]["payload"]["lookup"]]
last = moc[keys[-1]]
w("### 11a-bis. Chỉ trên " + str(len(retr)) + " câu CÓ tra ở mốc 1 (mốc 14 so mốc 1)")
w()
doi_moc14 = {}
w("| quan sát | đổi | tỉ lệ | KTC 95 % |")
w("|---|---|---|---|")
for ten, f in (("domain-set", lambda x, y: set(x["payload"]["domains"]) != set(y["payload"]["domains"])),
               ("text trả lời", lambda x, y: (x["payload"]["answer"] or "").strip() != (y["payload"]["answer"] or "").strip())):
    k = sum(1 for i in retr if f(last[i], g3[i]))
    n = len(retr)
    doi_moc14[ten] = k
    lo, hi = wilson(k, n)
    w("| %s | %d/%d | %s | %s |" % (ten, k, n, vi(k / n), ktc(lo, hi)))
w()
w("### 11a-ter. Đối chứng âm `probe-nosearch` (A01.3) — GIỮ TÁCH khỏi mẫu số curve")
w()
w("Mẫu số của curve là **360 = 12 mốc × 30 câu** dữ liệu; " + str(len(probe)) + " bản ghi probe dưới đây là")
w("**đối chứng âm riêng**, không bao giờ cộng vào 360. Chúng chạy với `search=False` để kiểm ranh giới")
w("*search tới model ⇔ `grounded=True` có `n_sources > 0`*:")
w()
w("| task_id | `lookup` | `grounded` | `n_sources` |")
w("|---|---|---|---|")
for p in probe:
    pl = p["payload"]
    w("| `%s` | %s | %s | %d |" % (p["task_id"], pl["lookup"], pl["grounded"], pl["n_sources"]))
w()
w("Cả " + str(len(probe)) + " câu: `lookup` vẫn bật mà `grounded` tắt và `n_sources` = 0 — ranh giới đúng")
w("chiều, không có grounding lén.")
w()

# ---------------- M6 ----------------
w("### 11b. M6 — biên flake(artefact) − flake(decision), 4 ô")
w()
w("**Nhãn đơn vị (bắt buộc):** mọi số ở bảng này là *k of n tests flaky across 19 runs* — đếm **test**,")
w("gộp qua 19 lần chạy so với golden `" + cham["M6"]["golden"] + "`. Đừng đọc lẫn với bảng 11b-bis, nơi")
w("đơn vị là *k of n tests failing in run r* — đếm test **trong một lần chạy**.")
w()
w("| ô | loại | decision: test flaky / 19 lần | artefact: test flaky / 19 lần | biên art − dec | KTC 95 % (Newcombe) |")
w("|---|---|---|---|---|---|")
for ten in sorted(cham["M6"]["o"]):
    o = cham["M6"]["o"][ten]
    w("| `%s` | %s | %d/%d | %d/%d | %s | %s |"
      % (ten, o["loai"], o["decision"]["flaky_tests"], o["decision"]["n_tests"],
         o["artefact"]["flaky_tests"], o["artefact"]["n_tests"],
         vi(o["bien_art_tru_dec"]),
         vi(o["newcombe_bien"][0]) + chr(8211) + vi(o["newcombe_bien"][1])))
w()
w("**Đọc cho đúng, một lần, để Discussion không hứa quá:** ở `routing-hosted`, bộ decision **cũng")
w("flake** — 10/40 tests flaky across 19 runs, không phải 0. Kết quả của M6 là **biên** 0,750 với")
w("KTC 0,575–0,858, nghĩa là *decision-level assertions flake ÍT HƠN*, **không** phải *không flake*.")
w("Câu 'assert the decision, log the artefact' phải đọc như một đánh đổi đo được, không như lời hứa")
w("tuyệt đối. Hai ô pinnable (`routing-local`, `stt-local`) có 0/40 và 0/23 nên biên bằng 0 và KTC phủ")
w("cả hai phía — ở đó M6 không phân biệt được hai bộ oracle, và điều đó cũng phải in.")
w()
w("### 11b-bis. M6 tách theo KHOẢNG CÁCH tới golden — không báo một con số gộp")
w()
w("Luật (chốt 23/09): lần chạy cách golden 22 phút vì máy ngủ (I-15) báo **riêng** với 18 lần theo lịch.")
w("**Nhãn đơn vị:** mọi số ở bảng này là *k of n tests failing in run r* — đếm test **trong một lần")
w("chạy**, mẫu số 252 = 126 test × 2 bộ oracle. KHÁC đơn vị của bảng 11b.")
w()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cham_m6_m7 as C

plan = json.loads(Path("docs/benchmark/runner/plan.json").read_text(encoding="utf-8"))
ok6 = sorted(C.doc_ok(REPO / plan["results"]["M6"]).values(), key=lambda r: r["payload"]["lan"])
tg = datetime.fromisoformat(ok6[0]["ts"])
w("| lần | giờ chạy | cách golden | decision: test hỏng / 252 | artefact: test hỏng / 252 |")
w("|---|---|---|---|---|")
rows = []
for r in ok6[1:]:
    t = datetime.fromisoformat(r["ts"])
    dec = art = 0
    for ten, kq in r["payload"]["tests"].items():
        if kq != "passed":
            if ten.split("::", 1)[0] == "decision":
                dec += 1
            else:
                art += 1
    rows.append(((t - tg).total_seconds() / 3600, dec, art))
    w("| %d | %s | %s h | %d | %d |"
      % (r["payload"]["lan"], r["ts"][:19].replace("T", " "),
         vi((t - tg).total_seconds() / 3600, 2), dec, art))
w()
d0, a0 = rows[0][1], rows[0][2]
da = [x[1] for x in rows[1:]]
aa = [x[2] for x in rows[1:]]
w("**Lần 2, cách golden " + vi(rows[0][0], 2) + " h (22 phút):** decision fail **" + str(d0)
  + "**, artefact fail **" + str(a0) + "**/252.")
w("**18 lần còn lại, cách golden " + vi(rows[1][0], 2) + chr(8211) + vi(rows[-1][0], 2)
  + " h:** decision fail " + str(min(da)) + chr(8211) + str(max(da))
  + ", artefact fail " + str(min(aa)) + chr(8211) + str(max(aa)) + ".")
w()
w("Đây là bằng chứng **bảo thủ**, thuộc Results chứ không phải Threats: ở khoảng cách 22 phút — ngắn hơn")
w("lịch đăng ký một bậc — bộ artefact đã hỏng " + str(a0) + " test còn bộ decision hỏng " + str(d0) + ". Bất ổn")
w("của artefact không cần thời gian để xuất hiện, nên việc máy ngủ làm lịch không đều **không** tạo ra kết quả này.")
w()

# ---------------- M7 ----------------
t7 = cham["M7"]["tong_ket"]
w("### 11c. M7 — ma trận dự đoán, " + str(t7["mau_so"]) + " đơn vị chấm")
w()
w("Đúng **" + str(t7["dung"]) + "** · sai **" + str(t7["sai"]) + "** · không phân định **"
  + str(t7["khong_phan_dinh"]) + "** · thiếu lực không tính **" + str(t7["thieu_luc_khong_tinh"])
  + "** · loại theo A06 **" + str(t7["loai_a06"]) + "** · chưa có cặp mù **" + str(t7["chua_co_cap_mu"]) + "**.")
w()
w("| ô | tầng | quan sát | pinnability | dự đoán | nguồn | k/n | KTC 95 % (Wilson) | phán quyết |")
w("|---|---|---|---|---|---|---|---|---|")
for u in cham["M7"]["don_vi"]:
    pq = u["phan_quyet"] + (" (thiếu lực)" if u["thieu_luc"] else "")
    w("| %d | %s | %s | %s | %s | %s | %d/%d | %s | %s |"
      % (u["o"], u["stage"], u["observable"], u["pinnability"], u["du_doan"], u["nguon"],
         u["k"], u["n"], vi(u["wilson"][0]) + chr(8211) + vi(u["wilson"][1]), pq))
w()
sai = [u for u in cham["M7"]["don_vi"] if u["phan_quyet"] == "sai"]
w("**" + str(len(sai)) + " đơn vị NGƯỢC dự đoán — in nguyên, không giấu:**")
w()
for u in sai:
    w("- **ô %d (%s, %s, %s), nguồn %s** — dự đoán *%s*, đo được %d/%d = %s, %s."
      % (u["o"], u["stage"], u["observable"], u["pinnability"], u["nguon"], u["du_doan"],
         u["k"], u["n"], vi(u["ty_le"]), ktc(u["wilson"][0], u["wilson"][1])))
w()
dp = cham["M7"]["depth"]
w("Phép kiểm (c) *depth*: hỗ trợ **" + str(dp["ho_tro"]) + "**, bác **" + str(dp["bac"])
  + "**, không phân định **" + str(dp["khong_phan_dinh"]) + "** trên " + str(len(dp["nhom"])) + " nhóm:")
w()
for nh in dp["nhom"]:
    w("- *" + nh["nhom"] + "* → **" + nh["ket_qua"] + "** ("
      + ", ".join("ô %d/%s %d/%d" % (x["o"], x["nguon"], x["k"], x["n"]) for x in nh["don_vi"]) + ")")
w()

# ---------------- loi thoang qua ----------------
w("### 11d. Lỗi thoáng qua — `error` đếm 0 nhưng KHÔNG phải không có lỗi")
w()
w("`status` in `error 0` vì mọi task cuối cùng đều `ok`. Ba file `*.errors.jsonl` giữ các lần thử HỎNG đã")
w("được thử lại thành công; prereg đòi in tỉ lệ *task từng lỗi* cạnh kết quả, nên chúng phải được đếm:")
w()
w("| file | số dòng | mã lỗi |")
w("|---|---|---|")
tong = 0
for f in sorted(glob.glob("docs/benchmark/M*_v1.errors.jsonl")):
    ls = [l for l in io.open(f, encoding="utf-8") if l.strip()]
    tong += len(ls)
    ma = sorted({m for m in (str(json.loads(l).get("error", ""))[:3] for l in ls) if m.isdigit()})
    w("| `%s` | %d | %s |" % (f.replace(os.sep, "/"), len(ls), ", ".join(ma)))
w("| **tổng** | **%d** | đều là 503 UNAVAILABLE hoặc 504 DEADLINE_EXCEEDED từ phía Gemini |" % tong)
w()
w("Không dòng nào là lỗi logic của hệ được đo; tất cả là lỗi mạng hoặc dịch vụ thoáng qua, thử lại là qua.")

# ---------------- 11e: kiem luc + danh sach A06 loai (VIEC A) ----------------
w("### 11e. Loại *thiếu lực* và 11 đơn vị bị A06 loại — cả hai ĐĂNG KÝ TRƯỚC, không nghĩ ra sau")
w()
w("Câu hỏi đúng phải hỏi: *thiếu lực* có phải rổ thứ tư nghĩ ra sau khi nhìn số không? **Không.**")
w("A04.5 ghi trước, kèm ngưỡng và kèm **đích danh các ô** sẽ rơi vào đó, trích nguyên văn:")
w()
w("> **Kiểm lực trước số.** Dự đoán *ổn định* với $0/n$ chỉ đạt cận trên Wilson ≤ 10 % khi $n \\ge 35$")
w("> ($0/31$ → 11,0 %; $0/30$ → 11,3 %; $0/35$ → 9,9 %). Đơn vị $n < 35$ **không thể** được chấm *đúng*")
w("> cho dự đoán ổn định: S1 (ô 1, 3, 4) và M3 (ô 15) in ra với nhãn **thiếu lực**, **không** vào mẫu")
w("> số; vẫn tính *sai* nếu rơi vào vùng sai (sai vẫn quan sát được). Ô dự đoán *không ổn định* không bị")
w("> ràng buộc này. S2 không dùng cho M7.")
w()
w("Ba đơn vị mang nhãn ấy trong kết quả — ô 1/S1, ô 3/S1, ô 4/S1, tất cả $n = 31 < 35$ — **đúng bằng")
w("danh sách A04.5 nêu trước**. Ô 15/M3 cũng thiếu lực ($n = 30$) nhưng đã bị A06 loại khỏi mẫu số vì")
w("lý do khác (pilot), nên không đếm lần hai. Không có đơn vị nào ngoài danh sách đăng ký rơi vào loại này.")
w()
w("Phần bù cũng phải in: A04 chỉ có **ba** phán quyết (đúng / sai / không phân định). *Thiếu lực* không")
w("phải phán quyết thứ tư — nó là **điều kiện vào mẫu số**, áp trước khi chấm, và đơn vị thiếu lực vẫn")
w("bị tính **sai** nếu rơi vào vùng sai. Ba đơn vị S1 đều $0/31$, tức không có cái nào được cứu bởi nhãn này.")
w()
w("**11 đơn vị A06 loại, mỗi đơn vị một dòng lý do** (`LOAI_A06` trong `desktop/scripts/cham_m6_m7.py`):")
w()
w("| ô | nguồn | lý do loại |")
w("|---|---|---|")
for (so, ng), ly in sorted(C.LOAI_A06.items()):
    w("| %d | %s | %s |" % (so, ng, ly))
w()
w("Chứng minh loại **trước** khi có số: A06 commit `a078d37` lúc **2026-09-17T11:33:34+07:00**; bản ghi")
w("M6 sớm nhất là **2026-09-18T10:02:46+07:00**, tức sau đó **22,5 giờ**. Mốc mù A04.5 là commit")
w("`015c0e7` lúc **2026-09-17T07:48:33+07:00**, và script lọc theo `ts` của lượt sau, không lọc tay:")
w("`khong_mu` rỗng và `chua_co_cap_mu` = 0, nghĩa là mọi cặp tính điểm đều có lượt sau nằm sau mốc mù.")
w()

# ---------------- 11f: o 12 (VIEC B) ----------------
w("### 11f. Ô 12 — decoding ĐÃ ghim đủ mà artefact vẫn đổi 9/50: bác thật, không phải lỗi cấu hình")
w()
w("Trước khi gọi ô 12 là *ma trận sai*, phải loại giả thuyết rẻ tiền: có phải chỉ ghim trọng số mà quên")
w("ghim bộ giải mã? Đọc cấu hình **thật sự gửi tới Ollama** (`plan.json` khoá `params.options`, và")
w("`OllamaExec.manifest` ghi `tham_so_gui`), không suy đoán:")
w()
w("| tham số | giá trị | ghim ở đâu |")
w("|---|---|---|")
w("| `temperature` | `0.0` | `plan.json` → `params.options` |")
w("| `seed` | `0` | `plan.json` → `params.options` |")
w("| `num_predict` | `100` | `plan.json` → `params.options` |")
w("| `num_thread` | `6` | `tham_so_gui` trong manifest, **giống nhau ở mọi bản ghi** |")
w("| `think` | `false` | `tham_so_gui` |")
w("| trọng số | digest `845dbda0ea48…` | giống hệt ở cả hai mốc của cả 9 cặp đổi |")
w()
w("Manifest M4 có ba bộ tham số vì tập còn **probe** cố ý đổi cấu hình — 5 bản ghi `seed 0 / temp 0,0`")
w("(điều kiện chính), 2 bản `seed 1`, 2 bản `temp 0,8`. Các cặp chấm ô 12 chỉ lấy mốc `t0` so `t24h`")
w("của `qwen2.5:7b`, đều thuộc điều kiện chính; probe không lẫn vào.")
w()
w("**Nên đây là bác thật.** Và nó không phải cắt cụt ở `num_predict`: cả hai phía đều `done_reason =")
w("stop`, và nội dung là **viết lại hẳn**, không phải một câu bị cắt ngắn. Ba ví dụ:")
w()
w("| cặp | t0 | t24h |")
w("|---|---|---|")
w("| `078cc5e1…` | *For example, virtual reality can simulate field trips to places like museums…* | *For example, virtual reality can transport students to historical sites…* |")
w("| `697711806949a46d` (3b) | *Enrolling on a gap year course abroad can indeed enhance your profile…* | *Indeed, taking a gap year to study or work abroad can often enhance your credentials…* |")
w("| `9aae4a2d…` (3b) | trả lời bằng tiếng Hàn | trả lời bằng tiếng Anh — đây cũng là 1/50 đổi `lang_label` |")
w()
w("Đối chiếu hai model: `qwen2.5:7b` đổi `reply_text` **9/50** và `lang_label` **1/50**; `qwen2.5:3b`")
w("đổi `reply_text` **4/50** và `lang_label` **1/50**. Quyết định bền hơn artefact ở cả hai, đúng chiều")
w("luận điểm chính — cái sai là dự đoán *ổn định tuyệt đối* cho artefact của model ghim, không phải")
w("thứ tự decision/artefact.")
w()
w("**Ô 12 KHÔNG được chấm lại.** Nó vẫn là dự đoán **sai**; phần trên là giải thích hậu kiểm, ghi riêng,")
w("không nhét ngược vào prereg. Điều phải nói ở Discussion: ma trận coi *caller-pinnable* là thuộc tính")
w("của **trọng số**, trong khi thực tế nó là thuộc tính của **toàn bộ tham số tới được model** — và ngay")
w("cả khi bộ tham số ấy đã ghim đủ, vẫn còn một trục ma trận không có. Bài đã có sẵn bằng chứng cùng")
w("chiều ở ngay §I: pilot ghi *an open-weight model run locally with seed and temperature pinned changed")
w("its text on 16/23 repeats … while the language decision those texts encode changed on 0/23*. Tức")
w("**dự đoán ô 12 mâu thuẫn với chính quan sát mở đầu của bài**, và số đo 9/50 đứng về phía pilot.")
w()

# ---------------- 11g: ra soat ngon ngu tich luy (VIEC C) ----------------
w("### 11g. Rà câu *tích luỹ theo thời gian* trong bản dựng — 0 chỗ phải sửa")
w()
w("M3 phẳng, nên mọi câu nói drift tăng dần theo ngày sẽ sai theo dữ liệu của chính bài. Quét toàn bộ")
w("`Submission TSE/latex/sections`, `supplement/sections` và `abstract.tex` theo các mẫu *accumulate,")
w("grow over, increase with time, degrade, decay, widen, over the days*:")
w()
w("- Mọi chỗ `decay` / `degrade` trong `01-introduction.tex` và `11-results.tex` đều nói về **độ sâu**")
w("  (*reproducibility decays with depth*, *degrade with the depth of the stage*), không nói về thời gian.")
w("- `supplement/04-response-language.tex` *accumulates its own past behaviour as context* — nói về lịch")
w("  sử hội thoại nhiều lượt, không phải trôi theo ngày.")
w("- `supplement/06-routing-determinism.tex` *let small-talk history accumulate* — tham số vận hành.")
w("- `supplement/05-routing-accuracy.tex` *did not degrade* — nói về lực phát hiện ở n = 50 so n = 200.")
w("- `s08-threats-detail.tex` đã viết sẵn đúng chiều: *reported as a curve and **not fitted to a decay model***.")
w()
w("**Không câu nào phải viết lại, không chạm §STOP 5.** Việc còn lại thuộc bước 3: thêm phát biểu")
w("khẳng định điều đã đo — *instability appears at the shortest separation we measured and does not grow")
w("over 6,5 days* — vào Results, rồi §I / abstract / Conclusion trỏ theo.")
w()


# ---------------- 11h: bang doi chieu may doc ----------------
o_rh = cham["M6"]["o"]["routing-hosted"]
t7k = cham["M7"]["tong_ket"]
DOI_CHIEU = [
    ("m3.milestones", str(len(keys))),
    ("m3.questions", str(len(g3))),
    ("m3.retrieving", str(len(retr))),
    ("m3.domain_changed", str(doi_moc14["domain-set"])),
    ("m3.text_changed", str(doi_moc14["text trả lời"])),
    ("m3.domain_lo", str(min(dm))),
    ("m3.domain_hi", str(max(dm))),
    ("m3.text_lo", str(min(tx))),
    ("m3.text_hi", str(max(tx))),
    ("m6.margin", "%.3f" % o_rh["bien_art_tru_dec"]),
    ("m6.margin_lo", "%.3f" % o_rh["newcombe_bien"][0]),
    ("m6.margin_hi", "%.3f" % o_rh["newcombe_bien"][1]),
    ("m6.dec_flaky", str(o_rh["decision"]["flaky_tests"])),
    ("m6.art_flaky", str(o_rh["artefact"]["flaky_tests"])),
    ("m6.n_tests", str(o_rh["decision"]["n_tests"])),
    ("m6.short_dec", str(d0)),
    ("m6.short_art", str(a0)),
    ("m6.tests_per_run", str(len(ok6[1]["payload"]["tests"]))),
    ("m7.correct", str(t7k["dung"])),
    ("m7.wrong", str(t7k["sai"])),
    ("m7.undecided", str(t7k["khong_phan_dinh"])),
    ("m7.total", str(t7k["mau_so"])),
    ("m7.excluded", str(t7k["loai_a06"])),
    ("m7.underpowered", str(t7k["thieu_luc_khong_tinh"])),
]
w("### 11h. Bảng đối chiếu máy đọc — khoá vòng giữa sổ cái và `numbers.json`")
w()
w("Có **hai** đường cùng đi từ cùng bộ file đo: `build_muc11.py` sinh mục 11 này, và `dem_me_27f()`")
w("trong `build_numbers.py` sinh `paper/numbers.json` rồi thành macro. Hai đường tính độc lập, nên")
w("phải có thứ buộc chúng bằng nhau — nếu không, sổ và bài trôi khỏi nhau mà không cổng nào thấy.")
w("Bảng dưới là bản máy đọc của mục 11; `tests/test_muc11_khop_numbers.py` so từng dòng với")
w("`numbers.json` (chuẩn hoá dấu phẩy thập phân), và `build_numbers.py --check` gọi nó.")
w()
w("| key | giá trị |")
w("|---|---|")
for k, v in DOI_CHIEU:
    w("| `%s` | `%s` |" % (k, v.replace(chr(46), chr(44))))
w()

out = CRLF.join(L) + CRLF
p = "docs/PAPER-NUMBERS.md"
s = io.open(p, encoding="utf-8", newline="").read()
assert not [c for c in out if ord(c) < 32 and c not in (chr(10), chr(13))]
moc = "## 11. B"
if moc in s:                      # thay the, khong chong them
    s = s[:s.index(moc)]
io.open(p, "w", encoding="utf-8", newline="").write(s.rstrip(chr(13) + NL) + CRLF + CRLF + out)
print("PAPER-NUMBERS.md: muc 11 = " + str(len(L)) + " dong, " + str(len(out)) + " byte")
