r"""BƯỚC 1 — pilot. Chạy nhỏ, in nguyên văn prompt, rồi DỪNG chờ duyệt.

    cd study\langconf
    ..\..\desktop\.venv\Scripts\python.exe scripts\pilot.py --report

Không có `--run` thì script chỉ dựng prompt và in ra, KHÔNG gọi model, không tốn
đồng nào. Thêm `--run` mới thật sự gọi Gemini (khoảng 150 lượt, xem ước tính in ra).
`--asr` chạy thêm phần nhãn-do-ASR trên WAV giọng thật đã có sẵn trong `desktop/logs/utts`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf import design, fleurs, prompts                      # noqa: E402
from langconf.cohere_metrics import CohereScorer                  # noqa: E402
from langconf.design import Spec                                  # noqa: E402
from langconf.langid import DualLangID                            # noqa: E402
from langconf.runner import ProbeItem, Runner                     # noqa: E402

DATA = ROOT / "data"
RESULTS = ROOT / "results"
DESKTOP = ROOT.parents[1] / "desktop"

# Pilot: 5 câu, 2 ngôn ngữ (cặp vi-en hai chiều), 1 model — đúng như chủ nhân đặt.
# Nhưng chạm vào MỌI mức của F4/F5/F6 ít nhất một lần, nếu không thì pilot không
# kiểm được cái cần kiểm.
PILOT = Spec(
    label_conditions=("oracle",),
    models=("gemini-2.5-flash",),
    pairs=(("vi", "en"),),
    both_directions=True,
    depths=(0, 2),
    label_positions=("none", "system", "user"),
    inject_sources=("history", "memory"),
    history_kinds=("clean", "contaminated"),
    n_probe=5,
)


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def load_key() -> str | None:
    """Lấy GEMINI_API_KEY qua `desktop/config.py`. Chỉ ĐỌC, không sửa (CLAUDE.md).

    Dùng lại bộ đọc `.env` của `desktop/` chứ không tự tách chuỗi: `.env` ở repo này
    có chú thích cùng dòng (`GEMINI_API_KEY=AQ... # lấy tại aistudio...`). Bản tự tách
    đầu tiên nuốt luôn chú thích, key chui vào header HTTP và httpx nổ
    `UnicodeEncodeError: 'ascii' codec` — 150/150 lượt pilot hỏng vì đúng chuyện này.
    """
    if str(DESKTOP) not in sys.path:
        sys.path.insert(0, str(DESKTOP))
    try:
        from config import Config

        key = Config.load().gemini_api_key
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="thật sự gọi model")
    parser.add_argument("--asr", action="store_true", help="chạy thêm phần nhãn-do-ASR")
    parser.add_argument("--report", action="store_true", help="in báo cáo đầy đủ")
    parser.add_argument("--n-prompts", type=int, default=3, help="in bao nhiêu prompt nguyên văn")
    args = parser.parse_args()

    # -- 1. FLEURS: đếm câu song song ------------------------------------
    section("1. FLEURS — câu song song ở cả bốn ngôn ngữ")
    fleurs.download_metadata(DATA / "fleurs_meta")
    for splits in (("dev",), ("test",), ("dev", "test")):
        table = fleurs.FleursText(DATA / "fleurs_meta", splits=splits)
        counts = table.counts()
        print(f"  {'+'.join(splits):<10} mỗi ngôn ngữ {counts['per_language']}"
              f"  ->  giao cả bốn: {counts['parallel']}")

    table = fleurs.FleursText(DATA / "fleurs_meta", splits=("dev",))
    selection = fleurs.select(table, n_probe=50, max_depth=8)
    print()
    print(f"  Chọn split `dev` (audio nhẹ nhất: 732 MB cho cả bốn ngôn ngữ).")
    print(f"  id song song có sẵn : {selection.available}")
    print(f"  dành cho lịch sử    : {len(selection.history_ids)} id "
          f"(8 cho lượt người dùng + 8 cho lượt trợ lý / mục ký ức)")
    print(f"  dành cho thăm dò    : {len(selection.probe_ids)} id — ĐỦ 50, không phải hạ")
    print(f"  seed                : {selection.seed}")
    print(f"  hai kho RỜI NHAU    : {not (set(selection.probe_ids) & selection.history_ids)}")

    # -- 2. Kiểm nhiễm dữ liệu -------------------------------------------
    section("2. Kiểm nhiễm — câu FLEURS nào tự nhắc tới một ngôn ngữ")
    pool = table.pool(selection.probe_ids + sorted(selection.history_ids))
    flagged = prompts.flag_language_mentions(pool)
    if not flagged:
        print("  Không câu nào. (Không có nghĩa là sạch tuyệt đối — chỉ là bộ lọc từ khoá.)")
    else:
        print(f"  {len(flagged)} câu tự nhắc tới ngôn ngữ. KHÔNG tự loại — chủ nhân quyết:")
        for row in flagged[:15]:
            where = "LỊCH SỬ" if row["id"] in selection.history_ids else "thăm dò"
            print(f"    [{where}] id={row['id']} lang={row['lang']} {row['hints']}")
            print(f"       {row['text'][:110]}")
    print()
    print("  Khung nhiệm vụ + tiêu đề ký ức có trung tính không: ", end="")
    prompts.check_scaffolding_is_neutral()
    print("ĐẠT (không có tên ngôn ngữ nào ngoài nhãn)")

    # -- 3. Lưới pilot ----------------------------------------------------
    section("3. Lưới pilot")
    counts = design.count(PILOT)
    print(f"  ô  : {counts['cells']}")
    print(f"  lượt gọi model : {counts['trials']}")
    print(f"  {json.dumps(PILOT.as_dict(), ensure_ascii=False, indent=2)}")

    backends: dict[str, object] = {}
    key = load_key()
    if args.run:
        from langconf.models import GeminiBackend

        if not key:
            raise SystemExit("không tìm thấy GEMINI_API_KEY trong desktop/.env")
        backends["gemini-2.5-flash"] = GeminiBackend(key)
    else:
        class _Dry:
            def chat(self, messages):
                from langconf.models import Reply
                return Reply("", 0.0, "dry-run", error="dry-run: chưa gọi model")
        backends["gemini-2.5-flash"] = _Dry()

    runner = Runner(
        table=table,
        selection=selection,
        backends=backends,
        out_path=RESULTS / "pilot.jsonl",
        asr_cache_path=RESULTS / "asr_cache_pilot.jsonl",
    )

    # -- 4. Prompt nguyên văn --------------------------------------------
    section("4. NGUYÊN VĂN prompt gửi đi — soi kỹ chỗ này")
    all_trials = list(design.trials(PILOT, selection.probe_ids))
    # Chọn có chủ đích: một ô sạch sâu 0, một ô nhiễm sâu 2 nhãn ở lượt người dùng,
    # một ô nhiễm từ KÝ ỨC — ba khuôn khác nhau, đủ để soi hết cách dựng.
    def pick(**want):
        for trial in all_trials:
            cell = trial.cell
            if all(getattr(cell, k) == v for k, v in want.items()):
                return trial
        return None

    chosen = [
        pick(depth=0, label_position="none", target_lang="en"),
        pick(depth=2, label_position="user", inject_source="history",
             history_kind="contaminated", target_lang="en"),
        pick(depth=2, label_position="system", inject_source="memory",
             history_kind="contaminated", target_lang="vi"),
    ][: args.n_prompts]

    for trial in chosen:
        if trial is None:
            continue
        built, meta = runner.build(trial)
        print()
        print("-" * 78)
        print(f"Ô: {trial.cell.name}")
        print(f"probe_id={trial.probe_id}  spoken_lang={trial.cell.target_lang}  "
              f"label_lang={built.label_lang}")
        print(f"kiểm nhiễm: ĐẠT (audit_messages không ném lỗi)")
        print("-" * 78)
        print(prompts.render_verbatim(built))
    print()
    print("-" * 78)
    print("Đối chứng — ĐÚNG cùng ô nhiễm ở trên nhưng lịch sử SẠCH.")
    print("Chỉ NGÔN NGỮ lượt trợ lý đổi; nội dung từng câu giữ nguyên.")
    print("-" * 78)
    clean = pick(depth=2, label_position="user", inject_source="history",
                 history_kind="clean", target_lang="en")
    if clean is not None:
        built, _ = runner.build(clean)
        print(prompts.render_verbatim(built))

    # -- 5. Kiểm nhiễm toàn bộ lưới pilot --------------------------------
    section("5. Kiểm nhiễm — dựng thử TẤT CẢ prompt của lưới pilot")
    bad = 0
    for trial in all_trials:
        try:
            runner.build(trial)
        except prompts.ContaminationError as exc:
            bad += 1
            print(f"  BẨN: {trial.cell.name} probe={trial.probe_id}\n    {exc}")
    print(f"  {len(all_trials)} prompt dựng thử, {bad} bẩn.")
    if bad:
        return 1

    # -- 6. Ước chi phí ---------------------------------------------------
    section("6. Ước chi phí pilot")
    sample_built, _ = runner.build(all_trials[0])
    deep = pick(depth=2, inject_source="history", history_kind="contaminated")
    deep_built, _ = runner.build(deep)
    def rough_tokens(built) -> int:
        return sum(len(t.content) for t in built.messages) // 3
    lo, hi = rough_tokens(sample_built), rough_tokens(deep_built)
    from langconf.models import MAX_TOKENS

    in_tokens = counts["trials"] * (lo + hi) // 2
    out_tokens = counts["trials"] * MAX_TOKENS
    usd = (in_tokens * 0.30 + out_tokens * 2.50) / 1_000_000
    print(f"  token vào ~{in_tokens:,}  token ra ~{out_tokens:,}  ->  ~{usd:.3f} USD")
    print(f"  (ước thô: 1 token ~ 3 ký tự; giá gemini-2.5-flash 0,30 / 2,50 USD mỗi triệu)")

    if not args.run:
        section("DỪNG — chưa gọi model")
        print("  Thêm --run để chạy thật 150 lượt. Chưa tốn đồng nào.")
        return 0

    # -- 7. Chạy thật -----------------------------------------------------
    section("7. Chạy pilot")
    stats = runner.run(PILOT)
    print(f"  {stats}")

    section("8. Chấm thử pilot")
    from langconf import scoring

    scorer = CohereScorer(DATA / "lid" / "lid.176.bin", DATA / "lid" / "words")
    detector = DualLangID(DATA / "lid" / "lid.176.bin")
    rows = [json.loads(l) for l in open(RESULTS / "pilot.jsonl", encoding="utf-8") if l.strip()]
    rows = [r for r in rows if not r.get("model_error")]

    groups: dict[tuple, list] = {}
    for row in rows:
        cell_key = (row["target_lang"], row["depth"], row["label_position"],
                    row["inject_source"], row["history_kind"])
        judged = scoring.judge(row, "speaker_language_accuracy", scorer, detector)
        if judged is not None:
            groups.setdefault(cell_key, []).append(judged)

    print(f"  {'T':<3}{'sâu':>4} {'nhãn':<8}{'nguồn':<9}{'lịch sử':<14}"
          f"{'khớp (đúng thực tế)':<28}{'LPR':<28}bỏ")
    for cell_key in sorted(groups, key=lambda k: (k[0], k[1], str(k[2]), str(k[3]), str(k[4]))):
        judged = groups[cell_key]
        summary = scoring.summarize_cell(cell_key, judged, ruler="speaker_language_accuracy", resamples=2000)
        target, depth, position, source, kind = cell_key
        print(f"  {target:<3}{depth:>4} {position:<8}{str(source):<9}{str(kind):<14}"
              f"{str(summary.match):<28}{str(summary.lpr):<28}{summary.skipped}")

    report = detector.agreement_report()
    print()
    print(f"  Đồng thuận fastText/lingua: {report['agree']}/{report['n']} "
          f"lệch {report['disagree_rate']:.1%} (ngưỡng dừng 3 %)")
    if report["stop"]:
        print("  >>> VƯỢT NGƯỠNG — dừng, hỏi chủ nhân trước khi chạy toàn bộ.")
        for example in report["examples"][:10]:
            print(f"      len={example['len']:>4} fastText={example['fasttext']:<8} "
                  f"lingua={example['lingua']}")

    if args.asr:
        section("9. F1 = ASR trên WAV giọng thật (kiểm đường ống, chưa phải bảng)")
        run_asr_probe(key)
    return 0


def run_asr_probe(api_key: str | None) -> None:
    """Chép vài WAV giọng thật bằng CẢ HAI backend và in nhãn — chứng minh hai thước.

    Dùng `desktop/logs/utts` + ground truth đã sửa lượt #17
    (`docs/baseline/realvoice_2026-09-06_v2_refs.json`). Không thu thêm giọng nào.
    """
    from langconf.asr import ASRBank

    refs_path = ROOT.parents[1] / "docs" / "baseline" / "realvoice_2026-09-06_v2_refs.json"
    refs = json.loads(refs_path.read_text(encoding="utf-8"))
    utts = DESKTOP / "logs" / "utts"
    names = sorted(refs)[:3]

    bank = ASRBank(api_key=api_key, languages=("vi", "en"))     # hạng DESKTOP_V3
    print(f"  hạng backend: {bank.tier} (baseline v3, chỉ vi/en)")
    print(f"  {'file':<26}{'thật':<6}{'backend':<20}{'nhãn':<6}{'p':<6}chép")
    for name in names:
        gold = refs[name]
        for backend in ("gemini-audio", "phowhisper-reread"):
            if backend == "gemini-audio" and not bank.has_gemini:
                continue
            heard = bank.transcribe(utts / name, backend)
            flag = "" if heard.lang == gold["lang"] else "   <-- NHÃN SAI"
            print(f"  {name:<26}{gold['lang']:<6}{backend:<20}{heard.lang:<6}"
                  f"{heard.lang_p:<6.2f}{heard.text[:44]!r}{flag}")
    print()
    print("  Nhãn sai ở đây KHÔNG phải lỗi của LLM. Đó là lý do bảng F1 phải có hai")
    print("  cột: 'tuân lệnh' chấm theo nhãn này, 'đúng thực tế' chấm theo cột 'thật'.")


if __name__ == "__main__":
    raise SystemExit(main())
