r"""Đo bộ định tuyến tra cứu: ĐỘ CHÍNH XÁC và TÍNH TẤT ĐỊNH.

    python scripts\bench_routing.py accuracy                    # việc 4a, 120 lượt
    python scripts\bench_routing.py determinism --reps 10       # việc 5a-5b
    python scripts\bench_routing.py history --reps 5            # việc 5c
    python scripts\bench_routing.py ab-refusal --reps 5         # việc 12
    python scripts\bench_routing.py rule-lang --reps 2        # việc 17, lưới 2x2
    python scripts\bench_routing.py rule-lang --rules vi,en,vi-v2 --reps 2   # việc 21
    python scripts\bench_routing.py history-neutral --reps 5  # việc 18

Hai thứ người ta hay gộp mà phải tách rõ:

- **Độ chính xác** — nó đoán ĐÚNG không. precision/recall so nhãn tay.
- **Tính tất định** — cùng một câu hỏi, hỏi lại N lần, nhãn có ỔN ĐỊNH không.

Một bộ định tuyến chính xác 85 % nhưng lật qua lật lại giữa các lần chạy thì không
dùng được, dù precision nhìn đẹp. Đúng bài học ADR-007 đã rút ở tầng STT: cùng một
file "Dừng." chép bốn lần ra bốn câu tiếng Anh khác nhau.

Bộ câu hỏi: `docs/benchmark/lookup_set_v1.jsonl`, giao thức ở
`docs/benchmark/LABELING-PROTOCOL.md`. Khối A chấm `[lookup]`, khối B chấm
`[premise]` (§3.3: tiền đề sai thì KHÔNG chấm định tuyến).

Chạy với `LLM_SEARCH` TẮT — chỉ cần cái NHÃN, không cần thật sự đi tra. Rẻ hơn
nhiều và không đụng hạn mức grounding.

KHÔNG ghi vào `logs/latency.jsonl` chính, KHÔNG đụng `docs/baseline/`.
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import statistics
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.persona import load_persona
from config import Config, enable_utf8_console
from handlers.llm_gemini import GeminiLLMHandler
from latency import LatencyTracker
from speech_to_speech.pipeline.messages import Transcription, TTSInput

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
SET_PATH = BENCH_DIR / "lookup_set_v1.jsonl"

# Song song vừa phải: đủ nhanh cho 2 000 lượt, đủ chậm để không đụng hạn mức phút.
WORKERS = 6

# Lượt đệm cho việc 5c. Ba câu KHÔNG cần tra và ba câu CẦN tra, lấy ngoài bộ thử để
# không dùng chính câu đang đo làm lịch sử của nó.
DEM_KHONG_TRA = [
    "Em kể cho anh một câu chuyện cười ngắn đi.",
    "Một cây số bằng bao nhiêu mét?",
    "Em giải thích ngắn gọn lực hấp dẫn là gì.",
]
DEM_CAN_TRA = [
    "Sáng nay Hà Nội bao nhiêu độ?",
    "Giá cà phê trong nước hôm nay thế nào?",
    "Tuần này có tin gì mới về xe điện ở Việt Nam?",
]

# Việc 18: lượt TRUNG TÍNH — tán gẫu vô thưởng vô phạt. Ba điều kiện, thiếu một cái là
# hỏng phép thử: (a) KHÔNG phải câu cần tra, nên không sinh nhãn `[lookup]` trong lịch
# sử; (b) KHÔNG sinh câu từ chối, nên không có nội dung "em không biết" để bắt chước;
# (c) KHÔNG phải câu hỏi sự kiện, khác hẳn DEM_KHONG_TRA — mấy câu ấy tuy không cần
# tra nhưng vẫn là hỏi-đáp tri thức, và "vịt vừa trả lời chắc nịch ba câu" tự nó đã là
# một mồi. Còn lại đúng MỘT biến: lịch sử DÀI THÊM bao nhiêu lượt.
#
# Tiếng Việt hết, kể cả khi câu đích là tiếng Anh — đúng như DEM_* của Bảng 6 đang làm.
# Đổi sang filler hợp ngôn ngữ thì so với Bảng 6 không còn sạch nữa; giữ nguyên tật cũ
# để hai bảng còn nói chuyện được với nhau, và ghi lại ở đây rằng đó là tật.
DEM_TRUNG_TINH = [
    "Chào em, hôm nay em thấy trong người thế nào?",
    "Em thích màu gì nhất?",
    "Em kể xem hôm nay có gì làm em thấy vui không?",
    "Em thấy làm vịt có gì hay?",
    "Nếu được đặt tên lại cho mình thì em chọn tên gì?",
    "Em thích buổi sáng hay buổi tối hơn?",
    "Em có bài hát nào hay ngân nga không?",
    "Em tưởng tượng xem cuối tuần này mình làm gì cho vui?",
    "Em thấy hôm nay nói chuyện với anh có dễ chịu không?",
]


def doc_bo() -> list[dict]:
    if not SET_PATH.exists():
        raise SystemExit(f"Chưa có {SET_PATH}. Chạy scripts\\build_lookup_set.py trước.")
    return [json.loads(line) for line in SET_PATH.read_text(encoding="utf-8").splitlines() if line]


class Vit:
    """Một con vịt chỉ có não, dùng riêng cho một luồng. Lịch sử tự quản."""

    def __init__(self, cfg: Config, prompt: str, temperature: float | None,
                 varied_phrases: bool = False) -> None:
        self.tracker = LatencyTracker(path=None, echo=False)
        kwargs: dict[str, Any] = {
            "api_key": cfg.gemini_api_key,
            "model": cfg.gemini_model,
            "system_prompt": prompt,
            "tracker": self.tracker,
            "varied_phrases": varied_phrases,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        self.handler = GeminiLLMHandler(
            threading.Event(), queue_in=queue.Queue(), queue_out=queue.Queue(),
            setup_kwargs=kwargs,
        )

    def hoi(self, text: str, lang: str) -> dict[str, Any]:
        """Một lượt. Trả về nhãn + lời thoại + độ trễ tầng LLM."""
        self.tracker.start_turn()
        reply = " ".join(
            out.text for out in self.handler.process(Transcription(text=text, language_code=lang))
            if isinstance(out, TTSInput)
        )
        record = self.tracker.finish() or {}
        return {
            "lookup": bool(record.get("lookup_flagged")),
            "premise": bool(record.get("premise_flagged")),
            "reply": reply,
            "llm_ms": record.get("t_llm_first"),
        }

    def quen(self) -> None:
        self.handler.on_session_end()


def chay_song_song(viec: list[Any], lam, nhan: str) -> list[Any]:
    """Chạy `viec` bằng ThreadPool, in tiến độ. Lỗi một lượt không giết cả mẻ."""
    xong = [0]
    khoa = threading.Lock()

    def boc(item):
        try:
            ket_qua = lam(item)
        except Exception as exc:                    # hạn mức, mạng, model trả rác
            ket_qua = {"error": f"{type(exc).__name__}: {exc}"}
        with khoa:
            xong[0] += 1
            if xong[0] % 25 == 0 or xong[0] == len(viec):
                print(f"  {nhan}: {xong[0]}/{len(viec)}")
        return ket_qua

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(boc, viec))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Khoảng tin cậy Wilson 95 %. Dùng nó chứ không dùng công thức chuẩn: ở
    k/n = 15/15 công thức chuẩn cho khoảng rộng bằng 0, vô nghĩa."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    giua = p + z * z / (2 * n)
    lech = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    mau = 1 + z * z / n
    return (max(0.0, (giua - lech) / mau), min(1.0, (giua + lech) / mau))


def ghi(path: Path, rows: list[dict]) -> None:
    """Ghi jsonl, KHÔNG ghi đè file đã có — thêm hậu tố `_bN` nếu trùng tên.

    Ngày 09/09 một mẻ đo Bảng 6 đã ghi đè mất file của việc 18 vì hai lệnh khác nhau
    sinh cùng một tên theo ngày. Cứu được nhờ file kia đã commit, nhưng đó là may chứ
    không phải thiết kế: dữ liệu đo là thứ chạy lại tốn tiền và tốn giờ, và một mẻ ghi
    đè lặng lẽ thì không ai biết cho tới lúc đi tìm nó.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        goc = path
        i = 2
        while path.exists():
            path = goc.with_name(f"{goc.stem}_b{i}{goc.suffix}")
            i += 1
        print(f"  ({goc.name} đã có — ghi sang {path.name} thay vì đè lên)")
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nGhi {len(rows)} bản ghi vào {path}")


