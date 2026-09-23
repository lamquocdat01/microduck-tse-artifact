r"""Sinh `paper/numbers.json` từ `docs/PAPER-NUMBERS.md` — luật C6 của đợt 11.

    python scripts\build_numbers.py            # sinh lại
    python scripts\build_numbers.py --check    # chỉ kiểm, khác thì trả mã thoát 1

## Vì sao không chép tay

Bài này **lập luận về tính tái lập**. Một con số chép tay lệch một chữ số trong một bài
về tái lập là tự bắn vào chân. Và dự án đã bắt được **năm giả tượng đo lường** trong
chính nó — không có lý do nào để tin rằng bàn phím an toàn hơn.

## Cái file này KHÔNG làm

Nó **không** tự phân tích văn xuôi tiếng Việt của sổ. Sổ là tài liệu người đọc, không
phải cơ sở dữ liệu; đoán cấu trúc từ văn xuôi là thêm một tầng có thể sai lặng lẽ.

Thay vào đó mỗi con số vào bài được khai **tường minh một lần** ở `SO` bên dưới, kèm
đủ năm cột, và `--check` đối chiếu lại với sổ bằng cách **tìm chuỗi**: giá trị nào khai
ở đây mà không xuất hiện nguyên văn trong `PAPER-NUMBERS.md` thì báo lỗi. Vậy sổ vẫn là
nguồn sự thật, còn file này là bản máy đọc được, và hai bên không trôi khỏi nhau.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import enable_utf8_console  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs" / "PAPER-NUMBERS.md"
OUT = REPO / "paper" / "numbers.json"

B = "docs/benchmark/"
BL = "docs/baseline/"

# id: (giá trị hiển thị, n, KTC, nguồn, quy ước, chuỗi phải có trong sổ)
SO: dict[str, dict] = {
    # ---- tầng phần cứng ----
    "hw.rx_first.p50.batch1": dict(value="133,4 ms", n="47 lượt", ci=None,
        src=B + "device_floor_20260906_v1.jsonl",
        conv="phân vị gần nhất; lát cắt: 57 bản ghi đầu, giữ lượt có t_tx_first",
        probe="133,4"),
    "hw.rx_first.p50.batch2": dict(value="131,6 ms", n="59 lượt", ci=None,
        src=B + "device_floor_20260909_v1.jsonl",
        conv="phân vị gần nhất; lát cắt: trọn phiên 1788966181-b850", probe="131,6"),
    "hw.rtt.p50.batch1": dict(value="32,4 ms", n="47 lượt", ci=None,
        src=B + "device_floor_20260906_v1.jsonl", conv="phân vị gần nhất", probe="32,4"),
    "hw.rtt.p50.batch2": dict(value="4,65 ms — hằng số trong phiên", n="59 lượt", ci=None,
        src=B + "device_floor_20260909_v1.jsonl", conv="phân vị gần nhất", probe="4,65"),
    "hw.group_gap": dict(value="1,1 ms (132,2 so với 131,1)", n="47 vs 12 lượt", ci=None,
        src=B + "device_floor_20260909_v1.jsonl",
        conv="lát cắt thay thế cho 2,3 ms; p50 y hệt ở cả hai", probe="1,1 ms"),

    # ---- sàn thiết bị, cả hai chặng (đợt 13, §1d) ----
    # Ba dòng này là thứ Bảng 3 chờ từ đầu. `m` (độ trễ đường thu laptop) vào chặng lên
    # với dấu âm và chặng xuống với dấu dương, nên nó TRIỆT TIÊU ở dòng tổng — và đó là
    # lý do dòng tổng mới là dòng đem đi cộng, không phải hai dòng kia.
    "hw.uplink": dict(value="p50 177,8 / p95 334,9 ms", n="22 click", ci=None,
        src=B + "devout_20260910_p1.json",
        conv="phân vị gần nhất; BỘ TẤT CẢ (n=22). Bỏ cụm cao thì p50 164,0 / p95 207,2 "
             "(n=19) — phải nói rõ đang trích bộ nào. Số cõng −m.",
        probe="177,8"),
    "hw.downlink": dict(value="p50 319,0 / p95 352,0 ms", n="18 lượt", ci=None,
        src=B + "devout_20260910_p2.json",
        conv="phân vị gần nhất; gồm cả một điểm rời 1 466 ms. Trung bình 319,5 ± 22,2 "
             "trên 17 lượt sau khi bỏ điểm ấy. Số cõng +m.",
        probe="319,0"),
    "hw.device_floor": dict(value="p50 525,9 / p95 653,9 ms", n="16 lượt", ci=None,
        src=B + "devout_20260910_p3.json",
        conv="phân vị gần nhất; bỏ điểm rời. m TỰ TRIỆT TIÊU nên dòng này không phụ "
             "thuộc con số 20,0 ms mà driver khai báo.",
        probe="525,9"),
    "hw.rx_first.p50.batch3": dict(value="130,3 ms", n="25 Turn", ci=None,
        src=B + "device_floor_20260910_v1.jsonl",
        conv="phân vị gần nhất; trọn lát cắt ba mẻ 10/09", probe="130,3"),
    "hw.marker_artifact": dict(value="319,0 so với 875,9 ms — chênh 2,7 lần", n="18 lượt",
        ci=None, src=B + "devout_20260910_p1.json",
        conv="CÙNG dữ liệu, cùng lượt, chỉ khác dụng cụ chấm mốc: lọc phối hợp so với "
             "ngưỡng+thời gian giữ. Giả tượng đo lường thứ sáu.",
        probe="875,9"),

    # ---- tầng STT ----
    "stt.det.local": dict(value="1/10 → 0/10 câu bất ổn", n="10 câu × 3 vòng",
        ci="Wilson 0,018–0,404 → 0,000–0,278",
        src=B + "stt_determinism_20260910_v2.jsonl",
        conv="so transcript nguyên văn; lát cắt: cả 3 vòng", probe="1/10 → 0/10"),
    "stt.p95.base": dict(value="2 506,9 → 1 494,3 ms = −40,4 %", n="30 / 30", ci=None,
        src=B + "stt_determinism_20260910_v2.jsonl",
        conv="phân vị gần nhất; lát cắt: cả 3 vòng", probe="−40,4 %"),
    "stt.hosted.day": dict(value="5/31 = 0,161", n="31", ci="Wilson 0,071–0,326",
        src=B + "stt_rescore_20260906_v3_fixed.json × " + B + "stt_rescore_20260907_v4_owner.json",
        conv="so `hypothesis` nguyên văn, không chuẩn hoá; cách nhau MỘT NGÀY", probe="5/31"),
    "stt.hosted.session": dict(value="2/31 = 0,065 (thô 3/31)", n="31",
        ci="Wilson 0,018–0,207",
        src=B + "stt_hosted_repeat_20260910_v1.jsonl",
        conv="so `hypothesis` nguyên văn; cách nhau 180 GIÂY; timeout_s = 4,0 đội thô lên 3/31",
        probe="2/31"),
    "stt.local.stable": dict(value="0/31 = 0,000", n="31", ci="Wilson 0,000–0,110",
        src=B + "stt_rescore_20260906_v3_fixed.json × " + B + "stt_rescore_20260907_v4_owner.json",
        conv="như trên; hai backend cục bộ", probe="0/31"),
    "stt.wer.hosted": dict(value="D-WER 0,3333", n="31", ci=None,
        src=B + "stt_rescore_20260906_v3_fixed.json",
        conv="D-WER (thước LỎNG NHẤT, D ≤ N ≤ O); lát cắt trọn 31", probe="0,3333"),
    "stt.wer.large_local": dict(value="D-WER 0,3684", n="31", ci=None,
        src=B + "stt_rescore_20260906_v3_fixed.json", conv="D-WER", probe="0,3684"),
    "stt.wer.small_local": dict(value="D-WER 0,7076", n="31", ci=None,
        src=B + "stt_rescore_20260906_v3_fixed.json", conv="D-WER", probe="0,7076"),
    "stt.wer.spread": dict(value="O/N/D = 0,458 / 0,415 / 0,368", n="31", ci=None,
        src=B + "stt_rescore_20260907_v4_owner.json",
        conv="ba thước; giãn O→D = 0,090 so với 0,035 giữa hai hệ", probe="0,458"),
    "stt.lang_wrong": dict(value="6/31 = 0,194", n="31", ci="Wilson 0,092–0,363",
        src=BL + "latency_desktop_realvoice_2026-09-06_v2.jsonl",
        conv="trọn phiên", probe="6/31"),

    # ---- định tuyến: độ chính xác ----
    "route.acc.all": dict(value="recall 0,720", n="50 / 50", ci="Wilson 0,583–0,825",
        src=B + "lookup_accuracy_20260909_v2.jsonl", conv="khối A", probe="0,720 (0,583–0,825)"),
    "route.acc.vi": dict(value="recall 0,920", n="25 / 25", ci="Wilson 0,750–0,978",
        src=B + "lookup_accuracy_20260909_v2.jsonl", conv="khối A, nửa vi", probe="0,920 (0,750–0,978)"),
    "route.acc.en": dict(value="recall 0,520", n="25 / 25", ci="Wilson 0,335–0,700",
        src=B + "lookup_accuracy_20260909_v2.jsonl", conv="khối A, nửa en", probe="0,520 (0,335–0,700)"),
    "route.grey.slow": dict(value="recall 0,450", n="20", ci="Wilson 0,258–0,658",
        src=B + "lookup_accuracy_20260909_v2.jsonl", conv="fact_type slow-changing", probe="0,258–0,658"),

    # ---- lưới 2×3 ----
    "grid.vi_vi": dict(value="192/200 = 0,960", n="200", ci="Wilson 0,923–0,980",
        src=B + "lookup_rule_lang_20260909_v2_b2.jsonl", conv="25 câu × 8 lần", probe="0,960 (0,923–0,980)"),
    "grid.en_vi": dict(value="174/199 = 0,874", n="199", ci="Wilson 0,821–0,913",
        src=B + "lookup_rule_lang_20260909_v2_b2.jsonl", conv="ô QUYẾT ĐỊNH", probe="0,874 (0,821–0,913)"),
    "grid.vi_en": dict(value="102/200 = 0,510", n="200", ci="Wilson 0,441–0,578",
        src=B + "lookup_rule_lang_20260910_v3.jsonl", conv="25 câu × 8 lần", probe="0,510 (0,441–0,578)"),
    "grid.en_en": dict(value="166/200 = 0,830", n="200", ci="Wilson 0,772–0,876",
        src=B + "lookup_rule_lang_20260910_v3.jsonl", conv="25 câu × 8 lần", probe="0,830 (0,772–0,876)"),
    "grid.decisive_p": dict(value="0,960 → 0,874, z = +3,105, p = 0,0019", n="200 / 199", ci=None,
        src=B + "lookup_rule_lang_20260909_v2_b2.jsonl", conv="z hai tỉ lệ", probe="0,0019"),
    "grid.J_pooled": dict(value="+0,680 / +0,702 / +0,685", n="400 / 400 mỗi bản", ci=None,
        src=B + "lookup_rule_lang_20260909_v2_b2.jsonl × " + B + "lookup_rule_lang_20260910_v3.jsonl",
        conv="gộp hai nửa", probe="+0,680"),
    "grid.gap": dict(value="chênh hai nửa 0,450 → 0,044", n="400 / 400", ci=None,
        src=B + "lookup_rule_lang_20260909_v2_b2.jsonl", conv="gộp hai nửa", probe="0,044"),

    # ---- định tuyến: tất định ----
    "det.temp0": dict(value="100/100 câu nhất quán", n="1 000 lượt",
        ci="Wilson 0,963–1,000; quy tắc ba: cận trên ≈ 0,3 %",
        src=B + "lookup_determinism_20260909_v1.jsonl", conv="10 lần mỗi câu", probe="100/100"),
    "det.temp08": dict(value="87/100; flip rate 3,30 %", n="~1 000 lượt", ci="Wilson 0,790–0,922",
        src=B + "lookup_determinism_20260909_v1.jsonl", conv="10 lần mỗi câu", probe="87/100"),
    "det.J_by_temp": dict(value="J +0,670 → +0,679", n="1 000 / 999", ci=None,
        src=B + "lookup_determinism_20260909_v1.jsonl", conv="cả hai config trong một file",
        probe="+0,670"),

    # ---- lịch sử ----
    "hist.b6b": dict(value="0,980 vs 0,820; z = +3,012; p = 0,0026", n="40 câu × 5", ci=None,
        src=B + "lookup_history_bang6_20260909_v1.jsonl × " + B + "lookup_history_neutral_am_20260909_v1_b2.jsonl",
        conv="20 fast + 20 never", probe="0,0026"),
    "hist.sweep_fp": dict(value="sai-dương 0,130 → 0,460; J 0,690 → 0,540", n="40 câu × 5", ci=None,
        src=B + "lookup_history_neutral_20260909_v1.jsonl × " + B + "lookup_history_neutral_am_20260909_v1.jsonl",
        conv="nửa dương × nửa âm", probe="0,540"),
    "hist.refusal_best": dict(value="J 0,770; precision 0,964; sai-dương 0,030", n="40 câu × 5", ci=None,
        src=B + "lookup_history_neutral_20260909_v1.jsonl × " + B + "lookup_history_neutral_am_20260909_v1.jsonl",
        conv="điểm vận hành tốt nhất — một TAI NẠN, không phải tinh chỉnh", probe="0,964"),
    "hist.ab_refusal": dict(value="A z = +2,858; B z = +3,959", n="100 mỗi ô", ci=None,
        src=B + "lookup_ab_refusal_20260909_v1.jsonl",
        conv="⚠ KHÔNG có nửa âm — chỉ dùng cho phép so A/B một biến", probe="+3,959"),

    # ---- ba cần gạt ----
    "lever.setA": dict(value="sai-dương 5,5× · J 1,05×", n="7 cấu hình", ci=None,
        src="tổng hợp ba mẻ — xem PAPER-NUMBERS §Mục 6ter",
        conv="TẬP A: hai nhiệt độ, ba bản quy tắc (gộp), lịch sử lượt đầu + 3 tán gẫu",
        probe="5,5×"),
    "lever.setB": dict(value="sai-dương 15,3× · J 1,43×", n="10 điểm vận hành", ci=None,
        src="tổng hợp ba mẻ — xem PAPER-NUMBERS §Mục 6ter",
        conv="TẬP B: tập A + 6/9 lượt tán gẫu + sau 3 từ chối", probe="15,3×"),

    # ---- grounding ----
    "gr.decision": dict(value="0/30", n="30", ci="Wilson 0,000–0,114; quy tắc ba: ≤ 10 %",
        src=B + "grounding_stability_20260909_run1.jsonl × " + B + "grounding_stability_20260910_run2.jsonl",
        conv="cửa sổ 13 giờ, qua đêm", probe="0/30"),
    "gr.domains": dict(value="15/21 = 0,714", n="21 câu có tra", ci="Wilson 0,500–0,862",
        src=B + "grounding_stability_20260909_run1.jsonl × " + B + "grounding_stability_20260910_run2.jsonl",
        conv="so bằng TÊN MIỀN, không phải uri", probe="15/21"),
    "gr.jaccard": dict(value="0,51", n="21", ci="— (trung bình, không phải tỉ lệ)",
        src=B + "grounding_stability_20260909_run1.jsonl × " + B + "grounding_stability_20260910_run2.jsonl",
        conv="trung bình Jaccard tập tên miền", probe="0,51"),
    "gr.neg_control": dict(value="7/9 = 0,78; Fisher p = 0,083", n="9", ci="Wilson 0,453–0,937",
        src=B + "grounding_stability_20260909_run1.jsonl × " + B + "grounding_stability_20260910_run2.jsonl",
        conv="đối chứng âm — so trên câu vịt NÓI RA", probe="7/9"),
    "gr.cost": dict(value="lời gọi hai 3 186 ms p50; +103 ms tới lúc nghe thấy", n="15 lượt có tra",
        ci=None, src=B + "grounding_20260909_v1.jsonl", conv="phân vị gần nhất; phân bố lưỡng cực",
        probe="+103 ms"),

    # ---- độ trễ / giả tượng ----
    "lat.e2e_v3": dict(value="p50 5 129 / p95 7 649 ms", n="90", ci=None,
        src=BL + "latency_desktop_baseline_2026-09-06_v3.jsonl",
        conv="phân vị gần nhất; nội suy tuyến tính cho 7 534 — lệch 115 ms", probe="7 649"),
    "lat.coldstart": dict(value="p50 và p95 dịch 0,00 ms ở cả 7 file", n="90 / 31", ci=None,
        src=BL + "latency_desktop_baseline_2026-09-06_v3.jsonl",
        conv="trừ 87,7 ms khỏi lượt đầu mỗi tiến trình", probe="0,00 ms"),
    "lat.e2e_with_device": dict(value="5 655 ms (5 129 + 526)", n="90 + 16", ci=None,
        src=BL + "latency_desktop_baseline_2026-09-06_v3.jsonl",
        conv="CHỈ dòng p50 cộng được. Dòng p95 (8 303 ms) là CẬN TRÊN THÔ, không phải "
             "p95 của tổng: hai đuôi độc lập nên chúng không đạt đỉnh cùng lúc.",
        probe="5 655"),

    # ---- nhánh open-weight (đợt 13, §1e) ----
    # Cổng chạy-lại CÙNG host, thay cho phép kiểm đổi-host đã bỏ cùng DeepInfra.
    "ow.rerun.lang": dict(value="23/23 = 1,000 nhãn không đổi", n="23 lượt",
        ci="Wilson 0,857–1,000",
        src="study/langconf/results/rerun_check_qwen2.5-7b.json",
        conv="cùng model, cùng prompt, cùng máy, seed=0 và temperature đã ghim, cách "
             "nhau 4 ngày. KHÔNG được viết 'tất định': cận dưới chỉ 0,857.",
        probe="23/23"),
    "ow.grid.qwen_d2": dict(value="0,746 so với 0,977 (không nhãn / nhãn ở user)",
        n="134 và 133 lượt", ci="Wilson 0,67–0,81 và 0,94–0,99",
        src="study/langconf/results/openweight_check.json",
        conv="LƯỚI RÚT GỌN 6 ô, Q4_K_M, ollama CPU. Tác vụ PHỤ — không phải phép đo nào "
             "của bài. Chiều tái lập, độ lớn thì không: ô này hosted rơi xuống 0,002.",
        probe="0,746"),
    "ow.grid.qwen_d8": dict(value="0,515 so với 0,955", n="134 và 132 lượt",
        ci="Wilson 0,43–0,60 và 0,90–0,98",
        src="study/langconf/results/openweight_check.json",
        conv="như trên; KTC hai ô TÁCH HẲN", probe="0,515"),
    "ow.grid.llama_d2": dict(value="26/26 = 1,000 — không nhiễm chút nào",
        n="26 lượt", ci="Wilson 0,87–1,00",
        src="study/langconf/results/openweight_check.json",
        conv="nhánh còn dở (128/4 000); KTC rộng. Ô mà hosted rơi xuống 0,002.",
        probe="26/26"),
    "ow.rerun.text": dict(value="7/23 = 0,304 chữ trùng từng ký tự", n="23 lượt",
        ci="Wilson 0,156–0,509",
        src="study/langconf/results/rerun_check_qwen2.5-7b.json",
        conv="cùng lượt như trên. Mọi tham số ghim được đều đã ghim mà chữ vẫn đổi ở "
             "70 % số lượt — cái tất định là QUYẾT ĐỊNH, không phải VĂN BẢN.",
        probe="7/23"),
}


# ---------------------------------------------------------------------------
# SỐ DẪN XUẤT — đếm từ chính tài liệu, không khai tay (đợt 27d). Số ca hỏng âm thầm = số `#`
# NGUYÊN của bảng catalogue §9 (dòng "2b" là cơ chế thứ hai của ca 2, không phải ca mới).
CATALOGUE = REPO / "paper" / "09b-silent-failures.md"
MACROS = REPO / "Submission TSE" / "latex" / "numbers_macros.tex"
CHU = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
       9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 20: "twenty"}


def dem_catalogue() -> int:
    """Đếm dòng `| <số nguyên> | ...` trong mục `### A. The catalogue` (tới mục ### kế tiếp)."""
    text = CATALOGUE.read_text(encoding="utf-8")
    m = re.search(r"^### A\. The catalogue\s*$(.*?)^### ", text, re.M | re.S)
    if not m:
        raise SystemExit(f"không thấy '### A. The catalogue' trong {CATALOGUE}")
    so = [int(x) for x in re.findall(r"^\|\s*(\d+)\s*\|", m.group(1), re.M)]
    if so != list(range(1, len(so) + 1)):
        raise SystemExit(f"số ca trong catalogue không liên tục 1..n: {so}")
    return len(so)


PLAN = REPO / "docs" / "benchmark" / "runner" / "plan.json"
S3_MANIFEST = REPO / "docs" / "benchmark" / "M1_s3_manifest.json"


def dem_tang_m1() -> dict[str, int]:
    """Cỡ ba tầng M1 (A04.2), đếm từ plan.json (S1, S2: số utterance KHÁC NHAU theo task t0 gemini) và
    manifest S3 (số WAV được nhận) — không gõ tay (đợt 27e việc 140)."""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    t0 = [t for t in plan["tasks"] if t["m"] == "M1" and t["id"].endswith("|gemini|t0|1")]
    s1 = {t["id"].split("|")[1] for t in t0 if t["id"].split("|")[1].startswith("rv1_")}
    s2 = {t["id"].split("|")[1] for t in t0 if t["params"].get("tang") == "wild"}
    s3 = json.loads(S3_MANIFEST.read_text(encoding="utf-8"))["tong"]["nhan"]
    s3_plan = {t["id"].split("|")[1] for t in t0 if t["params"].get("tang") == "s3"}
    if len(s3_plan) != s3:
        raise SystemExit(f"S3: manifest nhận {s3} nhưng plan có {len(s3_plan)} utterance")
    return {"S1": len(s1), "S2": len(s2), "S3": s3}


def dem_m6() -> dict[str, int]:
    """Số lần chạy M6 và số NGÀY lịch chúng trải qua (đợt 27e, sau duyệt 142): từ plan.json — task M6 và
    lịch m6.lich phải khớp nhau. Có dữ liệu thì đếm thêm số lần chạy ok trong M6 jsonl: việc 143 dùng số ấy
    (A04.3: thiếu lần thì báo số thực, không chạy bù), nên hai số lệch nhau sau 21/09 19:30 là cờ đỏ."""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    task = [t for t in plan["tasks"] if t["m"] == "M6"]
    lich = plan["m6"]["lich"]
    if sorted(t["at"] for t in task) != sorted(lich):
        raise SystemExit(f"M6: {len(task)} task trong plan không khớp lịch m6.lich ({len(lich)} mốc)")
    ngay = {a[:10] for a in lich}
    ok = set()
    duong = REPO / plan["results"]["M6"]
    if duong.exists():
        for line in duong.read_bytes().splitlines():
            try:
                r = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            if isinstance(r, dict) and r.get("status") == "ok":
                ok.add(r.get("task_id"))
    return {"runs": len(task), "days": len(ngay), "ok": len(ok)}




# Việc 143 — nhãn năm cột cho các số dẫn xuất của mẻ đăng ký trước.
# Cột `n` mang NHÃN ĐƠN VỊ của M6 (đợt 27h việc D): gộp-qua-19-lần khác trong-một-lần.
NHAN_27F: dict[str, tuple[str, str, str, str]] = {
    "m3.milestones": ("14 mốc", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "số mốc 12 h theo A01.3", "numMThreeMilestones"),
    "m3.questions": ("30 câu", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "cỡ bộ câu hỏi mỗi mốc", "numMThreeQuestions"),
    "m3.retrieving": ("20 / 30 câu", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "câu CÓ tra ở mốc 1; mẫu số của hai dòng dưới", "numMThreeRetrieving"),
    "m3.domain_changed": ("19 / 20 câu có tra", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "mốc 14 so mốc 1, tập tên miền", "numMThreeDomainChanged"),
    "m3.text_changed": ("20 / 20 câu có tra", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "mốc 14 so mốc 1, trường answer", "numMThreeTextChanged"),
    "m3.domain_lo": ("13 mốc (2..14)", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "cận DƯỚI dải domain-set đổi — dùng để nói curve PHẲNG", "numMThreeDomainLo"),
    "m3.domain_hi": ("13 mốc (2..14)", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "cận TRÊN dải domain-set đổi", "numMThreeDomainHi"),
    "m3.text_lo": ("13 mốc (2..14)", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "cận DƯỚI dải text đổi", "numMThreeTextLo"),
    "m3.text_hi": ("13 mốc (2..14)", "docs/benchmark/M3_20260916_v1.jsonl (14 mốc × 30 câu)", "cận TRÊN dải text đổi", "numMThreeTextHi"),
    "m6.margin": ("40 test, 19 lần", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "biên flake(artefact) − flake(decision), ô routing-hosted", "numMSixMargin"),
    "m6.margin_lo": ("40 test, 19 lần", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "Newcombe 95 % cận dưới", "numMSixMarginLo"),
    "m6.margin_hi": ("40 test, 19 lần", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "Newcombe 95 % cận trên", "numMSixMarginHi"),
    "m6.dec_flaky": ("k of n tests flaky across 19 runs", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "bộ decision CŨNG flake — không phải 0", "numMSixDecFlaky"),
    "m6.art_flaky": ("k of n tests flaky across 19 runs", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "bộ artefact, cùng mẫu số", "numMSixArtFlaky"),
    "m6.n_tests": ("k of n tests flaky across 19 runs", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "mẫu số của hai dòng trên", "numMSixTestsRouting"),
    "m6.short_dec": ("k of n tests failing in run r", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "lần 2, cách golden 22 phút (ca I-15) — ĐƠN VỊ KHÁC bảng gộp", "numMSixShortDec"),
    "m6.short_art": ("k of n tests failing in run r", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "lần 2, cách golden 22 phút — bằng chứng bảo thủ", "numMSixShortArt"),
    "m6.tests_per_run": ("k of n tests failing in run r", "docs/benchmark/M6_M7_cham_20260923.json · M6_20260918_v1.jsonl", "126 test × 2 bộ oracle", "numMSixTestsPerRun"),
    "m7.correct": ("15 đơn vị", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "đúng", "numMSevenCorrect"),
    "m7.wrong": ("15 đơn vị", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "sai — in nguyên, gồm ô 2 và ô 12", "numMSevenWrong"),
    "m7.undecided": ("15 đơn vị", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "không phân định", "numMSevenUndecided"),
    "m7.total": ("15 đơn vị", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "mẫu số sau khi trừ A06 và thiếu lực", "numMSevenTotal"),
    "m7.excluded": ("29 đơn vị in ra", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "A06 loại, in nhưng không vào mẫu số", "numMSevenExcluded"),
    "m7.underpowered": ("29 đơn vị in ra", "docs/benchmark/M6_M7_cham_20260923.json (M7.tong_ket)", "thiếu lực A04.5 (n < 35), đăng ký trước", "numMSevenUnderpowered"),
}

CHAM_M6M7 = REPO / "docs" / "benchmark" / "M6_M7_cham_20260923.json"


def dem_me_27f() -> dict:
    """Kết quả mẻ đăng ký trước 16–23/09 (việc 143) — ĐỌC TỪ FILE ĐO, không gõ tay.

    Vì sao ở `dan_xuat` chứ không ở `SO`: `SO` dành cho con số đối chiếu CHUỖI với sổ cái, hợp với
    số chép từ một mẻ đã đóng. Các số dưới đây **tính lại từ jsonl mỗi lần dựng**, nên chúng không
    thể trôi khỏi dữ liệu — đúng cách `m1.s*.n`, `m6.runs`, `m6.days` đã làm. Mục 11 của sổ cái
    sinh từ CÙNG các file này bằng `build_muc11.py`, nên sổ và macro không thể lệch nhau.
    """
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    ra: dict = {}

    # ---- M3: đường cong 14 mốc ----
    duong = REPO / plan["results"]["M3"]
    moc: dict[str, dict] = {}
    for line in duong.read_bytes().splitlines():
        if not line.strip():
            continue
        r = json.loads(line.decode("utf-8"))
        if r.get("status") != "ok" or r["task_id"].startswith("M3|probe-nosearch"):
            continue
        moc.setdefault(r["due"], {})[r["task_id"].split("|")[-1]] = r
    keys = sorted(moc)
    g, cuoi = moc[keys[0]], moc[keys[-1]]
    tra = [i for i in g if g[i]["payload"]["lookup"]]
    dom = [sum(1 for i in sorted(set(g) & set(moc[k]))
               if set(moc[k][i]["payload"]["domains"]) != set(g[i]["payload"]["domains"]))
           for k in keys[1:]]
    txt = [sum(1 for i in sorted(set(g) & set(moc[k]))
               if (moc[k][i]["payload"]["answer"] or "").strip() != (g[i]["payload"]["answer"] or "").strip())
           for k in keys[1:]]
    ra["m3.milestones"] = str(len(keys))
    ra["m3.questions"] = str(len(g))
    ra["m3.retrieving"] = str(len(tra))
    ra["m3.domain_changed"] = str(sum(1 for i in tra if set(cuoi[i]["payload"]["domains"])
                                      != set(g[i]["payload"]["domains"])))
    ra["m3.text_changed"] = str(sum(1 for i in tra if (cuoi[i]["payload"]["answer"] or "").strip()
                                    != (g[i]["payload"]["answer"] or "").strip()))
    ra["m3.domain_lo"], ra["m3.domain_hi"] = str(min(dom)), str(max(dom))
    ra["m3.text_lo"], ra["m3.text_hi"] = str(min(txt)), str(max(txt))

    # ---- M6 / M7: từ bản chấm ----
    cham = json.loads(CHAM_M6M7.read_text(encoding="utf-8"))
    o = cham["M6"]["o"]["routing-hosted"]
    ra["m6.margin"] = f"{o['bien_art_tru_dec']:.3f}"
    ra["m6.margin_lo"] = f"{o['newcombe_bien'][0]:.3f}"
    ra["m6.margin_hi"] = f"{o['newcombe_bien'][1]:.3f}"
    ra["m6.dec_flaky"] = str(o["decision"]["flaky_tests"])
    ra["m6.art_flaky"] = str(o["artefact"]["flaky_tests"])
    ra["m6.n_tests"] = str(o["decision"]["n_tests"])

    # lần chạy cách golden ngắn nhất (22 phút, ca I-15) — đơn vị KHÁC: test hỏng TRONG MỘT lần
    duong6 = REPO / plan["results"]["M6"]
    lan = []
    for line in duong6.read_bytes().splitlines():
        if not line.strip():
            continue
        r = json.loads(line.decode("utf-8"))
        if r.get("status") == "ok":
            lan.append(r)
    lan.sort(key=lambda r: r["payload"]["lan"])
    sau = lan[1]
    dec = sum(1 for t, kq in sau["payload"]["tests"].items()
              if kq != "passed" and t.split("::", 1)[0] == "decision")
    art = sum(1 for t, kq in sau["payload"]["tests"].items()
              if kq != "passed" and t.split("::", 1)[0] != "decision")
    ra["m6.short_dec"], ra["m6.short_art"] = str(dec), str(art)
    ra["m6.tests_per_run"] = str(len(sau["payload"]["tests"]))

    t7 = cham["M7"]["tong_ket"]
    for k, v in (("correct", "dung"), ("wrong", "sai"), ("undecided", "khong_phan_dinh"),
                 ("total", "mau_so"), ("excluded", "loai_a06"),
                 ("underpowered", "thieu_luc_khong_tinh")):
        ra["m7." + k] = str(t7[v])
    return ra

def dan_xuat() -> dict:
    n = dem_catalogue()
    ra = {"silent.count": dict(value=str(n), word=CHU[n], n=f"{n} ca", ci=None,
                               src="paper/09b-silent-failures.md §A (bảng)",
                               conv="đếm số # nguyên; 2b là cơ chế thứ hai của ca 2",
                               probe=None, macro="numSilentFailures")}
    tang = dem_tang_m1()
    for k, macro, src in (("S1", "numSOne", "plan.json: task M1 rv1_* t0 gemini"),
                          ("S2", "numSTwo", "plan.json: task M1 tang=wild t0 gemini"),
                          ("S3", "numSThree", "M1_s3_manifest.json tong.nhan (= plan tang=s3)")):
        ra[f"m1.{k.lower()}.n"] = dict(value=str(tang[k]), n=f"{tang[k]} utterance", ci=None, src=src,
                                       conv="cỡ tầng thiết kế (A04.2), không phải kết quả", probe=None,
                                       macro=macro)
    m6 = dem_m6()
    ra["m6.runs"] = dict(value=str(m6["runs"]), word=CHU[m6["runs"]], n=f"{m6['runs']} lần chạy", ci=None,
                         src="plan.json: task M6 (= m6.lich)", conv=f"thiết kế A04.3; ok trong jsonl hiện {m6['ok']}",
                         probe=None, macro="numMSixRuns")
    ra["m6.days"] = dict(value=str(m6["days"]), word=CHU[m6["days"]], n=f"{m6['days']} ngày lịch", ci=None,
                         src="plan.json: ngày khác nhau trong m6.lich", conv="đếm ngày lịch, không phải 24 h × n",
                         probe=None, macro="numMSixDays")

    # Việc 143 — kết quả mẻ đăng ký trước. `probe=None` như mọi số dẫn xuất khác: chúng tính
    # lại từ jsonl mỗi lần dựng nên không cần (và không nên) khớp chuỗi với sổ.
    for k, v in dem_me_27f().items():
        ra[k] = dict(value=v, n=NHAN_27F[k][0], ci=None, src=NHAN_27F[k][1],
                     conv=NHAN_27F[k][2], probe=None, macro=NHAN_27F[k][3])
    return ra



def kiem_khop_so_cai(dx: dict) -> list[str]:
    """Mục 11h của sổ cái phải khớp từng giá trị với `dan_xuat` — khoá vòng của đợt 27i.

    Hai đường tính độc lập từ cùng bộ jsonl: `build_muc11.py` → sổ, `dem_me_27f()` → numbers.json.
    Không buộc chúng thì chúng trôi khỏi nhau lặng lẽ. Sổ in `0,750`, json giữ `0.750` — so sau khi
    chuẩn hoá dấu thập phân. `tests/test_muc11_khop_numbers.py` kiểm kỹ hơn (gồm tập khoá);
    ở đây chỉ cần một câu trả lời cho cổng dựng gói, không gọi pytest lồng nhau.
    """
    text = LEDGER.read_text(encoding="utf-8")
    if "### 11h." not in text:
        return ["sổ cái chưa có mục 11h — chạy `python scripts/build_muc11.py`"]
    bang = {}
    for dong in text[text.index("### 11h."):].splitlines():
        m = re.match(r"\|\s*`([a-z0-9_.]+)`\s*\|\s*`([^`]+)`\s*\|\s*$", dong)
        if m:
            bang[m.group(1)] = m.group(2).strip().replace(",", ".")
    loi = []
    for k in NHAN_27F:
        cho = str(dx[k]["value"]).replace(",", ".")
        if k not in bang:
            loi.append(f"{k}: thiếu trong mục 11h")
        elif bang[k] != cho:
            loi.append(f"{k}: sổ nói {bang[k]!r}, numbers.json nói {cho!r}")
    thua = sorted(set(bang) - set(NHAN_27F))
    if thua:
        loi.append(f"mục 11h có khoá không khai trong NHAN_27F: {thua}")
    return loi

def macros_tex(dx: dict) -> str:
    n = dx["silent.count"]
    return ("% SINH BỞI desktop/scripts/build_numbers.py — KHÔNG SỬA TAY.\n"
            "% Nguồn: " + n["src"] + "; plan.json; M1_s3_manifest.json\n"
            f"\\newcommand{{\\numSilentFailures}}{{{n['word']}}}\n"
            f"\\newcommand{{\\NumSilentFailures}}{{{n['word'].capitalize()}}}\n"
            f"\\newcommand{{\\numSilentFailuresDigit}}{{{n['value']}}}\n"
            + "".join(f"\\newcommand{{\\{dx[k]['macro']}}}{{{dx[k]['value']}}}\n"
                      for k in ("m1.s1.n", "m1.s2.n", "m1.s3.n"))
            + f"\\newcommand{{\\numMSixRuns}}{{{dx['m6.runs']['word']}}}\n"
            + f"\\newcommand{{\\numMSixRunsDigit}}{{{dx['m6.runs']['value']}}}\n"
            + f"\\newcommand{{\\numMSixDays}}{{{dx['m6.days']['word']}}}\n"
            + "% Việc 143 — mẻ đăng ký trước 16–23/09, tính lại từ jsonl mỗi lần dựng.\n"
            + "".join(f"\\newcommand{{\\{NHAN_27F[k][3]}}}{{{dx[k]['value']}}}\n"
                      for k in NHAN_27F))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="chỉ kiểm, không ghi")
    enable_utf8_console()   # console Windows mac dinh la cp1258, in tieng Viet la vo
    args = ap.parse_args()

    ledger = LEDGER.read_text(encoding="utf-8")
    thieu = [k for k, v in SO.items() if v["probe"] not in ledger]

    print(f"Khai {len(SO)} con số; đối chiếu chuỗi với {LEDGER.name}")
    if thieu:
        print(f"\n!! {len(thieu)} con số KHÔNG tìm thấy nguyên văn trong sổ:")
        for k in thieu:
            print(f"   {k}   probe={SO[k]['probe']!r}")
        print("\n   Sổ là nguồn sự thật. Hoặc sửa `probe`, hoặc con số ấy chưa vào sổ.")
        return 1
    print("   tất cả khớp.")

    # Năm cột bắt buộc — thiếu cột nào thì con số ấy không được vào bài.
    khong_du = [k for k, v in SO.items() if not v["value"] or not v["n"] or not v["src"] or not v["conv"]]
    if khong_du:
        print(f"\n!! {len(khong_du)} con số thiếu cột bắt buộc: {khong_du}")
        return 1

    dx = dan_xuat()
    print(f"   dẫn xuất: silent.count = {dx['silent.count']['value']} ({dx['silent.count']['word']}) "
          f"từ {CATALOGUE.name}")
    data = {"_generated_from": "docs/PAPER-NUMBERS.md",
            "_rule": "value · n · ci · source · conventions; thiếu cột nào thì không vào bài",
            "numbers": SO, "dan_xuat": dx}
    lech = kiem_khop_so_cai(dx)
    if lech:
        print(f"\n!! sổ cái mục 11h KHÔNG khớp numbers.json ({len(lech)} chỗ):")
        for d in lech:
            print("   " + d)
        print("\n   Chạy lại build_muc11.py VÀ build_numbers.py; đừng sửa tay một bên.")
        return 1
    print(f"   mục 11h khớp numbers.json ({len(NHAN_27F)} khoá).")

    if args.check:
        loi = 0
        if OUT.exists():
            cu = json.loads(OUT.read_text(encoding="utf-8"))
            if cu.get("numbers") != SO or cu.get("dan_xuat") != dx:
                print("\n!! paper/numbers.json ĐÃ CŨ — chạy lại không có --check")
                loi = 1
            else:
                print("   paper/numbers.json khớp.")
        if not MACROS.exists() or MACROS.read_text(encoding="utf-8") != macros_tex(dx):
            print(f"\n!! {MACROS.name} CŨ hoặc thiếu — chạy lại không có --check")
            loi = 1
        return loi

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    MACROS.write_text(macros_tex(dx), encoding="utf-8")
    print(f"   ghi {OUT}\n   ghi {MACROS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
