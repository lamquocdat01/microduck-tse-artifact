"""LPR / WPR — bản port TRUNG THÀNH của `compute_metrics.py` (Cohere Labs, EMNLP 2024).

Nguồn: https://github.com/Cohere-Labs-Community/language-confusion (bản `main`,
tải 07/09/2026). Bài báo: arXiv 2406.20052.

Vì sao port lại thay vì `pip install` repo của họ: repo là script một file, đọc CSV
và `open('words')` theo đường dẫn tương đối, và nó gọi `fasttext.predict()` — hàm này
**vỡ với numpy 2.x** (`np.array(obj, copy=False)`), mà `desktop/.venv` đang dùng
numpy 2.4.6. Ở đây gọi thẳng `model.f.predict()` — đúng cái mà bản gốc gọi bên trong,
chỉ bỏ đoạn bọc numpy hỏng. Xem `_predict_label()`.

**Luật ở file này: không "cải tiến" gì cả.** Mọi chi tiết dưới đây là của họ, kể cả
những chỗ trông như lỗi — vì bảng của ta phải so được với bảng của họ:

- `normalize()` cắt ở `\nQ:`, bỏ **string.punctuation** (chỉ ASCII), thay `—` và `،`.
- Tách dòng bằng `\n`; tách từ bằng `line.split()` cho mọi ngôn ngữ trừ zh/ja.
  → **ko cũng tách theo khoảng trắng**, đúng như bản gốc.
- **Dòng dưới 5 token bị bỏ.** Câu trả lời mà không còn dòng nào ≥5 token thì
  KHÔNG được tính vào mẫu số (`non_skipped`). Đây là chi tiết chí mạng với ta:
  trợ lý giọng nói trả lời ngắn, nên tỉ lệ bị bỏ phải được báo cáo, xem `skipped`.
- `langid()`: fastText lid.176, top-1, `score > 0.3` mới nhận, không thì `unknown`
  (và `unknown != lang` nên tính là lỗi dòng).
- LPR = 1 − (số câu trả lời có ≥1 dòng sai) / non_skipped.
- WPR **chỉ tính cho ar, hi, ja, ko, ru, zh** — họ ghi rõ WPR không đáng tin với
  ngôn ngữ chữ Latin. Trong 4 ngôn ngữ của ta, **chỉ `ko` có WPR**; vi/en/id là N/A.
  Đừng bịa WPR cho vi/id để bảng "đẹp".
- WPR = 1 − (số câu có lỗi từ) / (non_skipped − số câu có lỗi dòng).
- Từ điển tiếng Anh: gist wchargin/8927565, chỉ giữ từ `islower()` và `len > 3`.

Khác biệt duy nhất so với bản gốc, và đều là mở rộng KHÔNG đổi số:
1. `CohereScorer` giữ model + từ điển trong một object thay vì biến toàn cục, để
   chạy nhiều cell trong một tiến trình.
2. Trả thêm `n`, `skipped`, `line_errors`, `word_errors` và cờ per-response
   (`per_response`) — cần cho bootstrap CI và để chấm lại offline.
3. `lcpr` = trung bình điều hoà LPR/WPR (bài báo có, script của họ không tính).
"""

from __future__ import annotations

import functools
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# Ngôn ngữ mà bài báo tính WPR. Chữ Latin không có trong danh sách này.
WPR_LANGS = ("ar", "hi", "ja", "ko", "ru", "zh")

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize(text: str) -> str:
    """Y hệt `normalize()` của bản gốc."""
    text = (text or "").split("\nQ:")[0].strip()
    text = text.translate(_PUNCT_TABLE)
    text = text.replace("—", " ")
    text = text.replace("،", "")
    return text


@functools.lru_cache(maxsize=2 ** 20)
def tokenize(line: str, lang: str) -> tuple[str, ...]:
    """Bản gốc chỉ tách đặc biệt cho zh (jieba) và ja (fugashi).

    Bốn ngôn ngữ của ta (vi, en, id, ko) đều rơi vào nhánh `line.split()`.
    Giữ nhánh zh/ja ở đây để ai mở rộng sang 15 ngôn ngữ không phải sửa công thức,
    nhưng import nằm trong hàm nên không bắt cài jieba/fugashi.
    """
    if lang == "zh":
        import jieba

        return tuple(jieba.cut(line))
    if lang == "ja":
        from fugashi import Tagger

        return tuple(Tagger("-O wakati -b 50000").parse(line).split())
    return tuple(line.split())


@dataclass
class ResponseVerdict:
    """Phán quyết cho MỘT câu trả lời — đơn vị để bootstrap lấy mẫu lại."""

    skipped: bool           # không còn dòng nào ≥5 token -> bản gốc bỏ hẳn khỏi mẫu số
    n_lines: int            # số dòng còn lại sau khi lọc
    line_errors: int        # số dòng bị fastText gán khác `lang`
    has_line_error: bool
    has_word_error: bool    # chỉ có nghĩa khi has_line_error == False
    line_acc: float         # 1 - line_errors/n_lines ; NaN nếu skipped
    line_langs: tuple[str, ...] = ()   # fastText đoán gì cho từng dòng (để soi lại)