# -- việc 4a: độ chính xác ----------------------------------------------------


def lenh_accuracy(cfg: Config, prompt: str, args) -> int:
    bo = doc_bo()
    print(f"Độ chính xác trên {len(bo)} câu (khối A chấm [lookup], khối B chấm [premise])")

    cuc_bo = threading.local()

    def mot_cau(row: dict) -> dict:
        vit = getattr(cuc_bo, "vit", None)
        if vit is None:
            vit = cuc_bo.vit = Vit(cfg, prompt, temperature=None)
        vit.quen()                                   # lịch sử RỖNG cho từng câu
        ra = vit.hoi(row["question"], row["lang"])
        return {**row, **ra, "ts": datetime.now(timezone.utc).astimezone().isoformat()}

    rows = chay_song_song(bo, mot_cau, "lượt")
    rows = [r for r in rows if "error" not in r]
    ghi(BENCH_DIR / f"lookup_accuracy_{date.today():%Y%m%d}_v2.jsonl", rows)
    bao_cao_accuracy(rows)
    return 0


def bao_cao_accuracy(rows: list[dict]) -> None:
    khoi_a = [r for r in rows if r["block"] == "A"]
    khoi_b = [r for r in rows if r["block"] == "B"]

    def bang(rows_: list[dict], ten: str) -> None:
        dd = sum(1 for r in rows_ if r["needs_lookup"] and r["lookup"])
        sd = sum(1 for r in rows_ if not r["needs_lookup"] and r["lookup"])
        sa = sum(1 for r in rows_ if r["needs_lookup"] and not r["lookup"])
        da = sum(1 for r in rows_ if not r["needs_lookup"] and not r["lookup"])
        p = dd / (dd + sd) if dd + sd else 0.0
        rc = dd / (dd + sa) if dd + sa else 0.0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        lo, hi = wilson(dd, dd + sa)
        print(f"\n  {ten}  (n={len(rows_)})")
        print(f"    đúng-dương {dd}   sai-dương {sd}   SAI-ÂM {sa}   đúng-âm {da}")
        print(f"    precision {p:.3f}   recall {rc:.3f}  [Wilson 95% {lo:.3f}–{hi:.3f}]   F1 {f1:.3f}")

    print("\n=== KHỐI A — định tuyến [lookup] ===")
    bang(khoi_a, "tất cả")
    for lang in ("vi", "en"):
        bang([r for r in khoi_a if r["lang"] == lang], f"tiếng {'Việt' if lang == 'vi' else 'Anh'}")
    for ft in ("never-changing", "slow-changing", "fast-changing"):
        con = [r for r in khoi_a if r["fact_type"] == ft]
        gan = sum(1 for r in con if r["lookup"])
        print(f"    {ft:<16} gắn nhãn {gan}/{len(con)}"
              + ("   <- ca RANH GIỚI" if ft == "slow-changing" else ""))

    sai_am = [r for r in khoi_a if r["needs_lookup"] and not r["lookup"]]
    print(f"\n  SAI-ÂM = cần tra mà không nhận ra rồi trả lời bừa: "
          f"{len(sai_am)}/{sum(1 for r in khoi_a if r['needs_lookup'])}")
    for r in sai_am:
        print(f"    [{r['lang']} {r['fact_type']}] {r['question'][:78]}")
        print(f"          -> {r['reply'][:100]}")

    print("\n=== KHỐI B — nhãn [premise], tiền đề SAI ===")
    bat = sum(1 for r in khoi_b if r["premise"])
    lo, hi = wilson(bat, len(khoi_b))
    print(f"  nhận ra tiền đề sai: {bat}/{len(khoi_b)}  [Wilson 95% {lo:.3f}–{hi:.3f}]")
    print(f"  trong đó cũng gắn [lookup]: {sum(1 for r in khoi_b if r['premise'] and r['lookup'])}"
          f"  (không tính là sai — xem LABELING-PROTOCOL §3.3)")
    for r in khoi_b:
        if not r["premise"]:
            print(f"    BỎ SÓT [{r['lang']}] {r['question'][:78]}")
            print(f"          -> {r['reply'][:100]}")


