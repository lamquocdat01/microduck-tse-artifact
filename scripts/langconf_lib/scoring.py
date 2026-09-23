"""Chấm điểm. Hai thước TÁCH RỜI, và khoảng tin cậy bootstrap cho mọi tỉ lệ.

## Vì sao phải tách hai thước

Ở điều kiện F1 = ASR, nhãn ngôn ngữ đưa cho LLM là do máy đoán, nên nó **có thể sai**.
Lúc đó "câu trả lời đúng hay sai" tách làm hai câu hỏi khác nhau:

    label obedience              reply_lang == label_lang
      "tuân lệnh nhãn"           LLM có làm theo NHÃN nó được đưa không?
    speaker-language accuracy    reply_lang == spoken_lang
      "đúng ngôn ngữ người nói"  người nói có được đáp đúng thứ tiếng họ dùng không?

TÊN GỌI — đặt có chủ đích, đừng đổi. **Không dùng "language adherence"**: thuật ngữ
đó đã bị DeepMind chiếm (arXiv 2606.17281, metric LAVR, đo ngôn ngữ của bản chép
trong model đa phương thức đầu-cuối). Trùng tên với một metric khác nghĩa là bảng
của ta sẽ bị đọc nhầm thành bảng của họ.

Gộp hai cái vào một ô là lặp lại đúng lỗi ground truth ở lượt #17 (`docs/ADR-008`:
thước cũ báo 16/30 "sai ngôn ngữ", tách ra thì là 3/30 lỗi STT + 13/30 lỗi LLM).
Một lượt mà STT nghe nhầm rồi LLM trả lời đúng theo cái nó nghe được là **LLM đúng,
hệ thống sai** — hai con số, hai người chịu trách nhiệm.

Ở F1 = oracle thì `label_lang == spoken_lang`, hai thước trùng nhau. Đó là phép kiểm
chính bộ chấm: chạy oracle mà hai thước ra số khác nhau là code hỏng.

Ở F5 = none không có nhãn -> **thước "tuân lệnh" không tồn tại**, chỉ báo "đúng thực
tế". Đừng điền 0 hay 1 vào ô đó; để trống.

## Hai cách đo "câu trả lời thuộc ngôn ngữ nào"

    lpr      theo đúng Cohere: chấm từng DÒNG, dòng dưới 5 token bị bỏ, cả câu trả
             lời chỉ cần một dòng sai là hỏng. Đây là số để đặt cạnh bảng của họ.
    match    một nhãn cho CẢ câu trả lời (fastText trên toàn văn). Đây là số so được
             với bảng cũ của chủ nhân ("2/15", "15/15") và không bị luật ≥5 token
             làm rỗng mẫu.

Báo cả hai. Chúng không thay thế nhau: `lpr` bỏ mẫu (xem `skipped`), `match` thì
không; `lpr` bắt được câu trả lời trộn hai thứ tiếng theo dòng, `match` thì không.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal, Sequence

from .cohere_metrics import WPR_LANGS, CohereScorer, ResponseVerdict

Ruler = Literal["label_obedience", "speaker_language_accuracy"]


@dataclass
class Judged:
    """Một lượt đã chấm xong theo MỘT thước."""

    ruler: Ruler
    ref_lang: str                 # ngôn ngữ dùng làm chuẩn cho thước này
    reply_lang: str               # fastText trên toàn văn
    reply_lang_lingua: str
    verdict: ResponseVerdict      # phán quyết theo dòng, kiểu Cohere
    match: bool                   # reply_lang == ref_lang

    def as_dict(self) -> dict:
        return {
            "ruler": self.ruler,
            "ref_lang": self.ref_lang,
            "reply_lang": self.reply_lang,
            "reply_lang_lingua": self.reply_lang_lingua,
            "match": self.match,
            "skipped": self.verdict.skipped,
            "line_errors": self.verdict.line_errors,
            "n_lines": self.verdict.n_lines,
            "has_line_error": self.verdict.has_line_error,
            "has_word_error": self.verdict.has_word_error,
        }


def ref_lang_for(record: dict, ruler: Ruler) -> str | None:
    """Ngôn ngữ chuẩn của một lượt theo thước đang dùng. None = thước không áp dụng."""
    if ruler == "speaker_language_accuracy":
        return record["spoken_lang"]
    return record.get("label_lang")          # None khi F5 = none


def judge_from_scored(record: dict, ruler: Ruler) -> Judged | None:
    """Dựng `Judged` từ dòng ĐÃ CHẤM (`scripts/enrich.py`) — không chạy lại nhận dạng.

    Nhanh hơn `judge()` khoảng hai bậc trên lưới đầy đủ, và quan trọng hơn: mọi bảng
    đọc cùng một bộ nhãn ngôn ngữ, nên hai bảng không thể lệch nhau vì chạy detector
    hai lần. Trả None nếu thước không áp dụng (F5 = none + label obedience).
    """
    prefix = "spk" if ruler == "speaker_language_accuracy" else "lbl"
    ref = record.get(f"{prefix}_ref_lang")
    if ref is None:
        return None
    verdict = ResponseVerdict(
        skipped=bool(record[f"{prefix}_skipped"]),
        n_lines=int(record[f"{prefix}_n_lines"] or 0),
        line_errors=int(record[f"{prefix}_line_errors"] or 0),
        has_line_error=bool(record[f"{prefix}_line_error"]),
        has_word_error=bool(record[f"{prefix}_word_error"]),
        line_acc=float("nan") if record[f"{prefix}_skipped"] else
        1 - (record[f"{prefix}_line_errors"] or 0) / max(1, record[f"{prefix}_n_lines"] or 1),
        line_langs=tuple(record.get(f"{prefix}_line_langs") or ()),
    )
    detected = record.get("reply_lang_fasttext") or "unknown"
    return Judged(
        ruler=ruler,
        ref_lang=ref,
        reply_lang=detected,
        reply_lang_lingua=record.get("reply_lang_lingua") or "unknown",
        verdict=verdict,
        match=detected == ref,
    )


def judge(
    record: dict,
    ruler: Ruler,
    scorer: CohereScorer,
    detector,
) -> Judged | None:
    """Chấm một lượt. Trả None nếu thước không áp dụng (F5 = none + thước tuân lệnh)."""
    ref = ref_lang_for(record, ruler)
    if ref is None:
        return None
    reply = record.get("reply_text") or ""
    verdict = scorer.judge(reply, ref)
    detected = detector.detect(reply)
    return Judged(
        ruler=ruler,
        ref_lang=ref,
        reply_lang=detected.fasttext,
        reply_lang_lingua=detected.lingua,
        verdict=verdict,
        match=detected.fasttext == ref,
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


@dataclass
class Rate:
    """Một tỉ lệ kèm khoảng tin cậy. **Không bao giờ báo số trần** (chủ nhân dặn)."""

    value: float
    lo: float
    hi: float
    n: int                        # mẫu số THẬT dùng để tính tỉ lệ này
    successes: float

    def as_dict(self) -> dict:
        return {
            "value": round(self.value, 4),
            "ci95": [round(self.lo, 4), round(self.hi, 4)],
            "n": self.n,
            "successes": round(self.successes, 2),
        }

    def __str__(self) -> str:
        if self.n == 0:
            return "—"
        return f"{self.value:.1%} [{self.lo:.1%}–{self.hi:.1%}] n={self.n}"


def bootstrap_rate(
    items: Sequence,
    statistic: Callable[[Sequence], tuple[float, int, float]],
    *,
    resamples: int = 10_000,
    seed: int = 20260907,
    alpha: float = 0.05,
) -> Rate:
    """Bootstrap phần trăm (percentile) ở mức MỘT CÂU TRẢ LỜI.

    Lấy mẫu lại chính các câu trả lời, không lấy mẫu lại "lỗi dòng": đơn vị độc lập
    của thí nghiệm là một lượt, và LPR vốn được định nghĩa trên câu trả lời.

    `statistic(mẫu) -> (tỉ lệ, mẫu số, số ca đạt)`. Trả mẫu số vì LPR có mẫu số riêng
    (`non_skipped`) khác với số phần tử đưa vào — bootstrap phải theo mẫu số ấy.
    """
    value, n, successes = statistic(items)
    if n == 0 or not items:
        return Rate(float("nan"), float("nan"), float("nan"), 0, 0.0)

    rng = random.Random(seed)
    size = len(items)
    draws = []
    for _ in range(resamples):
        sample = [items[rng.randrange(size)] for _ in range(size)]
        stat, sample_n, _ = statistic(sample)
        if sample_n > 0 and not math.isnan(stat):
            draws.append(stat)
    if not draws:
        return Rate(value, float("nan"), float("nan"), n, successes)
    draws.sort()
    lo = draws[max(0, int(round((alpha / 2) * (len(draws) - 1))))]
    hi = draws[min(len(draws) - 1, int(round((1 - alpha / 2) * (len(draws) - 1))))]
    return Rate(value, lo, hi, n, successes)


def _lpr_statistic(judged: Sequence[Judged]) -> tuple[float, int, float]:
    """LPR theo đúng Cohere: mẫu số là số câu KHÔNG bị bỏ."""
    kept = [j for j in judged if not j.verdict.skipped]
    if not kept:
        return float("nan"), 0, 0.0
    errors = sum(j.verdict.has_line_error for j in kept)
    return 1 - errors / len(kept), len(kept), len(kept) - errors


def _wpr_statistic(judged: Sequence[Judged]) -> tuple[float, int, float]:
    """WPR — chỉ với ngôn ngữ không dùng chữ Latin (Cohere: ar hi ja ko ru zh).

    Trong bốn ngôn ngữ của ta chỉ `ko` đủ điều kiện. Với vi/en/id, hàm này trả mẫu số
    0 và bảng sẽ in "—". Đừng thay bằng số khác cho bảng đỡ trống.
    """
    kept = [j for j in judged
            if not j.verdict.skipped and j.ref_lang in WPR_LANGS and not j.verdict.has_line_error]
    if not kept:
        return float("nan"), 0, 0.0
    errors = sum(j.verdict.has_word_error for j in kept)
    return 1 - errors / len(kept), len(kept), len(kept) - errors


def _match_statistic(judged: Sequence[Judged]) -> tuple[float, int, float]:
    """Tỉ lệ câu trả lời có nhãn ngôn ngữ toàn văn trùng chuẩn. Không bỏ câu nào."""
    if not judged:
        return float("nan"), 0, 0.0
    hits = sum(j.match for j in judged)
    return hits / len(judged), len(judged), hits


@dataclass
class CellSummary:
    key: tuple
    ruler: Ruler
    n_trials: int
    n_errors: int                 # lượt gọi model hỏng (mạng, quota) — không chấm
    lpr: Rate
    wpr: Rate
    match: Rate
    skipped: int
    reply_lang_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "key": list(self.key),
            "ruler": self.ruler,
            "n_trials": self.n_trials,
            "n_model_errors": self.n_errors,
            "skipped_by_line_rule": self.skipped,
            "lpr": self.lpr.as_dict(),
            "wpr": self.wpr.as_dict(),
            "match": self.match.as_dict(),
            "reply_lang_counts": self.reply_lang_counts,
        }


def summarize_cell(
    key: tuple,
    judged: Sequence[Judged],
    *,
    ruler: Ruler,
    n_errors: int = 0,
    resamples: int = 10_000,
    seed: int = 20260907,
) -> CellSummary:
    counts: dict[str, int] = {}
    for j in judged:
        counts[j.reply_lang] = counts.get(j.reply_lang, 0) + 1
    return CellSummary(
        key=key,
        ruler=ruler,
        n_trials=len(judged),
        n_errors=n_errors,
        lpr=bootstrap_rate(judged, _lpr_statistic, resamples=resamples, seed=seed),
        wpr=bootstrap_rate(judged, _wpr_statistic, resamples=resamples, seed=seed),
        match=bootstrap_rate(judged, _match_statistic, resamples=resamples, seed=seed),
        skipped=sum(j.verdict.skipped for j in judged),
        reply_lang_counts=dict(sorted(counts.items(), key=lambda kv: -kv[1])),
    )


def paired_difference_by_probe(
    a: dict[str, Judged],
    b: dict[str, Judged],
    statistic=_match_statistic,
    *,
    resamples: int = 2_000,
    seed: int = 20260907,
) -> Rate:
    """Hiệu hai tỉ lệ, bootstrap **GHÉP CẶP theo câu thăm dò**.

    Đây là con số chính của bài: "lịch sử nhiễm làm tụt bao nhiêu so với lịch sử sạch,
    ở cùng độ sâu". Hai ô dùng ĐÚNG cùng 50 câu FLoRes, khác nhau đúng một biến, nên
    lấy mẫu lại phải lấy theo CÂU chứ không lấy độc lập hai bên: lấy độc lập thì phương
    sai do "câu này khó hơn câu kia" bị tính hai lần và khoảng tin cậy rộng oan.

    Chỉ dùng phần giao của `probe_id` — lượt hỏng ở một bên thì bỏ cả cặp, vì so một
    bên 50 câu với một bên 48 câu là so hai tập câu khác nhau.
    """
    shared = sorted(set(a) & set(b))
    if not shared:
        return Rate(float("nan"), float("nan"), float("nan"), 0, 0.0)

    value_a, n_a, _ = statistic([a[p] for p in shared])
    value_b, n_b, _ = statistic([b[p] for p in shared])
    if n_a == 0 or n_b == 0:
        return Rate(float("nan"), float("nan"), float("nan"), 0, 0.0)

    rng = random.Random(seed)
    size = len(shared)
    draws = []
    for _ in range(resamples):
        picked = [shared[rng.randrange(size)] for _ in range(size)]
        stat_a, na, _ = statistic([a[p] for p in picked])
        stat_b, nb, _ = statistic([b[p] for p in picked])
        if na and nb and not (math.isnan(stat_a) or math.isnan(stat_b)):
            draws.append(stat_a - stat_b)
    if not draws:
        return Rate(value_a - value_b, float("nan"), float("nan"), size, 0.0)
    draws.sort()
    lo = draws[max(0, int(round(0.025 * (len(draws) - 1))))]
    hi = draws[min(len(draws) - 1, int(round(0.975 * (len(draws) - 1))))]
    return Rate(value_a - value_b, lo, hi, size, 0.0)


def paired_difference(
    a: Sequence[Judged],
    b: Sequence[Judged],
    statistic=_match_statistic,
    *,
    resamples: int = 10_000,
    seed: int = 20260907,
) -> Rate:
    """CI cho hiệu hai tỉ lệ (ví dụ: sâu 8 trừ sâu 0). Bootstrap ĐỘC LẬP hai bên.

    Không ghép cặp theo câu vì hai ô có thể lệch số lượt (lượt hỏng bị loại). Muốn
    ghép cặp thật thì phải lọc về giao của `probe_id` trước khi gọi — để chỗ gọi lo,
    vì chỉ chỗ đó mới biết ghép cặp có nghĩa hay không.
    """
    value_a, n_a, _ = statistic(a)
    value_b, n_b, _ = statistic(b)
    if n_a == 0 or n_b == 0:
        return Rate(float("nan"), float("nan"), float("nan"), 0, 0.0)

    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        sample_a = [a[rng.randrange(len(a))] for _ in range(len(a))]
        sample_b = [b[rng.randrange(len(b))] for _ in range(len(b))]
        stat_a, na, _ = statistic(sample_a)
        stat_b, nb, _ = statistic(sample_b)
        if na and nb and not (math.isnan(stat_a) or math.isnan(stat_b)):
            draws.append(stat_a - stat_b)
    if not draws:
        return Rate(value_a - value_b, float("nan"), float("nan"), min(n_a, n_b), 0.0)
    draws.sort()
    lo = draws[max(0, int(round(0.025 * (len(draws) - 1))))]
    hi = draws[min(len(draws) - 1, int(round(0.975 * (len(draws) - 1))))]
    return Rate(value_a - value_b, lo, hi, min(n_a, n_b), 0.0)