@dataclass
class Metrics:
    lang: str
    n: int                  # tổng số câu trả lời đưa vào
    non_skipped: int
    skipped: int
    with_line_errors: int
    with_word_errors: int
    acc: float
    lpr: float
    wpr: float | None       # None cho ngôn ngữ chữ Latin — đúng như bản gốc
    lcpr: float | None
    per_response: list[ResponseVerdict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "lang": self.lang,
            "n": self.n,
            "non_skipped": self.non_skipped,
            "skipped": self.skipped,
            "with_line_errors": self.with_line_errors,
            "with_word_errors": self.with_word_errors,
            "acc": self.acc,
            "lpr": self.lpr,
            "wpr": self.wpr,
            "lcpr": self.lcpr,
        }


class CohereScorer:
    """Giữ lid.176 + từ điển tiếng Anh. Dựng một lần, dùng cho mọi cell."""

    def __init__(self, lid_path: str | Path, words_path: str | Path) -> None:
        import fasttext

        self.lid_path = str(lid_path)
        self.words_path = str(words_path)
        with open(self.words_path, encoding="utf-8") as handle:
            words = [line.strip() for line in handle]
        # Bản gốc: chỉ giữ từ thường và dài hơn 3 ký tự.
        self.en_words = {w for w in words if w.islower() and len(w) > 3}
        self._model = fasttext.load_model(self.lid_path)

    def _predict_label(self, line: str) -> tuple[str, float]:
        """Bằng đúng `model.predict(line, k=1)` của fastText, tránh numpy 2.x.

        `FastText.predict()` làm hai việc: chặn `\\n` rồi nối `"\\n"` vào cuối, và
        gọi `self.f.predict(text, k, threshold, on_unicode_error)`. Chỉ khúc bọc
        `np.array(probs, copy=False)` ở cuối là vỡ với numpy 2.x, mà ta không cần
        khúc đó. Nên gọi thẳng `self._model.f.predict`, giữ nguyên hai bước trên.
        """
        if "\n" in line:
            raise ValueError("langid xử lý một dòng một lần (bỏ '\\n')")
        predictions = self._model.f.predict(line + "\n", 1, 0.0, "strict")
        if not predictions:
            return "unknown", 0.0
        score, label = predictions[0]
        return label.removeprefix("__label__"), float(score)

    def langid(self, line: str) -> str:
        """Y hệt `langid()` của bản gốc: ngưỡng 0,3, dưới ngưỡng là `unknown`."""
        label, score = self._predict_label(line)
        return label if score > 0.3 else "unknown"

    def judge(self, completion: str, lang: str) -> ResponseVerdict:
        """Chấm MỘT câu trả lời theo đúng vòng lặp trong `compute_metrics()`."""
        completion = normalize(completion)
        lines = completion.split("\n")
        line_tokens = [tokenize(line, lang) for line in lines]
        indices = [i for i, toks in enumerate(line_tokens) if len(toks) >= 5]
        lines = [lines[i] for i in indices]
        line_tokens = [line_tokens[i] for i in indices]

        if not lines:
            return ResponseVerdict(True, 0, 0, False, False, float("nan"))

        langs = tuple(self.langid(line) for line in lines)
        line_errors = sum(detected != lang for detected in langs)
        has_line_error = line_errors > 0
        has_word_error = False
        if not has_line_error:
            has_word_error = any(
                token.strip() in self.en_words for toks in line_tokens for token in toks
            )
        return ResponseVerdict(
            skipped=False,
            n_lines=len(lines),
            line_errors=line_errors,
            has_line_error=has_line_error,
            has_word_error=has_word_error,
            line_acc=1 - line_errors / len(lines),
            line_langs=langs,
        )

    def compute_metrics(self, completions: Iterable[str], lang: str) -> Metrics:
        """Bằng `compute_metrics(completions, lang)` của bản gốc, cộng thêm chi tiết."""
        verdicts = [self.judge(c, lang) for c in completions]
        return self.aggregate(verdicts, lang)

    @staticmethod
    def aggregate(verdicts: Sequence[ResponseVerdict], lang: str) -> Metrics:
        """Gộp các phán quyết -> LPR/WPR. Tách riêng để bootstrap gọi lại nhiều lần.

        Chú ý `max(1, ...)` ở mẫu số: bản gốc làm vậy, ta giữ. Nó khiến cell rỗng ra
        LPR = 1,0 chứ không lỗi chia 0 — nên LUÔN đọc kèm `non_skipped`.
        """
        non_skipped = sum(not v.skipped for v in verdicts)
        with_line_errors = sum(v.has_line_error for v in verdicts if not v.skipped)
        with_word_errors = sum(v.has_word_error for v in verdicts if not v.skipped)
        accs = [v.line_acc for v in verdicts if not v.skipped]

        lpr = 1 - with_line_errors / max(1, non_skipped)
        wpr = None
        if lang in WPR_LANGS:
            wpr = 1 - with_word_errors / max(1, non_skipped - with_line_errors)
        lcpr = None
        if wpr is not None and (lpr + wpr) > 0:
            lcpr = 2 * (lpr * wpr) / (lpr + wpr)

        return Metrics(
            lang=lang,
            n=len(verdicts),
            non_skipped=non_skipped,
            skipped=len(verdicts) - non_skipped,
            with_line_errors=with_line_errors,
            with_word_errors=with_word_errors,
            acc=sum(accs) / len(accs) if accs else 1.0,
            lpr=lpr,
            wpr=wpr,
            lcpr=lcpr,
            per_response=list(verdicts),
        )