# -- việc 5a-5b: tính tất định ------------------------------------------------


def lenh_determinism(cfg: Config, prompt: str, args) -> int:
    bo = [r for r in doc_bo() if r["block"] == "A"]
    if args.limit:
        bo = bo[: args.limit]
    cau_hinh = [("mac-dinh", None), ("temp0", 0.0)]
    print(f"Tính tất định: {len(bo)} câu × {args.reps} lần × {len(cau_hinh)} cấu hình "
          f"= {len(bo) * args.reps * len(cau_hinh)} lượt")

    cuc_bo = threading.local()
    viec = [(row, ten, temp, lan)
            for ten, temp in cau_hinh for row in bo for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, ten, temp, lan = item
        khoa = f"vit_{ten}"
        vit = getattr(cuc_bo, khoa, None)
        if vit is None:
            vit = Vit(cfg, prompt, temperature=temp)
            setattr(cuc_bo, khoa, vit)
        vit.quen()
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "fact_type": row["fact_type"],
                "needs_lookup": row["needs_lookup"], "config": ten, "rep": lan,
                "lookup": ra["lookup"], "premise": ra["premise"], "llm_ms": ra["llm_ms"]}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]
    ghi(BENCH_DIR / f"lookup_determinism_{date.today():%Y%m%d}_v1.jsonl", rows)
    bao_cao_determinism(rows)
    return 0


def entropy(p: float) -> float:
    if p in (0.0, 1.0):
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def bao_cao_determinism(rows: list[dict]) -> None:
    for cau_hinh in sorted({r["config"] for r in rows}):
        con = [r for r in rows if r["config"] == cau_hinh]
        theo_cau: dict[str, list[bool]] = defaultdict(list)
        for r in con:
            theo_cau[r["id"]].append(r["lookup"])

        nhat_quan = [cid for cid, v in theo_cau.items() if len(set(v)) == 1]
        lat = []
        ent = []
        for cid, v in theo_cau.items():
            da_so = Counter(v).most_common(1)[0][1]
            lat.append((len(v) - da_so) / len(v))
            ent.append(entropy(sum(v) / len(v)))

        print(f"\n=== {cau_hinh} ===")
        print(f"  câu 100% nhất quán: {len(nhat_quan)}/{len(theo_cau)} "
              f"({len(nhat_quan) / len(theo_cau) * 100:.1f} %)")
        print(f"  flip rate (tỉ lệ lần chạy trái đa số): {statistics.mean(lat) * 100:.2f} %")
        print(f"  entropy trung bình mỗi câu: {statistics.mean(ent):.4f} bit")

        bat_on = sorted(((e, cid) for e, cid in zip(ent, theo_cau)), reverse=True)[:8]
        bat_on = [(e, cid) for e, cid in bat_on if e > 0]
        if bat_on:
            print("  bất ổn nhất — ranh giới nằm ở đây:")
            for e, cid in bat_on:
                v = theo_cau[cid]
                print(f"    {cid:<20} {sum(v)}/{len(v)} lần gắn nhãn, entropy {e:.3f}")
        else:
            print("  không câu nào lật — entropy 0 trên toàn bộ.")

    # Gemini KHÔNG bảo đảm tất định ngay cả ở temperature=0. Đây là điều PHẢI đo
    # chứ không được giả định, và nếu đúng là không tất định thì đó là kết quả
    # đáng báo cáo, không phải lỗi cần giấu.
    print("\n(Nhắc: temperature=0 KHÔNG bảo đảm tất định ở Gemini. Số trên là số đo,"
          " không phải giả định.)")


# -- việc 5c: ảnh hưởng của lịch sử hội thoại ---------------------------------


