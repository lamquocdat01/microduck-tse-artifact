r"""Câu vừa cần KÝ ỨC vừa cần TIN MỚI — hai pha xử lý thật ra sao (việc 1.5, ADR-010 §3.4).

    desktop\.venv\Scripts\python.exe desktop\scripts\probe_cau_kep.py --reps 5

"tôi tên gì, và giá vàng hôm nay thế nào". Pha hai của grounding CHỈ có `google_search`
(API cấm trộn với function calling), nên nó không gọi được `recall`. Test ngoại tuyến
đã chốt phần CƠ CHẾ (pha hai mang khối MEMORY của system prompt, không mang kết quả tool
của pha một). Script này đo phần HÀNH VI: model thật làm gì với câu ấy.

Hai điều kiện, cùng câu, cùng persona thật (duck.md, có ghi chú tra cứu theo cờ):

    A  tên NẰM trong khối MEMORY của system prompt      (đường thường của pipeline)
    B  tên KHÔNG có trong MEMORY, chỉ `recall` trả được (ký ức ngoài top-k)

Đối chứng âm (luật dự án): cùng câu, LLM_SEARCH TẮT, điều kiện A — để biết "nói được
tên" là nhờ khối MEMORY chứ không phải model đoán bừa.

Ghi `docs/benchmark/cau_kep_20260913_v1.jsonl`. Không ghi latency.jsonl chính.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.persona import load_persona  # noqa: E402
from brain.tools import tool_declarations  # noqa: E402
from config import Config, enable_utf8_console  # noqa: E402
from handlers.llm_gemini import LOOKUP_FAILED, LOOKUP_REFUSAL, LOOKUP_WAIT, GeminiLLMHandler  # noqa: E402
from latency import LatencyTracker  # noqa: E402
from speech_to_speech.pipeline.messages import Transcription, TTSInput  # noqa: E402

REPO_DIR = Path(__file__).resolve().parents[2]
OUT = REPO_DIR / "docs" / "benchmark" / "cau_kep_20260913_v1.jsonl"

TEN = "Đạt"
KY_UC = f"- Chủ nhân tên là {TEN} (chắc 0,9)"
CAU = {
    "vi": "Tôi tên gì, và giá vàng hôm nay thế nào?",
    "en": "What's my name, and what's the gold price today?",
}


def mot_luot(cfg: Config, persona, dieu_kien: str, lang: str, search: bool) -> dict[str, Any]:
    goi_tool: list[str] = []

    def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
        goi_tool.append(name)
        if name == "recall":
            return {"ok": True, "facts": [{"text": f"Chủ nhân tên là {TEN}", "confidence": 0.9}]}
        return {"ok": True}

    memory = KY_UC if dieu_kien == "A" else ""
    prompt = persona.system_prompt(("MEMORY", memory))
    tracker = LatencyTracker(path=None, echo=False)
    handler = GeminiLLMHandler(
        threading.Event(), queue_in=queue.Queue(), queue_out=queue.Queue(),
        setup_kwargs={
            "api_key": cfg.gemini_api_key, "model": cfg.gemini_model,
            "system_prompt": prompt, "tracker": tracker,
            "tools": tool_declarations(), "tool_dispatch": dispatch,
            "search_enabled": search, "search_timeout_s": cfg.llm_search_timeout_s,
            "search_notes": {True: persona.search_on, False: persona.search_off},
        },
    )
    tracker.start_turn()
    cau = [o.text for o in handler.process(Transcription(text=CAU[lang], language_code=lang))
           if isinstance(o, TTSInput)]
    rec = tracker.finish() or {}
    tra_loi = " ".join(t for t in cau if t not in LOOKUP_WAIT.values())
    return {
        "dieu_kien": dieu_kien, "lang": lang, "search_enabled": search,
        "tools_called": goi_tool,
        "lookup_flagged": bool(rec.get("lookup_flagged")),
        "grounded": bool(rec.get("grounded")),
        "search_timeout": bool(rec.get("search_timeout")),
        "search_sources": rec.get("search_sources"),
        "search_ms": rec.get("search_ms"),
        # "Dat" không dấu cho câu tiếng Anh: model hay bỏ dấu tên riêng khi nói tiếng Anh.
        "noi_ten": TEN in tra_loi or "Dat" in tra_loi,
        "tu_choi": any(t in tra_loi for t in (*LOOKUP_FAILED.values(), *LOOKUP_REFUSAL.values())),
        "reply": " ".join(cau),
    }


def main() -> int:
    enable_utf8_console()
    from mrunner.khoa_grounding import chan_neu_m3   # cửa sổ M3: hạn grounding dùng chung
    chan_neu_m3(Path(__file__).name)
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()
    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY.")
        return 2
    persona = load_persona(cfg.persona_path)

    ke_hoach = [("A", True), ("B", True), ("A", False)]
    rows: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for dieu_kien, search in ke_hoach:
        for lang in ("vi", "en"):
            for rep in range(args.reps):
                try:
                    row = mot_luot(cfg, persona, dieu_kien, lang, search)
                except Exception as exc:              # một lượt hỏng không bỏ cả mẻ
                    row = {"dieu_kien": dieu_kien, "lang": lang, "search_enabled": search,
                           "error": f"{type(exc).__name__}: {exc}"}
                row.update(rep=rep, ts=ts, model=cfg.gemini_model)
                rows.append(row)
                print(f"{dieu_kien} search={int(search)} {lang} #{rep}: "
                      f"tool={row.get('tools_called')} lookup={row.get('lookup_flagged')} "
                      f"grounded={row.get('grounded')} ten={row.get('noi_ten')} "
                      f"| {str(row.get('reply', row.get('error')))[:110]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\nđiều kiện  search  lang   n  gọi recall  [lookup]  grounded  nói tên  từ chối")
    for dieu_kien, search in ke_hoach:
        for lang in ("vi", "en"):
            nhom = [r for r in rows if r["dieu_kien"] == dieu_kien and r["search_enabled"] == search
                    and r["lang"] == lang and "error" not in r]
            dem = lambda k: sum(1 for r in nhom if r[k])  # noqa: E731
            recall = sum(1 for r in nhom if "recall" in r["tools_called"])
            print(f"   {dieu_kien}        {int(search)}     {lang}  {len(nhom):2d}   {recall:2d}         "
                  f"{dem('lookup_flagged'):2d}        {dem('grounded'):2d}       {dem('noi_ten'):2d}      "
                  f"{dem('tu_choi'):2d}")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
