r"""Ước chi phí + thời gian TRƯỚC khi chạy. Không gọi model, không tốn gì.

    ..\..\desktop\.venv\Scripts\python.exe scripts\estimate.py

Mọi hằng số ở đây là **số đo thật từ pilot 150 lượt**, không phải đoán:

    token vào    67 ở độ sâu 0, cộng ~64 mỗi đơn vị nhiễm trong LỊCH SỬ,
                 cộng ~40 mỗi mục KÝ ỨC (mục ký ức không có lượt người dùng đi kèm)
    token ra     ~45 trung bình (trần đặt 100, model hiếm khi chạm)
    gemini       1,15 s/lượt khi gọi tuần tự
    qwen2.5:3b   6,6 s ở sâu 0 / 9,3 s ở sâu 8, CPU máy này
    model 7–8B   ước gấp đôi 3B -> ~15 s/lượt

Số tiền không phải chỗ đau. **Thời gian của model local mới là chỗ đau** — xem cột
cuối. Đó là lý do mọi đề án dưới đây đều cắt nhánh local trước.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import design                              # noqa: E402
from langconf.design import PAIRS, Spec                  # noqa: E402

# -- hằng số đo được từ pilot -------------------------------------------------
IN_BASE = 67
IN_PER_HISTORY_UNIT = 64
IN_PER_MEMORY_ITEM = 40
OUT_TOKENS = 45

SEC_GEMINI = 1.15          # tuần tự, một luồng
SEC_LOCAL_3B = 7.0
SEC_LOCAL_8B = 15.0

# USD / 1 triệu token (vào, ra). Model thứ ba để trống tới khi chủ nhân trả lời.
PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
}


def in_tokens(cell) -> int:
    if cell.depth == 0:
        return IN_BASE
    per = IN_PER_HISTORY_UNIT if cell.inject_source == "history" else IN_PER_MEMORY_ITEM
    return IN_BASE + per * cell.depth


def cost_and_time(spec: Spec, seconds_per_call: dict[str, float]) -> dict:
    per_model: dict[str, dict] = {}
    for cell in design.cells(spec):
        bucket = per_model.setdefault(cell.model, {"trials": 0, "in": 0, "out": 0})
        bucket["trials"] += spec.n_probe
        bucket["in"] += in_tokens(cell) * spec.n_probe
        bucket["out"] += OUT_TOKENS * spec.n_probe

    total_usd = 0.0
    total_hours = 0.0
    rows = []
    for model, bucket in sorted(per_model.items()):
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
        usd = (bucket["in"] * price_in + bucket["out"] * price_out) / 1_000_000
        hours = bucket["trials"] * seconds_per_call.get(model, SEC_GEMINI) / 3600
        total_usd += usd
        total_hours += hours
        rows.append({"model": model, **bucket, "usd": usd, "hours": hours})
    return {"rows": rows, "usd": total_usd, "hours": total_hours,
            "trials": sum(r["trials"] for r in rows)}


# ---------------------------------------------------------------------------
# Ba đề án
# ---------------------------------------------------------------------------

# Chốt 07/09/2026: **không có key API thứ ba**. Model thứ ba là một model local thứ
# hai KHÁC HỌ (`llama3.1:8b` vs `qwen2.5:7b`) — vẫn đủ để loại giả thuyết "chỉ là
# quirk của Gemini", nhưng đổi lại nhánh local nặng gấp đôi về thời gian CPU.
API_MODELS = ("gemini-2.5-flash",)
LOCAL = "qwen2.5:7b"
LOCAL_2 = "llama3.1:8b"
LOCALS = (LOCAL, LOCAL_2)
ALL_MODELS = (*API_MODELS, *LOCALS)


def _local_spec(model: str, **overrides) -> "Spec":
    """Lưới rút gọn cho model local: giữ F1 và F5 nguyên vẹn (hai đóng góp chính),
    cắt F3 xuống hai cặp đối lập nhất về hệ chữ, F4 xuống ba mốc đủ vẽ đường cong,
    bỏ F6. Đủ để nói "hiện tượng không phải của riêng Gemini", không hơn."""
    kwargs = dict(
        label_conditions=("oracle", "asr"), asr_backends=("gemini-audio",),
        models=(model,), pairs=(("vi", "en"), ("ko", "en")),
        depths=(0, 2, 8), label_positions=("none", "user"),
        inject_sources=("history",), n_probe=50,
    )
    kwargs.update(overrides)
    return Spec(**kwargs)

PLANS: dict[str, tuple[str, list[Spec]]] = {
    "A": (
        "ĐẦY ĐỦ — mọi mức của mọi yếu tố, cùng một lưới cho cả ba model",
        [Spec(label_conditions=("oracle", "asr"),
              asr_backends=("gemini-audio", "phowhisper-reread"),
              models=ALL_MODELS, pairs=PAIRS, n_probe=50)],
    ),
    "B": (
        "CÂN BẰNG (ĐÃ CHỐT) — Gemini chạy lưới đầy đủ; hai model local khác họ chạy "
        "lưới rút gọn vừa đủ để loại giả thuyết \"chỉ là quirk của Gemini\"",
        [
            Spec(label_conditions=("oracle", "asr"),
                 asr_backends=("gemini-audio", "phowhisper-reread"),
                 models=API_MODELS, pairs=PAIRS, n_probe=50),
            *[_local_spec(m) for m in LOCALS],
        ],
    ),
    "C": (
        "TỐI THIỂU CÔNG BỐ ĐƯỢC — cắt F1 còn một backend ASR, F5 còn hai mức, "
        "n = 30. Dùng nếu muốn có bảng trong một ngày",
        [
            Spec(label_conditions=("oracle", "asr"), asr_backends=("gemini-audio",),
                 models=API_MODELS, pairs=PAIRS,
                 label_positions=("none", "user"), n_probe=30),
            Spec(label_conditions=("oracle",), models=(LOCAL,),
                 pairs=(("vi", "en"), ("ko", "en")), depths=(0, 2, 8),
                 label_positions=("none", "user"), inject_sources=("history",),
                 n_probe=30),
        ],
    ),
}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    seconds = {"gemini-2.5-flash": SEC_GEMINI, LOCAL: SEC_LOCAL_8B, LOCAL_2: SEC_LOCAL_8B}
    print("Chốt 07/09/2026: không có key API thứ ba -> model thứ ba là model local")
    print(f"thứ hai khác họ ({LOCAL_2} so với {LOCAL}). Chỉ Gemini tốn tiền.\n")

    for name, (title, specs) in PLANS.items():
        print("=" * 78)
        print(f"ĐỀ ÁN {name} — {title}")
        print("=" * 78)
        grand = {"trials": 0, "usd": 0.0, "hours": 0.0}
        for spec in specs:
            result = cost_and_time(spec, seconds)
            for row in result["rows"]:
                print(f"  {row['model']:<20}{row['trials']:>8,} lượt "
                      f"{row['in']:>10,} token vào {row['out']:>9,} ra  "
                      f"{row['usd']:>7.2f} USD  {row['hours']:>7.1f} h")
            grand["trials"] += result["trials"]
            grand["usd"] += result["usd"]
            grand["hours"] += result["hours"]
        print(f"  {'TỔNG':<20}{grand['trials']:>8,} lượt"
              f"{'':>32}{grand['usd']:>9.2f} USD  {grand['hours']:>7.1f} h")
        print(f"  (giờ tính GỌI TUẦN TỰ. Model API chạy 8 luồng thì chia 8; "
              f"model local KHÔNG chia được — CPU đã kín.)")
        print()

    print("=" * 78)
    print("Nếu sau này có key API — giá cho MỘT model chạy lưới đầy đủ của đề án B")
    print("(USD / 1 triệu token vào / ra). Chỉ để tham khảo, hiện KHÔNG chạy.")
    print("=" * 78)
    tokens = cost_and_time(PLANS["B"][1][0], seconds)["rows"][0]
    for model, (price_in, price_out) in PRICES.items():
        if model == "gemini-2.5-flash":
            continue
        usd = (tokens["in"] * price_in + tokens["out"] * price_out) / 1_000_000
        print(f"  {model:<20}{price_in:>6.2f} / {price_out:>6.2f}   -> {usd:>7.2f} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
