r"""Đo giá phải trả của grounding hai pha (việc 10, ADR-010 §3.1).

    python scripts\bench_grounding.py --limit 12

Chạy với **LLM_SEARCH bật cứng trong chính script này**, không đọc .env: bộ số này
phải so được với bộ cũ, mà bộ cũ đo ở trạng thái tắt. Ai chạy cũng ra cùng điều kiện.

## Hai loại lượt, KHÔNG được gộp trung bình

Phân bố lưỡng cực, và gộp là xoá mất chính phát hiện:

- **lượt thường** — một lời gọi, 5 function tool, ~1 s tới chữ đầu;
- **lượt có `[lookup]`** — thêm một lời gọi thứ hai chỉ có `google_search`, ~4-5 s.

Ba mốc của lượt có tra, đo từ lúc LLM bắt đầu lượt:

    t_llm_first     chữ đầu của pha một (nhãn [lookup] nằm ở đây)
    t_wait          câu báo trước xuống TTS  — người dùng NGHE THẤY vịt ở đây
    t_answer_first  chữ đầu của câu trả lời thật, sau khi pha hai về

`search_ms` là RIÊNG lời gọi thứ hai, đo trong `_ground()`. Nó CHỒNG LÊN thời gian
phát câu báo trước, nên `t_answer_first` < `t_wait + search_ms` là chuyện bình
thường và chính là điều ta muốn thấy.

Không ghi vào `logs/latency.jsonl` chính, không đụng `docs/baseline/`.
"""

from __future__ import annotations

import argparse
import json
import queue
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.persona import load_persona
from config import Config, enable_utf8_console
from handlers.llm_gemini import LOOKUP_WAIT, GeminiLLMHandler
from latency import LatencyTracker
from speech_to_speech.pipeline.messages import Transcription, TTSInput

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
SET_PATH = BENCH_DIR / "lookup_set_v1.jsonl"

# Thấp hơn bench_routing (6): mỗi lượt có tra là HAI request, và grounding có hạn
# mức riêng (1 500 lượt/ngày miễn phí, ADR-010 §4). Không đua với hạn mức.
WORKERS = 3


def doc_bo() -> list[dict]:
    if not SET_PATH.exists():
        raise SystemExit(f"Chưa có {SET_PATH}. Chạy scripts\\build_lookup_set.py trước.")
    return [json.loads(line) for line in SET_PATH.read_text(encoding="utf-8").splitlines() if line]


class Vit:
    """Một con vịt chỉ có não. `search` quyết định có bật pha hai hay không."""

    def __init__(self, cfg: Config, prompt: str, search: bool) -> None:
        self.tracker = LatencyTracker(path=None, echo=False)
        self.handler = GeminiLLMHandler(
            threading.Event(), queue_in=queue.Queue(), queue_out=queue.Queue(),
            setup_kwargs={
                "api_key": cfg.gemini_api_key,
                "model": cfg.gemini_model,
                "system_prompt": prompt,
                "tracker": self.tracker,
                "search_enabled": search,
            },
        )

    def hoi(self, text: str, lang: str) -> dict[str, Any]:
        """Một lượt. Đánh dấu `t_wait` ngay lúc câu báo trước ra khỏi generator."""
        self.tracker.start_turn()
        bat_dau = perf_counter()
        t_wait: float | None = None
        cau: list[str] = []
        for out in self.handler.process(Transcription(text=text, language_code=lang)):
            if not isinstance(out, TTSInput):
                continue
            if t_wait is None and out.text in LOOKUP_WAIT.values():
                t_wait = (perf_counter() - bat_dau) * 1000.0
            cau.append(out.text)
        record = self.tracker.finish() or {}
        return {
            "lookup": bool(record.get("lookup_flagged")),
            "premise": bool(record.get("premise_flagged")),
            "grounded": bool(record.get("grounded")),
            "search_ms": record.get("search_ms"),
            "search_sources": record.get("search_sources"),
            "t_llm_first": record.get("t_llm_first"),
            "t_answer_first": record.get("t_answer_first"),
            "t_wait": round(t_wait, 1) if t_wait is not None else None,
            "llm_total_ms": round((perf_counter() - bat_dau) * 1000.0, 1),
            "reply": " ".join(cau),
        }

    def quen(self) -> None:
        self.handler.on_session_end()


def chay_song_song(viec: list[Any], lam, nhan: str) -> list[Any]:
    xong = [0]
    khoa = threading.Lock()

    def boc(item):
        try:
            ket_qua = lam(item)
        except Exception as exc:
            ket_qua = {"error": f"{type(exc).__name__}: {exc}"}
        with khoa:
            xong[0] += 1
            if xong[0] % 5 == 0 or xong[0] == len(viec):
                print(f"  {nhan}: {xong[0]}/{len(viec)}")
        return ket_qua

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(boc, viec))


def pxx(values: list[float], q: float) -> float | None:
    """Phân vị theo phương pháp gần nhất. n nhỏ nên KHÔNG nội suy — nội suy ở
    n = 12 là bịa ra độ mịn không có thật."""
    if not values:
        return None
    xep = sorted(values)
    return xep[min(len(xep) - 1, max(0, round(q * (len(xep) - 1))))]


def bang(ten: str, values: list[float]) -> None:
    if not values:
        print(f"  {ten:<24} (không có lượt nào)")
        return
    print(f"  {ten:<24} n={len(values):<3} p50 {pxx(values, 0.5):7.0f}   "
          f"p95 {pxx(values, 0.95):7.0f}   min {min(values):7.0f}   max {max(values):7.0f}"
          f"   tb {statistics.mean(values):7.0f}")