def lenh_history(cfg: Config, prompt: str, args) -> int:
    """Giả thuyết mạnh nhất, bắt nguồn từ ADR-008: lịch sử THẮNG system prompt.

    Nếu vài lượt trước không gắn nhãn, model bắt chước chính nó và NGỪNG gắn.
    """
    bo = [r for r in doc_bo()
          if r["block"] == "A" and r["needs_lookup"] and r["fact_type"] == "fast-changing"]
    bo = bo[: args.limit or 20]
    vi_tri = [("dau-phien", []), ("sau-3-khong-tra", DEM_KHONG_TRA), ("sau-3-co-tra", DEM_CAN_TRA)]
    print(f"Ảnh hưởng lịch sử: {len(bo)} câu × {len(vi_tri)} vị trí × {args.reps} lần")

    cuc_bo = threading.local()
    viec = [(row, ten, dem, lan) for ten, dem in vi_tri for row in bo for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, ten, dem, lan = item
        vit = getattr(cuc_bo, "vit", None)
        if vit is None:
            vit = cuc_bo.vit = Vit(cfg, prompt, temperature=None)
        vit.quen()
        for cau in dem:                              # dựng lịch sử THẬT, không giả
            vit.hoi(cau, row["lang"])
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "position": ten, "rep": lan,
                "lookup": ra["lookup"], "reply": ra["reply"][:160]}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]
    ghi(BENCH_DIR / f"lookup_history_{date.today():%Y%m%d}_v1.jsonl", rows)

    print("\n=== tỉ lệ gắn nhãn theo VỊ TRÍ trong phiên ===")
    for ten, _ in vi_tri:
        con = [r for r in rows if r["position"] == ten]
        if not con:
            continue
        gan = sum(1 for r in con if r["lookup"])
        lo, hi = wilson(gan, len(con))
        print(f"  {ten:<20} {gan}/{len(con)} = {gan / len(con) * 100:5.1f} %"
              f"   [Wilson 95% {lo:.3f}–{hi:.3f}]")
    print("\nCách chữa nếu có hiệu ứng đã biết sẵn từ ADR-008: kẹp chỉ thị vào LƯỢT"
          " NGƯỜI DÙNG, không chỉ ở system prompt.")
    return 0


# -- việc 12: A/B câu từ chối -------------------------------------------------


def z_hai_ti_le(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """z và p (hai phía) cho H0: hai tỉ lệ bằng nhau. Xấp xỉ chuẩn, gộp phương sai.

    Xấp xỉ này cần np và n(1-p) đủ lớn; ở n = 100 mỗi ô và tỉ lệ 0,78-0,93 thì đạt.
    Nếu chạy với `--reps` nhỏ làm n tụt xuống vài chục thì ĐỪNG trích p-value ra
    ngoài — nó không còn đáng tin, và hàm này không biết tự từ chối.
    """
    if not n1 or not n2:
        return (0.0, 1.0)
    p1, p2 = k1 / n1, k2 / n2
    gop = (k1 + k2) / (n1 + n2)
    se = math.sqrt(gop * (1 - gop) * (1 / n1 + 1 / n2))
    if se == 0:
        return (0.0, 1.0)
    z = (p1 - p2) / se
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return (z, p)


def lenh_ab_refusal(cfg: Config, prompt: str, args) -> int:
    """Việc 12: câu từ chối HẰNG SỐ (A) hay XOAY VÒNG (B)?

    §4 đo được hiệu ứng lịch sử đi NGƯỢC giả thuyết ADR-008 (p = 0,0026) và truy
    nguyên nhân về chính thiết kế của ta: `LOOKUP_REFUSAL` là hằng số, lưu nguyên
    văn, nên sau ba lượt đệm CẦN TRA thì lịch sử chứa ba câu giống hệt nhau, và áp
    lực chống lặp chữ đẩy model tránh gắn nhãn lần thứ tư.

    Phép thử cô lập đúng biến đó: cùng bộ câu, cùng ba vị trí lịch sử của việc 5c,
    chỉ đổi một thứ — số biến thể của câu từ chối. Nhánh A là nhánh B khoá ở chỉ
    số 0, nên hai nhánh không chênh nhau cả cách diễn đạt.

    Nếu nhánh B làm hiệu ứng biến mất thì đã cô lập được nguyên nhân, và ĐÓ LÀ
    PHÁT HIỆN: một chi tiết cài đặt tưởng vô hại làm lệch hẳn hành vi định tuyến.
    """
    bo = [r for r in doc_bo()
          if r["block"] == "A" and r["needs_lookup"] and r["fact_type"] == "fast-changing"]
    bo = bo[: args.limit or 20]
    vi_tri = [("dau-phien", []), ("sau-3-khong-tra", DEM_KHONG_TRA), ("sau-3-co-tra", DEM_CAN_TRA)]
    nhanh = [("A-hang-so", False), ("B-xoay-vong", True)]
    print(f"A/B câu từ chối: {len(bo)} câu × {len(vi_tri)} vị trí × {len(nhanh)} nhánh"
          f" × {args.reps} lần")

    cuc_bo = threading.local()
    viec = [(row, ten_vt, dem, ten_nh, xoay, lan)
            for ten_nh, xoay in nhanh
            for ten_vt, dem in vi_tri
            for row in bo
            for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, ten_vt, dem, ten_nh, xoay, lan = item
        khoa = f"vit_{ten_nh}"
        vit = getattr(cuc_bo, khoa, None)
        if vit is None:
            vit = Vit(cfg, prompt, temperature=None, varied_phrases=xoay)
            setattr(cuc_bo, khoa, vit)
        vit.quen()                                   # đặt lại cả lịch sử lẫn bộ đếm
        for cau in dem:                              # dựng lịch sử THẬT, không nhồi giả
            vit.hoi(cau, row["lang"])
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "position": ten_vt,
                "branch": ten_nh, "varied": xoay, "rep": lan,
                "lookup": ra["lookup"], "reply": ra["reply"][:160]}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]
    ghi(BENCH_DIR / f"lookup_ab_refusal_{date.today():%Y%m%d}_v1.jsonl", rows)
    bao_cao_ab(rows, [t for t, _ in vi_tri], [t for t, _ in nhanh])
    return 0


