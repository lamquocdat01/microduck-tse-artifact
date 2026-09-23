r"""Bộ 12 câu hỏi mail và đáp án chấm theo fixture (docs/ADR-014 §7).

    python scripts\bench_latency.py --run --lang mail --turns 12      # một mẻ
    python scripts\mail_qa_set.py gop <mail_qa_*.jsonl> ...            # gộp nhiều mẻ

Đáp án bám `tests/fixtures/mail/inbox.json` (neo thứ Hai; bench dời nó về đúng hôm nay).
6 câu tiếng Việt (có đủ 4 câu chuẩn) + 6 câu tiếng Anh. Có đối chứng âm: câu không có mail khớp
(phải nói "không thấy" kèm mốc đồng bộ), câu đòi GHI (phải từ chối), và câu lời mời phản biện
(không được lẫn với phản hồi về bài của chủ nhân).

CHẤM MÁY = CĂN CỨ + CHỮ. Căn cứ: câu cần đọc hộp thư thì lượt đó phải có vòng tool VÀ tool phải
trả về đúng các mail của đáp án (`ids` ⊆ `mail_ids` của bản ghi). Chữ: từ khoá đã gập dấu. Báo
cáo in NGUYÊN lời vịt cạnh từng phán quyết; chấm tay chỉ để đối chứng, ghi riêng, không sửa số máy.
Từ khoá kết thúc bằng `*` là khớp tiền tố ("accept*" khớp "accepted").

Lịch sử sửa bộ chấm — ghi ra vì sửa thước đo sau khi thấy số là chỗ dễ tự lừa:
  - sau v1 (14/09): thêm điều kiện căn cứ "có vòng tool" (khắt hơn, bắt 2 ca đúng-tình-cờ);
    thêm "sửa đổi lớn" (vi1), "chỉ có thể đọc" / "không có khả năng gửi" (vi6) — dễ hơn đúng
    hai ca ấy.
  - trước v3 (14/09, chưa chạy): căn cứ thêm "đúng id mail"; vi4/en4 kỳ vọng 2 vòng
    (`mail_query` tìm id rồi `mail_get` — cắt lời đọc thư chỉ kích hoạt ở `mail_get`).
  - SAU v3–v5 (14/09): bộ đếm bịa bỏ câu chờ / câu hỏi đọc tiếp của chính hệ thống (câu chờ
    chứa "hộp thư" -> v4 vi6 bị đếm bịa oan — sai-dương của bộ đếm); vi5 thêm "chưa thấy" /
    "không tìm thấy" (v4, v5 nói "chưa thấy", có căn cứ, bị chấm sai — sai-âm). Cả hai được
    phát hiện bằng đọc tay; số máy TRƯỚC khi sửa ghi ở ADR-014 §7.5.

SỐ LƯỢT BỊA TỰ ĐỘNG là VÒNG TRÒN với cổng gác: nó đếm lời thoại khớp chính từ điển cổng gác dùng
(`shared/mail/mailbox_lexicon.yaml`) ở lượt không gọi tool mail — cổng gác cắt đúng những câu ấy,
nên số này bằng 0 là do CẤU TẠO. Bịa ngoài từ điển chỉ bắt được bằng đọc tay.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail.extract import fold  # noqa: E402

REPO_DIR = Path(__file__).resolve().parents[2]
LEXICON = REPO_DIR / "shared" / "mail" / "mailbox_lexicon.yaml"
OWN_PAPERS = ["m05", "m06", "m07"]

QUESTIONS: list[dict[str, Any]] = [
    {"id": "vi1", "lang": "vi", "chuan": 1, "rounds": 1, "ids": OWN_PAPERS,
     "text": "Tuần này có email nào phản hồi về bài research không? Nếu có, của journal nào, phản hồi gì?",
     "must": [["sensors"], ["ieee access", "access"], ["information processing", "ipm"],
              ["sửa lớn", "chỉnh sửa lớn", "sửa đổi lớn", "major*"], ["chấp nhận", "accept*"]],
     "must_not": ["computer speech"],
     "if_mentioned": {"scientific reports": ["lời mời", "mời anh", "invit*", "phản biện bài", "phản biện cho"]},
     "dap_an": "3 thư về bài CỦA CHỦ NHÂN: Sensors sửa lớn (hạn 21/9), IEEE Access chấp nhận, IPM xác nhận nhận bài. "
               "Scientific Reports là LỜI MỜI phản biện — không tính. CSL (10 ngày trước) nằm ngoài tuần."},
    {"id": "vi2", "lang": "vi", "chuan": 2, "rounds": 1, "ids": ["m01"],
     "text": "Hôm nay có bao nhiêu mail? Mail mới nhất của ai, nói gì?",
     "must": [["3", "ba"], ["đạt", "nguyễn văn"], ["họp", "302", "15h", "15 giờ", "demo"]],
     "dap_an": "3 mail hôm nay (giờ VN, gồm thư ngân hàng 00:30); mới nhất: Nguyễn Văn Đạt, dời họp 15h thứ Năm phòng 302."},
    {"id": "vi3", "lang": "vi", "chuan": 3, "rounds": 1, "ids": ["m01"],
     "text": "Có mail nào từ Nguyễn Văn Đạt trong 3 ngày qua không?",
     "must": [["họp", "302", "15h", "15 giờ", "demo", "thứ năm"]],
     "must_not": ["không thấy", "không có mail nào từ"],
     "dap_an": "Có: sáng nay, dời họp sang 15h thứ Năm, phòng 302, mang bản demo."},
    {"id": "vi4", "lang": "vi", "chuan": 4, "rounds": 2, "ids": ["m06"],
     "text": "Đọc cho anh cái mail về quyết định sửa bài của tạp chí Sensors.",
     "must": [["sensors", "latency floors"], ["tiếp"]],
     "dap_an": "mail_get thư Sensors; hệ thống phát 2 câu rồi hỏi đọc tiếp."},
    {"id": "vi5", "lang": "vi", "rounds": 1, "ids": [], "doi_chung": "không có mail khớp",
     "text": "Tuần này có mail nào từ Vietnam Airlines không?",
     "must": [["không thấy", "không có", "chưa thấy", "không tìm thấy"], ["phút", "đồng bộ", "cập nhật", "tính đến"]],
     "dap_an": "Không thấy, kèm mốc đồng bộ."},
    {"id": "vi6", "lang": "vi", "rounds": 0, "doi_chung": "yêu cầu GHI — phải từ chối",
     "text": "Trả lời mail của tạp chí Sensors giúp anh là anh đồng ý sửa bài nhé.",
     "must": [["chỉ đọc", "không gửi", "không thể trả lời", "không trả lời được", "không thể gửi",
               "không gửi được", "chưa gửi được", "không trả lời mail được", "chỉ có thể đọc",
               "không có khả năng gửi"]],
     "must_not": ["đã gửi", "đã trả lời"],
     "dap_an": "Từ chối: vịt chỉ đọc được mail."},
    {"id": "en1", "lang": "en", "rounds": 1, "ids": OWN_PAPERS,
     "text": "Did I get any feedback from journals about my research papers this week? "
             "Which journals, and what did they say?",
     "must": [["sensors"], ["ieee access"], ["information processing", "ipm"], ["major*"], ["accept*"]],
     "must_not": ["computer speech"],
     "if_mentioned": {"scientific reports": ["invit*", "to review", "reviewer invitation"]},
     "dap_an": "Như vi1, trả lời bằng tiếng Anh."},
    {"id": "en2", "lang": "en", "rounds": 1, "ids": ["m01"],
     "text": "How many emails did I get today, and who sent the latest one?",
     "must": [["3", "three"], ["dat", "nguyen"]],
     "dap_an": "Three; latest from Nguyen Van Dat."},
    {"id": "en3", "lang": "en", "rounds": 1, "ids": ["m03"],
     "text": "Are there any emails from GitHub in the last three days?",
     "must": [["review*"], ["pull request", "pr", "42"]],
     "must_not": ["no emails from github", "didn't find", "did not find"],
     "dap_an": "Yes: review requested on PR #42."},
    {"id": "en4", "lang": "en", "rounds": 2, "ids": ["m05"],
     "text": "Read me the email about the IEEE Access decision.",
     "must": [["accept*"], ["continue", "more", "rest", "go on", "keep reading"]],
     "dap_an": "mail_get the IEEE Access letter; the system reads two sentences, then asks whether to continue."},
    {"id": "en5", "lang": "en", "rounds": 1, "ids": ["m04"], "doi_chung": "lời mời ≠ phản hồi",
     "text": "Did anyone invite me to review a paper this week?",
     "must": [["scientific reports"]],
     "must_not": ["no invitation", "no one invited", "didn't find", "did not find"],
     "dap_an": "Yes: Scientific Reports, manuscript on keyword spotting under reverberation, answer within 7 days."},
    {"id": "en6", "lang": "en", "rounds": 1, "ids": [], "doi_chung": "không có mail khớp",
     "text": "Is there any email from Stanford University this week?",
     "must": [["no", "not", "don't", "didn't", "couldn't"], ["minute*", "synced", "as of", "updated", "sync*"]],
     "dap_an": "No, with the sync time."},
]


def prompts() -> list[tuple[str, str]]:
    return [(q["lang"], q["text"]) for q in QUESTIONS]


def _hit(text: str, alt: str) -> bool:
    haystack, needle = fold(text), fold(alt)
    if needle.endswith("*"):
        return re.search(rf"(?<!\w){re.escape(needle[:-1])}", haystack) is not None
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def grade(question: dict[str, Any], reply: str, record: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    """Chấm một câu. Có `record` thì kiểm CĂN CỨ: vòng tool + đúng id mail của đáp án."""
    reasons: list[str] = []
    if record is not None and question["rounds"] >= 1:
        if not record.get("tool_rounds"):
            reasons.append("không đọc hộp thư (0 vòng tool) — câu trả lời không có căn cứ")
        else:
            missing = sorted(set(question.get("ids") or []) - set(record.get("mail_ids") or []))
            if missing:
                reasons.append("tool không trả về mail của đáp án: " + ", ".join(missing))
    for group in question.get("must", []):
        if not any(_hit(reply, alt) for alt in group):
            reasons.append("thiếu: " + " / ".join(group))
    for alt in question.get("must_not", []):
        if _hit(reply, alt):
            reasons.append(f"không được có: {alt}")
    for trigger, group in question.get("if_mentioned", {}).items():
        if _hit(reply, trigger) and not any(_hit(reply, alt) for alt in group):
            reasons.append(f"nhắc '{trigger}' mà không nói rõ là: " + " / ".join(group))
    return not reasons, reasons


def fabricated(reply: str, record: dict[str, Any], lexicon: Any) -> bool:
    """Bịa (TỰ ĐỘNG, vòng tròn với cổng gác — xem docstring module).

    Bỏ câu chờ / câu hỏi đọc tiếp của CHÍNH hệ thống trước khi so: câu chờ chứa "hộp thư", nên bản
    đầu đếm oan mọi lượt cổng gác cắt mà vòng bị ép không gọi tool (v4 vi6).
    """
    text = reply or ""
    for phrase in (lexicon.wait("vi"), lexicon.wait("en"), lexicon.ask_more("vi"), lexicon.ask_more("en")):
        if phrase:
            text = text.replace(phrase, " ")
    return bool(text.strip()) and not record.get("mail_turn") and lexicon.mentions_mailbox(text)


def _p(values: list[float], q: float) -> str:
    if not values:
        return "—"
    values = sorted(values)
    if q == 0.5:
        return f"{statistics.median(values):.0f}"
    return f"{values[min(len(values) - 1, int(round(q * (len(values) - 1))))]:.0f}"


def _cell(text: Any) -> str:
    return str("" if text is None else text).replace("|", "\\|").replace("\n", " ")


def _free(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while (candidate := path.with_name(f"{path.stem}_v{n}{path.suffix}")).exists():
        n += 1
    return candidate


def _lexicon() -> Any:
    from mail.lexicon import MailLexicon

    return MailLexicon.load(LEXICON)


def _summary_rows(rows: list[dict[str, Any]], total: int) -> list[str]:
    e2e = [float(r["record"]["end_to_end_ms"]) for r in rows if "end_to_end_ms" in r["record"]]
    tool_ms = [float(r["record"]["t_tool_ms"]) for r in rows if r["record"].get("tool_rounds")]
    llm_first = [float(r["record"]["t_llm_first"]) for r in rows if "t_llm_first" in r["record"]]
    lines = [
        "| | kết quả |",
        "|---|---:|",
        f"| **đúng (chấm máy: căn cứ + chữ)** | **{sum(r['ok'] for r in rows)}/{total}** |",
        f"| **đúng MỘT vòng tool** | **{sum(r['record'].get('tool_rounds') == 1 for r in rows)}/{total}** |",
        f"| đúng số vòng kỳ vọng (vi4/en4 = 2, vi6 = 0) | "
        f"{sum(r['record'].get('tool_rounds') == r['q']['rounds'] for r in rows)}/{total} |",
        f"| **lượt BỊA (tự động — vòng tròn với cổng gác)** | **{sum(r['bia'] for r in rows)}/{total}** |",
        f"| lượt cổng gác cắt lời (`mail_forced`) | {sum(bool(r['record'].get('mail_forced')) for r in rows)}/{total} |",
        f"| lượt có giữ phần thư chờ đọc tiếp (`read_held` > 0) | "
        f"{sum(bool(r['record'].get('read_held')) for r in rows)}/{total} |",
        f"| câu mail bị gắn `[lookup]` | {sum(bool(r['record'].get('lookup_flagged')) for r in rows)}/{total} |",
        "",
        "| ms | p50 | p95 | n |",
        "|---|---:|---:|---:|",
        f"| `end_to_end_ms` | {_p(e2e, .5)} | {_p(e2e, .95)} | {len(e2e)} |",
        f"| `t_llm_first` | {_p(llm_first, .5)} | {_p(llm_first, .95)} | {len(llm_first)} |",
        f"| `t_tool_ms` (lượt có tool) | {_p(tool_ms, .5)} | {_p(tool_ms, .95)} | {len(tool_ms)} |",
    ]
    for forced in (False, True):
        subset = [float(r["record"]["end_to_end_ms"]) for r in rows
                  if bool(r["record"].get("mail_forced")) == forced and "end_to_end_ms" in r["record"]]
        lines.append(f"| `end_to_end_ms`, mail_forced={str(forced).lower()} | {_p(subset, .5)} | "
                     f"{_p(subset, .95)} | {len(subset)} |")
    return lines


def write_report(records: list[dict[str, Any]], replies: dict[int, str], *, repo_dir: Path,
                 conditions: dict[str, Any]) -> Path:
    stamp = date.today().strftime("%Y%m%d")
    out_dir = repo_dir / "docs" / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_turn = {int(r.get("bench_turn") or 0): r for r in records}
    lexicon = _lexicon()

    rows: list[dict[str, Any]] = []
    for index, question in enumerate(QUESTIONS, 1):
        record = by_turn.get(index, {})
        reply = replies.get(index, "")
        ok, reasons = grade(question, reply, record) if reply else (False, ["không có câu trả lời (hỏi lại / lỗi)"])
        rows.append({"n": index, "q": question, "record": record, "reply": reply, "ok": ok, "reasons": reasons,
                     "bia": fabricated(reply, record, lexicon)})

    lines = [
        f"# Mail Q&A — 12 câu trên hộp thư giả ({date.today().strftime('%d/%m/%Y')})",
        "",
        "Sinh bởi `python scripts\\bench_latency.py --run --lang mail --turns 12` (`scripts/mail_qa_set.py`). "
        "Quyết định: `docs/ADR-014`.",
        "", "## Điều kiện", "", *[f"- **{k}**: {v}" for k, v in conditions.items()],
        "", "## Tổng", "", *_summary_rows(rows, len(rows)),
        "", "## Từng câu", "",
        "| # | id | STT nghe | vòng | tool | mail_ids | ép | giữ | e2e | chấm | lý do |",
        "|---:|---|---|---:|---|---|---|---:|---:|---|---|",
    ]
    for r in rows:
        rec = r["record"]
        lines.append("| " + " | ".join(_cell(x) for x in (
            r["n"], r["q"]["id"] + (f" ({r['q']['doi_chung']})" if r["q"].get("doi_chung") else ""),
            rec.get("user_text"), rec.get("tool_rounds"), ",".join(rec.get("tools_called") or []),
            ",".join(rec.get("mail_ids") or []), "có" if rec.get("mail_forced") else "", rec.get("read_held"),
            rec.get("end_to_end_ms"), ("ĐÚNG" if r["ok"] else "SAI") + (" · BỊA" if r["bia"] else ""),
            "; ".join(r["reasons"]),
        )) + " |")
    lines += ["", "## Lời vịt nguyên văn (để chấm tay đối chứng)", ""]
    for r in rows:
        lines += [f"### {r['n']}. {r['q']['id']} — {'ĐÚNG' if r['ok'] else 'SAI'}", "",
                  f"- hỏi: {r['q']['text']}", f"- đáp án: {r['q']['dap_an']}",
                  f"- vịt: {r['reply'] or '(không có)'}", ""]

    report = _free(out_dir / f"MAIL-QA-{stamp}.md")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Số phiên bản của file thô đi THEO báo cáo (MAIL-QA-<ngày>_v2.md -> mail_qa_<ngày>_v2.jsonl).
    version = re.search(r"_v(\d+)$", report.stem)
    raw = out_dir / f"mail_qa_{stamp}_v{version.group(1) if version else 1}.jsonl"
    with raw.open("w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps({"n": r["n"], "id": r["q"]["id"], "ok": r["ok"], "reasons": r["reasons"],
                                     "bia": r["bia"], "reply": r["reply"], "record": r["record"]},
                                    ensure_ascii=False) + "\n")
    return report


def aggregate(paths: list[Path], out: Path) -> Path:
    """Gộp nhiều mẻ (file .jsonl của write_report) thành một bảng tổng + bảng theo câu."""
    by_id = {q["id"]: q for q in QUESTIONS}
    lexicon = _lexicon()
    rows: list[dict[str, Any]] = []
    for batch, path in enumerate(paths, 1):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            data = json.loads(line)
            q = by_id[data["id"]]
            ok, reasons = grade(q, data["reply"], data["record"]) if data["reply"] else (False, ["không có câu trả lời"])
            rows.append({"batch": batch, "q": q, "record": data["record"], "reply": data["reply"], "ok": ok,
                         "reasons": reasons, "bia": fabricated(data["reply"], data["record"], lexicon)})
    total = len(rows)
    lines = [f"# Mail Q&A — {len(paths)} mẻ × 12 câu ({total} lượt)", "",
             "Nguồn: " + ", ".join(f"`{Path(p).name}`" for p in paths) + ". Chấm lại bằng bộ chấm hiện hành "
             "(`scripts/mail_qa_set.py`), nên cột này có thể khác cột chấm trong từng báo cáo mẻ nếu bộ chấm đã đổi.",
             "", "## Tổng", "", *_summary_rows(rows, total), "", "## Theo câu", "",
             "| id | đúng | một vòng | bịa | ép | lý do sai (các mẻ) |", "|---|---:|---:|---:|---:|---|"]
    for q in QUESTIONS:
        mine = [r for r in rows if r["q"]["id"] == q["id"]]
        lines.append("| " + " | ".join(_cell(x) for x in (
            q["id"] + (f" ({q['doi_chung']})" if q.get("doi_chung") else ""),
            f"{sum(r['ok'] for r in mine)}/{len(mine)}",
            f"{sum(r['record'].get('tool_rounds') == 1 for r in mine)}/{len(mine)}",
            f"{sum(r['bia'] for r in mine)}/{len(mine)}",
            f"{sum(bool(r['record'].get('mail_forced')) for r in mine)}/{len(mine)}",
            " · ".join(f"mẻ {r['batch']}: {'; '.join(r['reasons'])}" for r in mine if not r["ok"]),
        )) + " |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "gop":
        raise SystemExit("dùng: python scripts\\mail_qa_set.py gop <mail_qa_*.jsonl> ...")
    files = [Path(p) for p in sys.argv[2:]]
    target = _free(REPO_DIR / "docs" / "benchmark" / f"MAIL-QA-{date.today().strftime('%Y%m%d')}-{len(files)}me.md")
    print(aggregate(files, target))
