r"""Thử xem Gemini có cho trộn function tool + google_search trong CÙNG một request không.

Chạy TRƯỚC khi nối grounding vào pipeline (docs/ADR-010). Một số phiên bản API từ
chối request có cả hai loại `types.Tool`; nếu vậy thì phải chọn một, và đó là đánh
đổi người dùng quyết chứ không phải chỗ này quyết.

    python scripts\probe_grounding.py

Bốn phép thử, mỗi phép là một request thật:
    1. chỉ function tool          (đối chứng: đường hiện tại)
    2. chỉ google_search          (grounding có chạy với model/khoá này không)
    3. cả hai, hai Tool riêng     (dạng ta muốn dùng)
    4. cả hai, gộp một Tool       (dạng dự phòng nếu 3 hỏng)

Mỗi phép chạy hai lần: thinking_budget=0 (mặc định của repo, ADR-001) và không
đặt thinking_config. Mục đích: biết grounding có đòi thinking không — nếu có thì
GHI LẠI, đừng tự bật, vì thinking_budget=0 là điều kiện của mọi số đo đã có.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google import genai
from google.genai import types

from brain.tools import tool_declarations
from config import Config, enable_utf8_console

CAU_HOI = "Hôm nay giá vàng SJC ở Việt Nam khoảng bao nhiêu một lượng?"


def _search_tool() -> types.Tool:
    return types.Tool(google_search=types.GoogleSearch())


def _both_separate() -> list[types.Tool]:
    return tool_declarations() + [_search_tool()]


def _both_merged() -> list[types.Tool]:
    """Gộp function_declarations và google_search vào MỘT Tool."""
    declarations = tool_declarations()[0].function_declarations
    return [types.Tool(function_declarations=declarations, google_search=types.GoogleSearch())]


PHEP_THU = {
    "1. chỉ function tool": tool_declarations,
    "2. chỉ google_search": lambda: [_search_tool()],
    "3. cả hai, Tool riêng": _both_separate,
    "4. cả hai, gộp một Tool": _both_merged,
}


def thu(client: genai.Client, model: str, ten: str, tools: list[types.Tool], thinking: bool) -> bool:
    config = types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=400,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if not thinking:
        config.thinking_config = types.ThinkingConfig(thinking_budget=0)

    nhan = f"{ten}  [{'thinking mặc định' if thinking else 'thinking_budget=0'}]"
    bat_dau = perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=CAU_HOI, config=config)
    except Exception as exc:
        print(f"\n{nhan}\n   HỎNG  {type(exc).__name__}: {str(exc)[:400]}")
        return False

    ms = (perf_counter() - bat_dau) * 1000
    text = (response.text or "").strip().replace("\n", " ")
    meta = getattr(response.candidates[0], "grounding_metadata", None) if response.candidates else None
    queries = list(getattr(meta, "web_search_queries", None) or []) if meta else []
    chunks = len(getattr(meta, "grounding_chunks", None) or []) if meta else 0
    calls = [c.name for c in (response.function_calls or [])]
    usage = response.usage_metadata
    nghi = getattr(usage, "thoughts_token_count", None) if usage else None

    print(f"\n{nhan}\n   OK    {ms:.0f} ms")
    print(f"   truy vấn tra cứu : {queries or '(không có)'}")
    print(f"   nguồn trả về     : {chunks}")
    print(f"   function call    : {calls or '(không có)'}")
    print(f"   thinking token   : {nghi if nghi is not None else '(không báo)'}")
    print(f"   lời thoại        : {text[:200]}")
    return True


def main() -> int:
    enable_utf8_console()
    from mrunner.khoa_grounding import chan_neu_m3   # cửa sổ M3: hạn grounding dùng chung
    chan_neu_m3(Path(__file__).name)
    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY trong ..\\.env")
        return 1
    client = genai.Client(api_key=cfg.gemini_api_key)
    print(f"model: {cfg.gemini_model}\ncâu hỏi: {CAU_HOI}")
    print(f"google-genai: {getattr(genai, '__version__', '(không rõ)')}")

    ket_qua: dict[str, bool] = {}
    for ten, dung_tools in PHEP_THU.items():
        try:
            tools = dung_tools()
        except Exception:
            print(f"\n{ten}\n   HỎNG ngay lúc dựng Tool:")
            traceback.print_exc()
            ket_qua[ten] = False
            continue
        for thinking in (False, True):
            ok = thu(client, cfg.gemini_model, ten, tools, thinking)
            ket_qua[f"{ten} / {'thinking' if thinking else 'budget=0'}"] = ok

    print("\n" + "=" * 60)
    for ten, ok in ket_qua.items():
        print(f"  {'OK  ' if ok else 'HỎNG'}  {ten}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