def bao_cao_ab(rows: list[dict], vi_tri: list[str], nhanh: list[str]) -> None:
    def o(br: str, vt: str) -> tuple[int, int]:
        con = [r for r in rows if r["branch"] == br and r["position"] == vt]
        return sum(1 for r in con if r["lookup"]), len(con)

    print("\n=== tỉ lệ gắn nhãn: NHÁNH × VỊ TRÍ ===")
    print(f"  {'vị trí':<20}" + "".join(f"{br:>22}" for br in nhanh))
    for vt in vi_tri:
        dong = f"  {vt:<20}"
        for br in nhanh:
            k, n = o(br, vt)
            dong += f"{k:>6}/{n:<3} = {k / n * 100 if n else 0:5.1f} %" if n else f"{'—':>22}"
        print(dong)

    print("\n=== TRONG từng nhánh: hiệu ứng lịch sử còn không? ===")
    print("  (phép so duy nhất có ý nghĩa ở §4 là sau-3-không-tra vs sau-3-có-tra)")
    for br in nhanh:
        k1, n1 = o(br, "sau-3-khong-tra")
        k2, n2 = o(br, "sau-3-co-tra")
        z, p = z_hai_ti_le(k1, n1, k2, n2)
        ket = "CÓ ý nghĩa" if p < 0.05 else "không kết luận được"
        print(f"  {br:<14} {k1}/{n1} vs {k2}/{n2}   z = {z:+.3f}   p = {p:.4f}   {ket}")
        lo1, hi1 = wilson(k1, n1)
        lo2, hi2 = wilson(k2, n2)
        print(f"                 Wilson 95%: {lo1:.3f}–{hi1:.3f}  vs  {lo2:.3f}–{hi2:.3f}")

    print("\n=== GIỮA hai nhánh, cùng vị trí ===")
    for vt in vi_tri:
        k1, n1 = o(nhanh[0], vt)
        k2, n2 = o(nhanh[1], vt)
        z, p = z_hai_ti_le(k1, n1, k2, n2)
        print(f"  {vt:<20} A {k1}/{n1} vs B {k2}/{n2}   z = {z:+.3f}   p = {p:.4f}")

    print("\nĐọc kết quả:")
    print("  - B làm p ở 'sau-3-có-tra' mất ý nghĩa  -> đã cô lập được nguyên nhân"
          " là CÂU HẰNG SỐ, không phải bắt chước nhãn. Đó là phát hiện.")
    print("  - hiệu ứng còn nguyên ở cả hai nhánh    -> nguyên nhân nằm chỗ khác;"
          " giả thuyết né-lặp-chữ ở §4.1 SAI, phải ghi lại là sai.")
    print("  - CHƯA đổi mặc định sang B ở đây. Đo xong rồi mới quyết (ADR-012 §4.2).")



# -- việc 17: lưới 2x2 ngôn ngữ quy tắc x ngôn ngữ câu hỏi ---------------------


