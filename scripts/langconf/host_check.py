r"""Đổi host có đổi kết luận không — chạy LẠI đúng những lượt ollama đã chạy, qua DeepInfra.

    ..\..\desktop\.venv\Scripts\python.exe scripts\host_check.py --arm qwen2.5:7b
    ..\..\desktop\.venv\Scripts\python.exe scripts\host_check.py --arm qwen2.5:7b --estimate

Vì sao cần: chuyển nhánh open-weight từ CPU cục bộ sang API là một thay đổi hạ tầng
giữa chừng. Bỏ qua thì nó thành một caveat trong bài ("chúng tôi đổi host, mong là
không sao"). Chạy lại đúng cùng lượt rồi so từng cái thì nó thành **một phép kiểm có
số** — và đó là thứ người phản biện hỏi.

Hai host KHÔNG chạy cùng trọng số y hệt:

    ollama      Q4_K_M   (lượng tử hoá 4 bit)
    DeepInfra   bfloat16 (DeepInfra công bố qua `models/list`)

Nên phép kiểm này đo **lượng tử hoá + hạ tầng gộp lại**, không tách được hai thứ. Nói
đúng như vậy trong bài; đừng gọi nó là "kiểm hạ tầng".

Ghép lượt bằng cách nào: `trial_key` băm cả `Cell`, mà `Cell.model` khác nhau giữa hai
host, nên khoá KHÔNG trùng — cố ý, để resume không lẫn. Ở đây ta ghép theo **mọi
trường của ô TRỪ `model`, cộng `probe_id`**.

Chủ nhân đặt ngưỡng: **lệch nhãn ngôn ngữ trên 10 % thì DỪNG**, không chạy tiếp.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import fleurs                                # noqa: E402
from langconf.design import Cell, Trial                    # noqa: E402
from langconf.langid import DualLangID, _same_language     # noqa: E402
from langconf.runner import Runner                         # noqa: E402
from scripts.run_main import (                             # noqa: E402
    HOSTED, DATA, RESULTS, deepinfra_key, fleurs_probe_items, load_key,
    make_bank_factory,
)

# Trường xác định một ô, TRỪ `model` — đó là biến duy nhất được phép khác giữa hai host.
MATCH_FIELDS = ("label_condition", "asr_backend", "target_lang", "confuse_lang",
                "depth", "label_position", "inject_source", "history_kind")

STOP_THRESHOLD = 0.10          # chủ nhân đặt


def cell_from_row(row: dict, model: str) -> Cell:
    """Dựng lại `Cell` từ một dòng jsonl, thay mỗi chuỗi model."""
    return Cell(
        label_condition=row["label_condition"],
        asr_backend=row.get("asr_backend"),
        model=model,
        target_lang=row["target_lang"],
        confuse_lang=row["confuse_lang"],
        depth=row["depth"],
        label_position=row["label_position"],
        inject_source=row.get("inject_source"),
        history_kind=row.get("history_kind"),
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True, choices=sorted(HOSTED))
    parser.add_argument("--estimate", action="store_true",
                        help="chỉ đếm lượt + ước tiền, không gọi API")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    ollama_path = RESULTS / f"main_{args.arm.replace(':', '-')}.jsonl"
    if not ollama_path.exists():
        raise SystemExit(f"không có {ollama_path} — nhánh ollama chưa chạy lượt nào")

    rows = [json.loads(l) for l in open(ollama_path, encoding="utf-8") if l.strip()]
    done = [r for r in rows if not r.get("model_error")]
    print(f"{len(rows):,} lượt ollama đã ghi, {len(done):,} lượt chạy được")
    if args.limit:
        done = done[: args.limit]

    model_id = HOSTED[args.arm]
    out_path = RESULTS / f"hostcheck_{model_id.replace('/', '_')}.jsonl"

    from langconf.models import DeepInfraBackend

    # Ước tiền TRƯỚC. Token vào lấy từ chính `in_tokens` mà ollama đã đếm — sát hơn
    # nhiều so với ước theo ký tự, dù bộ tách từ của hai bên không giống hệt.
    in_tokens = sum(r.get("in_tokens") or 0 for r in done)
    out_tokens = sum(r.get("out_tokens") or 0 for r in done)
    if True:                       # luon in uoc tinh truoc khi chay
        backend_for_price = DeepInfraBackend(model_id, api_key="chua-can")
        usd = backend_for_price.price_usd(in_tokens, out_tokens)
        print(f"  model DeepInfra : {model_id}")
        print(f"  siêu dữ liệu    : {backend_for_price.metadata}")
        print(f"  token vào/ra    : {in_tokens:,} / {out_tokens:,} (theo bộ đếm của ollama)")
        print(f"  ước chi phí     : ${usd:.4f}")
    if args.estimate:
        return 0

    table = fleurs.FleursText(DATA / "fleurs_meta", splits=("dev",))
    selection = fleurs.select(table, n_probe=50, max_depth=8)
    items = fleurs_probe_items(table, selection)
    backend = DeepInfraBackend(model_id, api_key=deepinfra_key())

    runner = Runner(
        table=table, selection=selection, backends={model_id: backend},
        out_path=out_path, asr_bank_for=make_bank_factory(load_key()),
        asr_cache_path=RESULTS / "asr_cache.jsonl", probe_items=items,
    )
    runner._frozen_asr = True          # bộ đệm ASR đã đầy từ nhánh Gemini

    already = {json.loads(l)["trial_key"]
               for l in open(out_path, encoding="utf-8")} if out_path.exists() else set()

    print(f"\nChạy lại {len(done)} lượt qua DeepInfra -> {out_path}")
    started = time.perf_counter()
    with open(out_path, "a", encoding="utf-8") as sink:
        for index, row in enumerate(done, start=1):
            trial = Trial(cell_from_row(row, model_id), row["probe_id"])
            if trial.key in already:
                continue
            built, meta = runner.build(trial)
            reply = backend.chat(built.as_dicts())
            sink.write(json.dumps({
                "trial_key": trial.key,
                "match_key": [row.get(f) for f in MATCH_FIELDS] + [row["probe_id"]],
                **trial.cell.as_dict(),
                "probe_id": row["probe_id"], "spoken_lang": row["spoken_lang"],
                "label_lang": built.label_lang, **meta,
                "reply_text": reply.text, "latency_ms": round(reply.latency_ms, 1),
                "model_error": reply.error, **reply.raw,
            }, ensure_ascii=False) + "\n")
            sink.flush()
            if index % 10 == 0 or index == len(done):
                print(f"  {index}/{len(done)}  {index / (time.perf_counter() - started):.2f}/s")

    # -- so từng lượt --------------------------------------------------------
    hosted = [json.loads(l) for l in open(out_path, encoding="utf-8") if l.strip()]
    by_key = {tuple(r["match_key"]): r for r in hosted}
    detector = DualLangID(DATA / "lid" / "lid.176.bin")

    compared = agree = agree_strict = identical_text = 0
    disagreements = []
    returned = collections.Counter()
    for row in done:
        key = tuple([row.get(f) for f in MATCH_FIELDS] + [row["probe_id"]])
        other = by_key.get(key)
        if other is None or other.get("model_error"):
            continue
        compared += 1
        returned[other.get("model_returned")] += 1
        a = detector.detect(row.get("reply_text") or "", record=False).fasttext
        b = detector.detect(other.get("reply_text") or "", record=False).fasttext
        agree += _same_language(a, b)
        agree_strict += a == b
        identical_text += (row.get("reply_text") or "").strip() == (other.get("reply_text") or "").strip()
        if not _same_language(a, b):
            disagreements.append((row, other, a, b))

    print()
    print("=" * 78)
    print("PHÉP KIỂM ĐỔI HOST — nhãn ngôn ngữ của câu trả lời có trùng không")
    print("=" * 78)
    if compared == 0:
        print("  không có lượt nào so được")
        return 1
    rate = agree / compared
    print(f"  so được            : {compared} lượt")
    print(f"  trùng nhãn ngôn ngữ: {agree}/{compared} = {rate:.1%}")
    print(f"  trùng theo mã      : {agree_strict}/{compared} = {agree_strict / compared:.1%}")
    print(f"  trùng NGUYÊN VĂN   : {identical_text}/{compared} = {identical_text / compared:.1%}")
    print(f"    (không kỳ vọng cao — Q4_K_M vs bfloat16 là hai bộ số khác nhau;")
    print(f"     điều quan trọng là NHÃN NGÔN NGỮ trùng, vì đó là thứ bài này đo)")
    print(f"  chuỗi model API trả về: {dict(returned)}")
    if disagreements:
        print(f"\n  {len(disagreements)} lượt lệch nhãn:")
        for row, other, a, b in disagreements[:10]:
            print(f"    nói={row['spoken_lang']} sâu={row['depth']} "
                  f"nhãn={row['label_position']} {row.get('history_kind')}")
            print(f"      ollama   ({a}): {(row.get('reply_text') or '')[:70]!r}")
            print(f"      deepinfra({b}): {(other.get('reply_text') or '')[:70]!r}")

    print()
    if 1 - rate > STOP_THRESHOLD:
        print(f"  >>> DỪNG — lệch {1 - rate:.1%} > ngưỡng {STOP_THRESHOLD:.0%}. "
              f"Báo chủ nhân, KHÔNG chạy tiếp lưới DeepInfra.")
        return 1
    print(f"  Lệch {1 - rate:.1%} ≤ ngưỡng {STOP_THRESHOLD:.0%} -> đổi host không đổi "
          f"kết luận về ngôn ngữ. Chạy tiếp được.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
