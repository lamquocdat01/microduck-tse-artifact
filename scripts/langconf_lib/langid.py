"""Nhận dạng ngôn ngữ hai thước: fastText lid.176 (thước chính) + lingua (thước soi).

Vì sao hai cái: Cohere chấm bằng fastText, nên **fastText là thước chính** — bỏ nó đi
là bảng của ta hết so được với bảng của họ. Nhưng fastText lid.176 nổi tiếng yếu với
câu ngắn, mà trợ lý giọng nói trả lời ngắn. lingua chạy song song để đo xem thước
chính có đang trôi không.

Quy tắc dừng (chủ nhân đặt): hai thước lệch quá **3 %** trên tập đã chấm thì DỪNG,
báo cáo, không tự chọn bên nào. `agreement_report()` trả đúng con số đó.

`unknown` là một nhãn hợp lệ, không phải lỗi: fastText dưới ngưỡng 0,3 và lingua
không quyết được đều ra `unknown`. Hai bên cùng `unknown` vẫn tính là **đồng thuận**.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# lingua trả về đối tượng Language; ta chỉ giữ mã ISO 639-1 hai chữ để so với fastText.
UNKNOWN = "unknown"

# Nhóm nhãn mà hai bộ nhận dạng gọi khác tên nhưng người đọc coi là MỘT.
#
# `id` (Indonesia) và `ms` (Mã Lai) là hai chuẩn hoá của cùng một ngôn ngữ, hiểu lẫn
# nhau được. lingua chạy `from_all_languages()` có cả hai trong kho và rất hay chọn
# `ms` cho câu tiếng Indonesia; fastText thì thiên về `id`. Đo trên 22 530 câu trả lời
# thật: **420 trong 437 ca lệch (96 %) đúng là cặp này**. Bỏ nó ra thì tỉ lệ lệch rơi
# từ 1,94 % xuống 0,08 %.
#
# Đây KHÔNG phải hai thước bất đồng về việc model trả lời đúng ngôn ngữ hay chưa — nó
# là bất đồng về cách đặt tên. Cổng 3 % sinh ra để bắt "thước chính đang trôi", nên
# gộp cặp này lại là đúng mục đích của cổng. Nhưng **chỉ gộp ở cổng đồng thuận**:
# LPR/WPR vẫn chấm bằng fastText với mã `id` y như Cohere, không đụng vào.
EQUIVALENT = ({"id", "ms"},)


def _same_language(a: str, b: str) -> bool:
    if a == b:
        return True
    return any(a in group and b in group for group in EQUIVALENT)


@dataclass(frozen=True)
class LangVerdict:
    text_len: int
    fasttext: str
    fasttext_p: float
    lingua: str
    lingua_p: float

    @property
    def agree(self) -> bool:
        """Đồng thuận CHẶT: hai thước trả về đúng cùng một mã."""
        return self.fasttext == self.lingua

    @property
    def agree_language(self) -> bool:
        """Đồng thuận theo NGÔN NGỮ: `id` và `ms` tính là một (xem EQUIVALENT)."""
        return _same_language(self.fasttext, self.lingua)

    def as_dict(self) -> dict:
        return {
            "fasttext": self.fasttext,
            "fasttext_p": round(self.fasttext_p, 4),
            "lingua": self.lingua,
            "lingua_p": round(self.lingua_p, 4),
            "agree": self.agree,
            "agree_language": self.agree_language,
        }


class DualLangID:
    """Chấm ngôn ngữ ở mức CẢ CÂU TRẢ LỜI (khác với LPR chấm từng dòng).

    Dùng cho hai thước "tuân lệnh" / "đúng thực tế". LPR/WPR vẫn do
    `cohere_metrics.CohereScorer` lo, theo đúng công thức của họ.
    """

    def __init__(self, lid_path: str | Path, fasttext_threshold: float = 0.3) -> None:
        import fasttext
        from lingua import LanguageDetectorBuilder

        self._ft = fasttext.load_model(str(lid_path))
        self._threshold = fasttext_threshold
        # from_all_languages: KHÔNG bó vào 4 ngôn ngữ của thí nghiệm. Bó lại thì
        # detector buộc phải chọn một trong bốn, và tỉ lệ đồng thuận sẽ đẹp giả tạo —
        # đúng cái ta cần phát hiện là câu trả lời trôi sang ngôn ngữ THỨ NĂM.
        self._lingua = LanguageDetectorBuilder.from_all_languages().build()
        self._verdicts: list[LangVerdict] = []

    def _flatten(self, text: str) -> str:
        """fastText xử lý một dòng một lần; gộp xuống dòng thành khoảng trắng."""
        return " ".join((text or "").split())

    def detect_fasttext(self, text: str) -> str:
        """CHỈ fastText, không chạy lingua. Dùng cho LCE ở mức câu và mức từ.

        `detect()` chạy cả hai thước — đúng cho việc soi câu trả lời (mỗi lượt một
        lần), nhưng sai cho LCE: LCE gọi nhận dạng ~40 lần MỖI lượt (một lần mỗi từ).
        Đo được: `detect()` 0,199 ms/từ, chỉ fastText 0,006 ms/từ — **33 lần**. Trên
        61 200 lượt đó là 8 phút so với 12 giây, cho một con số mà `lce.py` vốn đã
        khai là dùng fastText.

        Không ghi vào sổ đồng thuận: cổng 3 % nói về nhãn của CẢ câu trả lời, không
        phải nhãn của từng từ (mức từ vốn nhiều nhiễu, xem `lce.py`).
        """
        flat = self._flatten(text)
        if not flat:
            return UNKNOWN
        predictions = self._ft.f.predict(flat + "\n", 1, 0.0, "strict")
        if not predictions:
            return UNKNOWN
        score, label = predictions[0]
        return label.removeprefix("__label__") if score > self._threshold else UNKNOWN

    def detect(self, text: str, record: bool = True) -> LangVerdict:
        flat = self._flatten(text)
        if not flat:
            verdict = LangVerdict(0, UNKNOWN, 0.0, UNKNOWN, 0.0)
        else:
            predictions = self._ft.f.predict(flat + "\n", 1, 0.0, "strict")
            if predictions:
                score, label = predictions[0]
                ft_lang = label.removeprefix("__label__") if score > self._threshold else UNKNOWN
                ft_p = float(score)
            else:
                ft_lang, ft_p = UNKNOWN, 0.0

            values = self._lingua.compute_language_confidence_values(flat)
            if values and values[0].value > 0.0:
                lingua_lang = values[0].language.iso_code_639_1.name.lower()
                lingua_p = float(values[0].value)
            else:
                lingua_lang, lingua_p = UNKNOWN, 0.0

            verdict = LangVerdict(len(flat), ft_lang, ft_p, lingua_lang, lingua_p)

        if record:
            self._verdicts.append(verdict)
        return verdict

    def agreement_report(self, threshold: float = 0.03) -> dict:
        """Tỉ lệ hai thước lệch nhau. Vượt `threshold` -> `stop` = True."""
        total = len(self._verdicts)
        if total == 0:
            return {"n": 0, "agree": 0, "disagree": 0, "disagree_rate": 0.0, "stop": False}
        strict = sum(not v.agree for v in self._verdicts)
        # Cổng chấm theo đồng thuận NGÔN NGỮ, không theo mã: `id` vs `ms` là bất đồng
        # về tên gọi, không phải về việc model có trả lời đúng thứ tiếng hay không.
        # Báo cả hai con số để người đọc tự thấy phần nào là tên gọi.
        real = sum(not v.agree_language for v in self._verdicts)
        rate = real / total
        examples = [
            {"len": v.text_len, "fasttext": v.fasttext, "lingua": v.lingua}
            for v in self._verdicts
            if not v.agree_language
        ][:20]
        return {
            "n": total,
            "agree": total - real,
            "disagree": real,
            "disagree_rate": rate,
            "disagree_strict": strict,
            "disagree_rate_strict": strict / total,
            "threshold": threshold,
            "stop": rate > threshold,
            "examples": examples,
        }

    def reset(self) -> None:
        self._verdicts.clear()