def lenh_rule_lang(cfg: Config, prompt: str, args) -> int:
    """Quy tắc `[lookup]` viết bằng tiếng gì thì định tuyến tiếng ấy tốt hơn?

    Chênh lệch phải giải thích: recall tiếng Anh 0,520 so với tiếng Việt 0,920
    (Bảng 2). Giả thuyết: quy tắc viết bằng tiếng Việt nên bị át ở lượt tiếng Anh —
    đúng cơ chế ADR-008, nơi lịch sử tiếng Anh thắng system prompt tiếng Việt.

    **Chạy lại nửa tiếng Anh thôi thì không kết luận được gì.** Hai lời giải thích
    khác hẳn nhau cùng khớp dữ liệu: "quy tắc hợp ngôn ngữ thì ăn" và "câu tiếng Anh
    vốn khó hơn". Phân biệt chúng cần ô thứ tư, và ô QUYẾT ĐỊNH là **quy tắc tiếng
    Anh × câu hỏi tiếng Việt**: giả thuyết đúng thì recall tiếng Việt phải TỤT ở đó.
    Nếu tiếng Việt vẫn 0,92 trong khi tiếng Anh lên, thì cái ăn thua là ngôn ngữ của
    CÂU HỎI chứ không phải sự hợp nhau giữa hai bên.

    Chạy CẢ BỐN ô trong cùng một mẻ, kể cả hai ô đã có số. Bảng 2 đo hôm khác, ở
    temperature 0,8 với flip rate 3,30 % (Bảng 5) — ghép số cũ vào lưới mới là để
    trôi dạt giữa hai lần chạy đội lốt hiệu ứng. Hai ô cũ ở đây làm ĐỐI CHỨNG: chúng
    phải ra gần 0,920 và 0,520, không thì cả lưới không dùng được.
    """
    from brain.persona import doi_ngon_ngu_quy_tac_lookup, duong_dan_quy_tac

    ban = [x.strip() for x in args.rules.split(",") if x.strip()]
    if "vi" not in ban:
        raise SystemExit("Phải có `vi` trong --rules: nó là ĐỐI CHỨNG, không phải một ô tuỳ chọn.")
    quy_tac = {"vi": prompt}
    for rl in ban:
        if rl == "vi":
            continue
        moi_prompt = doi_ngon_ngu_quy_tac_lookup(
            prompt, duong_dan_quy_tac(cfg.persona_path.parent, rl))
        if moi_prompt == prompt:
            raise SystemExit(f"Quy tắc {rl} không đổi gì — kiểm lại file quy tắc.")
        quy_tac[rl] = moi_prompt

    bo = [r for r in doc_bo() if r["block"] == "A"]
    if args.lang:
        # Chỉ một nửa ngôn ngữ. Dùng khi cần dồn reps vào đúng chỗ đang tranh chấp
        # thay vì trải mỏng đều — khoảng cách phải phân giải ở đây bé hơn độ trôi
        # giữa hai lần chạy, nên cỡ mẫu mới là thứ quyết định (ADR-012 §5.1).
        bo = [r for r in bo if r["lang"] == args.lang]
    if args.limit:
        bo = bo[: args.limit]
    print(f"Lưới ngôn ngữ: {len(bo)} câu × {len(ban)} bản quy tắc ({', '.join(ban)})"
          f" × {args.reps} lần = {len(bo) * len(ban) * args.reps} lượt")

    cuc_bo = threading.local()
    viec = [(row, rl, lan) for rl in ban for row in bo for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, rl, lan = item
        kho = getattr(cuc_bo, "kho", None)
        if kho is None:
            kho = cuc_bo.kho = {}
        vit = kho.get(rl)
        if vit is None:
            vit = kho[rl] = Vit(cfg, quy_tac[rl], temperature=None)
        vit.quen()
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "rule_lang": rl, "rep": lan,
                "fact_type": row["fact_type"], "needs_lookup": row["needs_lookup"],
                "lookup": ra["lookup"], "reply": ra["reply"][:160]}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]
    ver = "v2" if "vi-v2" in ban else "v1"
    ghi(BENCH_DIR / f"lookup_rule_lang_{date.today():%Y%m%d}_{ver}.jsonl", rows)

    def recall(rl: str, ql: str) -> tuple[int, int]:
        con = [r for r in rows if r["rule_lang"] == rl and r["lang"] == ql and r["needs_lookup"]]
        return sum(1 for r in con if r["lookup"]), len(con)

    NHAN = {"vi": "quy tắc vi (gốc)", "en": "quy tắc en", "vi-v2": "quy tắc vi-v2"}

    def gop(rl: str) -> tuple[int, int]:
        con = [r for r in rows if r["rule_lang"] == rl and r["needs_lookup"]]
        return sum(1 for r in con if r["lookup"]), len(con)

    print("\n=== LƯỚI — recall (câu CẦN tra mà có gắn nhãn) ===")
    print(f"  {'':<20}{'câu tiếng Việt':<28}{'câu tiếng Anh':<28}gộp")
    for rl in ban:
        o = []
        for ql in ("vi", "en"):
            k, n = recall(rl, ql)
            lo, hi = wilson(k, n)
            o.append(f"{k}/{n} = {k / n:.3f} [{lo:.3f}-{hi:.3f}]" if n else "—")
        kg, ng = gop(rl)
        kv, nv = recall(rl, "vi")
        ke, ne = recall(rl, "en")
        # `--lang` chỉ chạy một nửa -> không có "chênh hai nửa" để mà tính. In `nan`
        # vào bảng là mời người đọc sau tưởng phép đo hỏng.
        duoi = (f"   (chênh hai nửa {abs(kv / nv - ke / ne):.3f})" if nv and ne else "")
        print(f"  {NHAN.get(rl, rl):<20}{o[0]:<28}{o[1]:<28}{kg / ng:.3f}{duoi}")

    print("\n  đối chứng với Bảng 2 (phải khớp, không thì lưới không dùng được):")
    for ql, cu in (("vi", 0.920), ("en", 0.520)):
        k, n = recall("vi", ql)
        if n:
            print(f"    quy tắc vi × câu {ql}: {k / n:.3f} so với {cu:.3f} đã công bố"
                  f"   lệch {k / n - cu:+.3f}")

    if "vi-v2" in ban and "en" in ban:
        print("\n  === VIỆC 21: vi-v2 nghiêng về bản nào? ===")
        print("  (A) model tuân chỉ thị TIẾNG ANH giỏi hơn  -> vi-v2 phải giống bản vi gốc")
        print("  (B) bản tiếng Việt của ta viết chưa chuẩn  -> vi-v2 phải giống bản en")
        for ql in ("vi", "en"):
            k2, n2 = recall("vi-v2", ql)
            kv, nv = recall("vi", ql)
            ke, ne = recall("en", ql)
            if not (n2 and nv and ne):
                continue
            d_vi, d_en = abs(k2 / n2 - kv / nv), abs(k2 / n2 - ke / ne)
            gan = "bản vi gốc -> (A)" if d_vi < d_en else (
                "bản en -> (B)" if d_en < d_vi else "CÁCH ĐỀU hai bản — lưng chừng")
            print(f"    câu {ql}: vi-v2 {k2 / n2:.3f}   |  vi {kv / nv:.3f} (cách {d_vi:.3f})"
                  f"   en {ke / ne:.3f} (cách {d_en:.3f})   -> gần {gan}")
            z1, p1 = z_hai_ti_le(k2, n2, kv, nv)
            z2, p2v = z_hai_ti_le(k2, n2, ke, ne)
            print(f"             vi-v2 vs vi: z {z1:+.3f} p {p1:.4f}"
                  f"   |  vi-v2 vs en: z {z2:+.3f} p {p2v:.4f}")
        print("  Cả hai phép so đều KHÔNG có ý nghĩa, hoặc CẢ HAI đều có -> kết quả"
              " LƯNG CHỪNG.\n  Lúc đó BÁO CHỦ NHÂN, đừng tự chọn cách diễn giải"
              " (điểm dừng của đợt 4).")

    kv, nv = recall("vi", "vi")
    ke, ne = recall("en", "vi") if "en" in ban else (0, 0)
    if nv and ne:
        z, pgt = z_hai_ti_le(kv, nv, ke, ne)
        print(f"\n  Ô QUYẾT ĐỊNH — câu tiếng Việt, đổi quy tắc vi→en:"
              f" {kv / nv:.3f} → {ke / ne:.3f}   z {z:+.3f}   p {pgt:.4f}")
        print("    TỤT có ý nghĩa  -> quy tắc hợp ngôn ngữ mới ăn; đúng cơ chế ADR-008.")
        print("    KHÔNG tụt       -> cái ăn thua là ngôn ngữ CÂU HỎI, không phải sự hợp nhau;")
        print("                       giả thuyết bị bác, và đó cũng là một kết quả.")
    ka, na = recall("vi", "en")
    kb, nb = recall("en", "en") if "en" in ban else (0, 0)
    if na and nb:
        z, pgt = z_hai_ti_le(ka, na, kb, nb)
        print(f"  Ô đối xứng     — câu tiếng Anh, đổi quy tắc vi→en:"
              f" {ka / na:.3f} → {kb / nb:.3f}   z {z:+.3f}   p {pgt:.4f}")

    print("\n  precision (kèm để thấy có phải chỉ đang gắn nhãn bừa nhiều hơn không):")
    for rl in ban:
        for ql in ("vi", "en"):
            con = [r for r in rows if r["rule_lang"] == rl and r["lang"] == ql]
            dd = sum(1 for r in con if r["needs_lookup"] and r["lookup"])
            sd = sum(1 for r in con if not r["needs_lookup"] and r["lookup"])
            if dd + sd:
                print(f"    quy tắc {rl} × câu {ql}: {dd / (dd + sd):.3f}"
                      f"   (đúng-dương {dd}, sai-dương {sd})")
    return 0