def main() -> int:
    enable_utf8_console()
    from mrunner.khoa_grounding import chan_neu_m3   # cửa sổ M3: hạn grounding dùng chung
    chan_neu_m3(Path(__file__).name)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=12, help="số câu MỖI loại")
    parser.add_argument("--reps", type=int, default=1)
    args = parser.parse_args()

    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY trong ..\\.env")
        return 1
    prompt = load_persona(cfg.persona_path).system_prompt()

    bo = doc_bo()
    # "Có tra": fast-changing, đã gán nhãn tay là cần tra. "Không tra":
    # never-changing. Hai cụm tách bạch có chủ ý — đây là phép đo ĐỘ TRỄ, không
    # phải phép đo độ chính xác của bộ định tuyến (cái đó ở bench_routing).
    def chon(fact_type: str, needs: bool) -> list[dict]:
        """Lấy `--limit` câu, CÂN HAI NGÔN NGỮ. Bộ câu xếp en trước vi, nên cắt
        thẳng `[:limit]` cho ra một mẻ toàn tiếng Anh — và số đo grounding tiếng
        Việt là thứ ta cần nhất, vì đó mới là ngôn ngữ chính của vịt."""
        theo_lang = {
            lang: [r for r in bo if r["block"] == "A" and r["lang"] == lang
                   and r["needs_lookup"] is needs and r["fact_type"] == fact_type]
            for lang in ("vi", "en")
        }
        ra: list[dict] = []
        for i in range(max(len(v) for v in theo_lang.values())):
            for lang in ("vi", "en"):
                if i < len(theo_lang[lang]) and len(ra) < args.limit:
                    ra.append(theo_lang[lang][i])
        return ra

    co_tra = chon("fast-changing", True)
    khong_tra = chon("never-changing", False)
    print(f"Grounding hai pha: {len(co_tra)} câu CÓ tra + {len(khong_tra)} câu KHÔNG tra"
          f" × {args.reps} lần, {WORKERS} luồng")

    cuc_bo = threading.local()
    viec = [(row, lan) for row in co_tra + khong_tra for lan in range(args.reps)]

    def mot_luot(item) -> dict:
        row, lan = item
        vit = getattr(cuc_bo, "vit", None)
        if vit is None:
            vit = cuc_bo.vit = Vit(cfg, prompt, search=True)
        vit.quen()                                   # lịch sử RỖNG cho từng câu
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "lang": row["lang"], "fact_type": row["fact_type"],
                "needs_lookup": row["needs_lookup"], "rep": lan, **ra,
                "ts": datetime.now(timezone.utc).astimezone().isoformat()}

    rows = [r for r in chay_song_song(viec, mot_luot, "lượt") if "error" not in r]

    out = BENCH_DIR / f"grounding_{date.today():%Y%m%d}_v1.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nGhi {len(rows)} bản ghi vào {out}")

    tra = [r for r in rows if r["grounded"]]
    thuong = [r for r in rows if not r["grounded"]]

    def lay(rows_: list[dict], key: str) -> list[float]:
        return [r[key] for r in rows_ if r.get(key) is not None]

    print(f"\n=== LƯỢT CÓ TRA (n={len(tra)}) — hai lời gọi ===")
    bang("lời gọi thứ hai", lay(tra, "search_ms"))
    bang("t_llm_first (pha 1)", lay(tra, "t_llm_first"))
    bang("t_wait (nghe thấy vịt)", lay(tra, "t_wait"))
    bang("t_answer_first", lay(tra, "t_answer_first"))
    bang("tổng tầng LLM", lay(tra, "llm_total_ms"))
    nguon = lay(tra, "search_sources")
    if nguon:
        print(f"  nguồn trả về mỗi lượt: p50 {pxx(nguon, 0.5):.0f}   "
              f"min {min(nguon):.0f}   max {max(nguon):.0f}")

    print(f"\n=== LƯỢT KHÔNG TRA (n={len(thuong)}) — một lời gọi, giữ 5 tool ===")
    bang("t_llm_first", lay(thuong, "t_llm_first"))
    bang("tổng tầng LLM", lay(thuong, "llm_total_ms"))

    a = pxx(lay(tra, "t_answer_first"), 0.5)
    b = pxx(lay(thuong, "t_llm_first"), 0.5)
    if a and b:
        print(f"\nGIÁ PHẢI TRẢ (p50, tới chữ đầu của câu TRẢ LỜI): "
              f"{a:.0f} ms so với {b:.0f} ms = +{a - b:.0f} ms, {a / b:.1f}×")
    c = pxx(lay(tra, "t_wait"), 0.5)
    if c and b:
        print(f"NHƯNG người dùng NGHE THẤY vịt ở {c:.0f} ms (câu báo trước), "
              f"so với {b:.0f} ms của lượt thường = +{c - b:.0f} ms")
    print("\nHai dòng trên là hai câu chuyện khác nhau về CÙNG một lượt. Báo cả hai."
          "\nĐừng lấy trung bình chung với lượt thường: phân bố lưỡng cực.")

    lac = [r for r in rows if r["needs_lookup"] != r["lookup"]]
    if lac:
        print(f"\n(Định tuyến lệch nhãn tay ở {len(lac)}/{len(rows)} lượt — đó là phép đo"
              f" của bench_routing, ở đây chỉ ghi nhận vì nó đổi cỡ mẫu hai nhóm.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
