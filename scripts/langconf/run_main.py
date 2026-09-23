r"""BƯỚC 2 — chạy toàn bộ đề án B. Ghi jsonl, không chấm điểm.

    ..\..\desktop\.venv\Scripts\python.exe scripts\run_main.py --arm gemini
    ..\..\desktop\.venv\Scripts\python.exe scripts\run_main.py --arm qwen2.5:7b
    ..\..\desktop\.venv\Scripts\python.exe scripts\run_main.py --arm llama3.1:8b
    ..\..\desktop\.venv\Scripts\python.exe scripts\run_main.py --arm realvoice

Mỗi nhánh ghi vào file riêng trong `results/`, resume độc lập, chạy được song song
với nhau (nhánh Gemini chờ mạng, nhánh local chờ CPU — không giẫm chân nhau; nhưng
HAI nhánh local thì phải chạy lần lượt, cùng tranh một CPU).

`--dry` in kế hoạch rồi dừng, không gọi model.

## Đề án B (chốt 07/09/2026, sau khi biết không có key API thứ ba)

    gemini-2.5-flash   lưới ĐẦY ĐỦ: F1×F2×F3×F4×F5×F6, 8 hướng, n=50   61 200 lượt
    qwen2.5:7b         lưới rút gọn (giữ F1 và F5, cắt F3/F4, bỏ F6)     4 000 lượt
    llama3.1:8b        như trên, khác họ model                            4 000 lượt

Nhánh `realvoice` chạy CÙNG thiết kế trên 31 WAV giọng thật, **báo riêng**, không
trộn vào bảng FLEURS (chủ nhân dặn). Chỉ cặp vi-en, vì dữ liệu thật chỉ có hai
thứ tiếng đó, và chỉ hạng backend `DESKTOP_V3` (baseline v3 y nguyên).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import design, fleurs                       # noqa: E402
from langconf.design import PAIRS, Spec                   # noqa: E402
from langconf.runner import ProbeItem, Runner             # noqa: E402

DATA = ROOT / "data"
RESULTS = ROOT / "results"
DESKTOP = ROOT.parents[1] / "desktop"
REFS = ROOT.parents[1] / "docs" / "baseline" / "realvoice_2026-09-06_v2_refs.json"

# Hai nhánh open-weight chạy được ở hai nơi. `Cell.model` mang ĐÚNG chuỗi id của nhà
# cung cấp, nên `trial_key` của hai host khác nhau và resume không thể lẫn — chạy
# DeepInfra không bị bỏ qua vì ollama đã chạy rồi.
#
# Vì sao có DeepInfra: hành vi ngôn ngữ là thuộc tính của TRỌNG SỐ, không phải của
# phần cứng. Vì sao GIỮ ollama: nửa còn lại của bài (`docs/ADR-006`) là số CPU cục bộ.
#
# CẢNH BÁO đã kiểm ngày 07/09/2026 qua `api.deepinfra.com/models/list`:
#   Qwen/Qwen2.5-7B-Instruct              deprecated 2025-11-06, thay bằng Qwen3-14B
#   meta-llama/Meta-Llama-3.1-8B-Instruct deprecated 2026-07-16, thay bằng bản Turbo
# "Deprecated" chưa chắc là "đã gỡ", nhưng nếu gỡ thật thì không có bản cùng họ cùng
# cỡ nào thay được (Qwen3-14B khác cỡ và có chế độ nghĩ; bản Turbo là fp8 chứ không
# phải bfloat16). Việc đầu tiên khi có key là thử một lượt.
HOSTED = {
    "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
    "llama3.1:8b": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}

GEMINI_SPEC = Spec(
    label_conditions=("oracle", "asr"),
    asr_backends=("gemini-audio", "phowhisper-reread"),
    models=("gemini-2.5-flash",),
    pairs=PAIRS,
    n_probe=50,
)


# Trần cứng chủ nhân đặt. Vượt là DỪNG và báo, không tự chạy tiếp.
HARD_CAP_USD = 3.00

# Token vào theo độ sâu — số ĐO từ 150 lượt pilot, không phải ước theo ký tự.
IN_BASE, IN_PER_HISTORY_UNIT, OUT_TOKENS = 67, 64, 45


def estimate_tokens(spec: Spec) -> tuple[int, int]:
    """(token vào, token ra) cho cả `spec`. Đếm theo từng ô, không lấy trung bình."""
    total_in = 0
    for cell in design.cells(spec):
        depth_cost = IN_BASE + (IN_PER_HISTORY_UNIT * cell.depth if cell.depth else 0)
        total_in += depth_cost * spec.n_probe
    return total_in, len(design.cells(spec)) * spec.n_probe * OUT_TOKENS


def check_cost_cap(spec: Spec, backend) -> None:
    """In ước chi phí rồi DỪNG nếu vượt trần. Gọi TRƯỚC lượt API đầu tiên.

    Bộ tách từ của mỗi nhà cung cấp một khác nên con số này là ước, không phải hoá
    đơn. Nhân hệ số an toàn 1,5 khi so với trần: thà dừng oan còn hơn tiêu quá.
    """
    in_tokens, out_tokens = estimate_tokens(spec)
    usd = backend.price_usd(in_tokens, out_tokens)
    print(f"  token ước tính : {in_tokens:,} vào / {out_tokens:,} ra")
    print(f"  chi phí ước    : ${usd:.4f}  (biên an toàn ×1,5 -> ${usd * 1.5:.4f})")
    print(f"  trần cứng      : ${HARD_CAP_USD:.2f}")
    if usd * 1.5 > HARD_CAP_USD:
        raise SystemExit(
            f"DỪNG: ước ${usd * 1.5:.2f} (đã nhân biên an toàn) vượt trần "
            f"${HARD_CAP_USD:.2f}. Báo chủ nhân, không tự chạy tiếp."
        )


def local_spec(model: str) -> Spec:
    """Lưới rút gọn cho model local. Giữ F1 và F5 nguyên vẹn — hai đóng góp chính —
    cắt F3 xuống hai cặp đối lập nhất về hệ chữ, F4 xuống ba mốc, bỏ F6."""
    return Spec(
        label_conditions=("oracle", "asr"),
        asr_backends=("gemini-audio",),
        models=(model,),
        pairs=(("vi", "en"), ("ko", "en")),
        depths=(0, 2, 8),
        label_positions=("none", "user"),
        inject_sources=("history",),
        n_probe=50,
    )


def realvoice_spec(target_lang: str, n_probe: int) -> Spec:
    """31 WAV giọng thật. `@v3` ở tên backend chọn hạng DESKTOP_V3 (chỉ vi/en)."""
    return Spec(
        label_conditions=("oracle", "asr"),
        asr_backends=("gemini-audio@v3", "phowhisper-reread@v3"),
        models=("gemini-2.5-flash",),
        pairs=((target_lang, "en" if target_lang == "vi" else "vi"),),
        both_directions=False,
        n_probe=n_probe,
    )


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def deepinfra_key() -> str:
    """DEEPINFRA_API_KEY từ `.env` ở gốc repo. Chỉ ĐỌC, không sửa (CLAUDE.md).

    Không dùng bộ đọc của `desktop/config.py` vì nó chỉ biết các khoá của desktop.
    Tự tách, nhưng **cắt chú thích cùng dòng** — `.env` của repo này có
    `GEMINI_API_KEY=AQ... # lấy tại aistudio...`, và bản đầu tiên nuốt luôn chú thích
    khiến 150/150 lượt pilot hỏng vì httpx nổ ascii ở header.
    """
    env = DESKTOP.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DEEPINFRA_API_KEY="):
                value = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
                if value:
                    return value
    key = os.environ.get("DEEPINFRA_API_KEY")
    if key:
        return key
    raise SystemExit(
        "không tìm thấy DEEPINFRA_API_KEY. Thêm một dòng vào .env ở gốc repo: "
        "DEEPINFRA_API_KEY=<key>"
    )


def load_key() -> str:
    if str(DESKTOP) not in sys.path:
        sys.path.insert(0, str(DESKTOP))
    from config import Config

    key = Config.load().gemini_api_key
    if not key:
        raise SystemExit("không có GEMINI_API_KEY (đọc qua desktop/config.py)")
    return key


def fleurs_probe_items(table: fleurs.FleursText, selection) -> dict:
    """{(lang, flores_id): ProbeItem} — chữ chuẩn + WAV cho điều kiện ASR."""
    items = {}
    for lang in fleurs.LANGUAGES:
        for sid in selection.probe_ids:
            wav = DATA / "audio" / lang / f"{sid}.wav"
            items[(lang, sid)] = ProbeItem(
                probe_id=sid, lang=lang, gold_text=table.text(sid, lang),
                wav=wav if wav.exists() else None, source="fleurs",
            )
    return items


def realvoice_items() -> tuple[dict, dict[str, list[str]]]:
    """31 WAV giọng thật + câu mẫu (ground truth đã sửa lượt #17)."""
    refs = json.loads(REFS.read_text(encoding="utf-8"))
    utts = DESKTOP / "logs" / "utts"
    items, by_lang = {}, {"vi": [], "en": []}
    for name in sorted(refs):
        row = refs[name]
        lang = row["lang"]
        items[(lang, name)] = ProbeItem(
            probe_id=name, lang=lang, gold_text=row["text"],
            wav=utts / name, source="realvoice",
        )
        by_lang[lang].append(name)
    return items, by_lang


def make_bank_factory(api_key: str):
    """Dựng ASRBank theo hạng, chỉ khi cần, và dùng lại (mỗi hạng nạp ~1 GB model)."""
    from langconf.asr import FOUR, ASRBank

    cache: dict[str, ASRBank] = {}

    def get(tier: str) -> ASRBank:
        if tier not in cache:
            langs = ("vi", "en") if tier == "DESKTOP_V3" else FOUR
            print(f"  [asr] nạp hạng {tier} ({'/'.join(langs)})…")
            cache[tier] = ASRBank(api_key=api_key, languages=langs)
        return cache[tier]

    return get


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True,
                        choices=["gemini", "qwen2.5:7b", "llama3.1:8b", "realvoice"])
    parser.add_argument("--host", choices=["ollama", "deepinfra"], default="ollama",
                        help="chỉ áp cho hai nhánh open-weight; gemini/realvoice bỏ qua")
    parser.add_argument("--workers", type=int, default=None,
                        help="mặc định 8 cho Gemini, 1 cho model local (CPU đã kín)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry", action="store_true", help="in kế hoạch rồi dừng")
    args = parser.parse_args()

    api_key = load_key()
    table = fleurs.FleursText(DATA / "fleurs_meta", splits=("dev",))
    selection = fleurs.select(table, n_probe=50, max_depth=8)

    if args.arm == "realvoice":
        items, by_lang = realvoice_items()
        specs = []
        for lang in ("vi", "en"):
            # Mỗi lượt giọng thật có ngôn ngữ CỐ ĐỊNH, nên hướng T phải khớp với chính
            # ngôn ngữ của lượt đó. Chạy hai lượt riêng, mỗi lượt một kho thăm dò.
            sel = replace(selection, probe_ids=by_lang[lang])
            specs.append((realvoice_spec(lang, len(by_lang[lang])), sel))
        out = RESULTS / "realvoice.jsonl"
        workers = args.workers if args.workers is not None else 4
    elif args.arm == "gemini":
        items = fleurs_probe_items(table, selection)
        specs = [(GEMINI_SPEC, selection)]
        out = RESULTS / "main_gemini.jsonl"
        workers = args.workers if args.workers is not None else 8
    else:
        items = fleurs_probe_items(table, selection)
        model_id = HOSTED[args.arm] if args.host == "deepinfra" else args.arm
        specs = [(local_spec(model_id), selection)]
        slug = model_id.replace(":", "-").replace("/", "_")
        out = RESULTS / f"main_{slug}.jsonl"
        # ollama = 1 luồng (CPU đã kín, mở luồng chỉ làm mỗi lượt chậm hơn).
        # deepinfra = 8 luồng, chờ mạng chứ không chờ CPU.
        default_workers = 8 if args.host == "deepinfra" else 1
        workers = args.workers if args.workers is not None else default_workers

    total = sum(design.count(spec)["trials"] for spec, _ in specs)
    print(f"nhánh {args.arm}: {total:,} lượt, {workers} luồng -> {out}")
    for spec, _ in specs:
        counts = design.count(spec)
        print(f"  {counts['cells']:>5} ô × {spec.n_probe} câu = {counts['trials']:>7,} lượt")
    if args.dry:
        print("--dry: dừng, chưa gọi model.")
        return 0

    from langconf.models import GeminiBackend, OllamaBackend

    if args.arm in ("gemini", "realvoice"):
        backends = {"gemini-2.5-flash": GeminiBackend(api_key)}
    elif args.host == "deepinfra":
        from langconf.models import DeepInfraBackend

        backend = DeepInfraBackend(model_id, api_key=deepinfra_key())
        print(f"  DeepInfra {model_id}")
        print(f"  siêu dữ liệu: {backend.metadata}")
        if backend.metadata.get("deprecated_ts"):
            import datetime

            when = datetime.datetime.utcfromtimestamp(backend.metadata["deprecated_ts"]).date()
            print(f"  !! model này DeepInfra đánh dấu deprecated từ {when}, "
                  f"thay bằng {backend.metadata.get('replaced_by')}")
        check_cost_cap(specs[0][0], backend)
        backends = {model_id: backend}
    else:
        backends = {model_id: OllamaBackend(model_id, timeout_s=900)}

    stats = []
    for spec, sel in specs:
        runner = Runner(
            table=table, selection=sel, backends=backends, out_path=out,
            asr_bank_for=make_bank_factory(api_key),
            asr_cache_path=RESULTS / "asr_cache.jsonl",
            probe_items=items,
        )
        # Chép ASR TRƯỚC, tuần tự, rồi mới mở luồng gọi LLM. Xem `Runner.prefetch_asr`.
        if "asr" in spec.label_conditions:
            print(runner.prefetch_asr(spec))
        stats.append(runner.run(spec, workers=workers, limit=args.limit))
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