# -- việc 18: cơ chế hiệu ứng lịch sử, bằng lượt trung tính -------------------


def lenh_history_neutral(cfg: Config, prompt: str, args) -> int:
    """Hiệu ứng lịch sử là do ĐỘ DÀI lịch sử hay do NỘI DUNG câu từ chối?

    Hạn chế số 7 của outline: hiệu ứng tái lập được (Bảng 6) nhưng chưa truy ra cơ
    chế. Giả thuyết "áp lực chống lặp chữ" đã bị A/B bác bỏ (Bảng 7) — xoay vòng câu
    từ chối còn làm hiệu ứng MẠNH thêm, ngược hẳn chiều dự đoán.

    Phép thử tách được hai lời giải thích còn lại: **đổi độ dài lịch sử bằng lượt
    trung tính**, giữ nguyên nội dung. Lượt trung tính không cần tra và không sinh
    câu từ chối, nên nếu tỉ lệ gắn nhãn vẫn tụt theo độ dài thì nguyên nhân là VỊ TRÍ
    chứ không phải nội dung.

    - Tụt theo độ dài  -> **pha loãng theo vị trí**: lịch sử càng dài, chỉ thị trong
      system prompt càng yếu. Đúng cơ chế ADR-008, và cách chữa đã biết sẵn — kẹp chỉ
      thị vào lượt NGƯỜI DÙNG chứ không chỉ để ở system prompt.
    - Phẳng theo độ dài -> do nội dung lượt trước; lúc đó mới đi tìm tiếp.

    Một phép thử, hai nhánh đều cho kết luận, nên chạy nó là đáng dù ra chiều nào.

    Chạy kèm hai mốc của Bảng 6 (`dau-phien` và `sau-3-co-tra`) trong CÙNG một mẻ.
    Không có chúng thì mọi so sánh đều là so với số đo hôm khác, và ở temperature 0,8
    thì trôi dạt giữa hai lần chạy đủ to để bịa ra một hiệu ứng.
    """
    # `--negatives`: đối chứng bắt buộc. Đo trên câu CẦN tra thì "lịch sử dài làm tỉ
    # lệ gắn nhãn lên" có hai lời giải thích — định tuyến TỐT hơn, hoặc vịt gắn nhãn
    # BỪA cho mọi thứ. Chỉ nhìn nửa dương thì không phân biệt được. Chạy lại đúng bộ
    # vị trí ấy trên câu never-changing: sai-dương mà cũng lên thì đó là gắn bừa.
    if args.negatives:
        bo = [r for r in doc_bo()
              if r["block"] == "A" and not r["needs_lookup"] and r["fact_type"] == "never-changing"]
    else:
        bo = [r for r in doc_bo()
              if r["block"] == "A" and r["needs_lookup"] and r["fact_type"] == "fast-changing"]
    bo = bo[: args.limit or 20]

    do_dai = [int(x) for x in args.lengths.split(",") if x.strip()]
    if do_dai and max(do_dai) > len(DEM_TRUNG_TINH):
        raise SystemExit(f"Chỉ có {len(DEM_TRUNG_TINH)} lượt trung tính, xin {max(do_dai)}.")
    # Ba mốc của Bảng 6 luôn chạy cùng mẻ. `sau-3-khong-tra` có mặt vì Bảng 6 thiếu
    # đúng ô sai-dương của nó: hai mốc kia đã có nửa âm từ việc 18, riêng nó thì chưa,
    # và một bảng ba dòng mà chỉ hai dòng có cột sai-dương thì không đọc được.
    vi_tri: list[tuple[str, list[str]]] = [("dau-phien", [])]
    vi_tri += [(f"{n}-trung-tinh", DEM_TRUNG_TINH[:n]) for n in do_dai if n]
    vi_tri += [("sau-3-khong-tra", DEM_KHONG_TRA), ("sau-3-co-tra", DEM_CAN_TRA)]

    goi = sum(len(dem) + 1 for _, dem in vi_tri) * len(bo) * args.reps
    print(f"Cơ chế hiệu ứng lịch sử: {len(bo)} câu × {len(vi_tri)} vị trí × {args.reps}"
          f" lần ≈ {goi} lời gọi (đã tính cả lượt đệm)")

    cuc_bo = threading.local()
    viec = [(row, ten, dem, lan) for ten, dem in vi_tri for row in bo for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, ten, dem, lan = item
        vit = getattr(cuc_bo, "vit", None)
        if vit is None:
            vit = cuc_bo.vit = Vit(cfg, prompt, temperature=None)
        vit.quen()
        for cau in dem:                              # dựng lịch sử THẬT, không giả
            vit.hoi(cau, row["lang"])
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "position": ten,
                "n_dem": len(dem), "trung_tinh": ten.endswith("trung-tinh"), "rep": lan,
                "needs_lookup": row["needs_lookup"], "fact_type": row["fact_type"],
                "lookup": ra["lookup"], "reply": ra["reply"][:160]}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]
    duoi = "_am" if args.negatives else ""
    ghi(BENCH_DIR / f"lookup_history_neutral{duoi}_{date.today():%Y%m%d}_v1.jsonl", rows)

    nhan_bang = ("tỉ lệ gắn nhãn SAI (câu never-changing) theo ĐỘ DÀI lịch sử"
                 if args.negatives else "tỉ lệ gắn nhãn theo ĐỘ DÀI lịch sử")
    print(f"\n=== {nhan_bang} ===")
    for ten, _ in vi_tri:
        con = [r for r in rows if r["position"] == ten]
        if not con:
            continue
        gan = sum(1 for r in con if r["lookup"])
        lo, hi = wilson(gan, len(con))
        print(f"  {ten:<20} n={len(con):<4} {gan}/{len(con)} = {gan / len(con) * 100:5.1f} %"
              f"   [Wilson 95% {lo:.3f}-{hi:.3f}]")

    def o(ten: str) -> tuple[int, int]:
        con = [r for r in rows if r["position"] == ten]
        return sum(1 for r in con if r["lookup"]), len(con)

    dai = [t for t, _ in vi_tri if t.endswith("trung-tinh")]
    if dai and o("dau-phien")[1]:
        k0, n0 = o("dau-phien")
        print("\n  so với lượt đầu (chỉ đổi ĐỘ DÀI, nội dung trung tính):")
        for ten in dai:
            k, n = o(ten)
            if n0 and n:
                z, pgt = z_hai_ti_le(k0, n0, k, n)
                print(f"    {ten:<18} {k0 / n0:.3f} → {k / n:.3f}   z {z:+.3f}   p {pgt:.4f}")
        kc, nc = o("sau-3-co-tra")
        kt, nt = o(dai[0])
        if nc and nt:
            z, pgt = z_hai_ti_le(kt, nt, kc, nc)
            print(f"\n  cùng ĐỘ DÀI {dai[0].split('-')[0]}, đổi NỘI DUNG"
                  f" (trung tính → có từ chối): {kt / nt:.3f} → {kc / nc:.3f}"
                  f"   z {z:+.3f}   p {pgt:.4f}")
    print("\n  Tụt theo độ dài  -> pha loãng theo vị trí; chữa bằng cách kẹp chỉ thị ở"
          " LƯỢT NGƯỜI DÙNG (ADR-008).\n  Phẳng theo độ dài -> do nội dung lượt trước;"
          " đi tìm tiếp ở đó.")

    print("\n  === ba mốc của Bảng 6, chép thẳng vào tài liệu ===")
    for ten in ("dau-phien", "sau-3-khong-tra", "sau-3-co-tra"):
        k, n = o(ten)
        if n:
            lo, hi = wilson(k, n)
            print(f"    {ten:<18} {k}/{n} = {k / n * 100:5.1f} %   [Wilson {lo:.3f}-{hi:.3f}]")
    return 0


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="lenh", required=True)
    for ten in ("accuracy", "determinism", "history", "ab-refusal",
                "rule-lang", "history-neutral"):
        p = sub.add_parser(ten)
        p.add_argument("--reps", type=int, default=10)
        p.add_argument("--limit", type=int, default=0, help="chỉ lấy N câu đầu (chạy thử)")
        if ten == "rule-lang":
            p.add_argument("--lang", default="", choices=("", "vi", "en"),
                           help="chỉ chạy nửa ngôn ngữ này (mặc định: cả hai)")
            p.add_argument("--rules", default="vi,en",
                           help="các bản quy tắc đem so, cách nhau dấu phẩy; "
                                "`vi` bắt buộc có vì nó là đối chứng "
                                "(vd: vi,en,vi-v2 cho việc 21)")
        if ten == "history-neutral":
            p.add_argument("--lengths", default="3,6,9",
                           help="số lượt trung tính chèn vào, cách nhau dấu phẩy")
            p.add_argument("--negatives", action="store_true",
                           help="đối chứng: chạy trên câu never-changing, đo SAI-DƯƠNG")

    args = parser.parse_args()
    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY trong ..\\.env")
        return 1
    prompt = load_persona(cfg.persona_path).system_prompt()

    return {"accuracy": lenh_accuracy,
            "determinism": lenh_determinism,
            "history": lenh_history,
            "ab-refusal": lenh_ab_refusal,
            "rule-lang": lenh_rule_lang,
            "history-neutral": lenh_history_neutral}[args.lenh](cfg, prompt, args)


if __name__ == "__main__":
    raise SystemExit(main())
