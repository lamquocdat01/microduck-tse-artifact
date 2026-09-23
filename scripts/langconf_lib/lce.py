"""Language Confusion Entropy (LCE) — thước mịn, bổ sung cho LPR/WPR nhị phân.

Chen, Li, Biswas & Bjerva, **"Large Language Models are Easily Confused: A Quantitative
Metric, Security Implications and Typological Analysis"**, arXiv:2410.13237.
Code: <https://github.com/siebeniris/QuantifyingLanguageConfusion>
(`src/analysis_language_confusion/language_confusion_for_prompting.py`).

## Công thức, nguyên văn của họ

    H_C(X) = − Σ_{x∈X₁} (1 − p(x))·log p(x)  −  Σ_{x∈X₂} p(x)·log p(x)

X₁ = ngôn ngữ ĐÍCH, X₂ = mọi ngôn ngữ khác, p(x) = tỉ lệ đơn vị được gán cho x.
Cài đặt của họ (`get_reweighted_entropy`) chỉ cộng trên những ngôn ngữ **thật sự xuất
hiện** trong phân bố, và họ thêm một ô `"unk"` bằng phần thiếu khi tổng < 1.

Vì sao nó bổ sung được cho LPR: LPR nhị phân — một dòng sai là hỏng cả câu trả lời.
LCE bắt được "nhiễm một phần" (60 % đúng ngôn ngữ, 40 % lệch) mà LPR vẫn chấm là
hỏng y như 100 % lệch. Ở độ sâu nhiễm THẤP, chỗ hiệu ứng còn yếu, đó đúng là chỗ LPR
dễ bỏ sót.

## ⚠ Hai cảnh báo phải in kèm mọi bảng LCE

**1. LCE = 0 cho cả câu trả lời HOÀN HẢO lẫn câu SAI HẲN.** Trả lời trọn vẹn bằng
ngôn ngữ đích: p(đích) = 1 → −(1−1)·log 1 = 0. Trả lời trọn vẹn bằng ngôn ngữ SAI:
ngôn ngữ đích không có trong phân bố nên không đóng góp gì, còn ngôn ngữ sai có
p = 1 → −1·log 1 = 0. **Hai ca ngược nhau, cùng một số.** LCE đo *độ trộn lẫn*, không
đo *độ đúng*. Nên nó không bao giờ được đứng một mình — luôn đọc cạnh LPR/match.

**2. Mức "dòng" của họ vô dụng với dữ liệu của ta.** Họ tách theo `\\n`, giả định câu
trả lời nhiều dòng (danh sách, markdown). Trợ lý giọng nói của ta trả lời 2–3 câu
liền một đoạn — một dòng duy nhất → phân bố suy biến p = 1,0 → LCE ≡ 0 với MỌI lượt.
Nên ở đây tính LCE ở hai mức khác:

    câu (sentence)  tách theo dấu chấm câu. Đây là bản THAY THẾ cho mức dòng của họ,
                    hợp với văn nói. Ghi rõ là ta đi chệch, và vì sao.
    từ (word)       đúng như họ đặc tả. Nhận dạng từng từ bằng fastText vì nhanh
                    (~10 µs/từ); lingua chính xác hơn nhưng ~1 ms/từ, tức là gấp
                    trăm lần cho 3 triệu từ của mẻ chạy đầy đủ.

Nhận dạng ngôn ngữ ở mức một từ vốn không đáng tin — chính Cohere ghi điều đó trong
phần Hạn chế của họ. Con số mức từ ở đây là **chỉ dấu**, không phải bằng chứng.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .cohere_metrics import normalize

# Tách câu cho văn nói: dấu kết câu + khoảng trắng. Không dùng thư viện tách câu —
# thêm phụ thuộc cho một việc mà chuỗi hai dòng làm xong, và tiếng Hàn/Việt/Indonesia
# đều kết câu bằng đúng những dấu này.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？…])\s+|\n+")

UNK = "unk"


@dataclass
class Entropy:
    value: float
    n_units: int
    distribution: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "lce": round(self.value, 4),
            "n_units": self.n_units,
            "dist": {k: round(v, 3) for k, v in self.distribution.items()},
        }


def reweighted_entropy(distribution: dict[str, float], target_lang: str) -> float:
    """H_C theo đúng `get_reweighted_entropy` của họ.

    Chỉ cộng trên ngôn ngữ CÓ MẶT trong phân bố — ngôn ngữ đích vắng mặt thì không
    đóng góp gì (xem cảnh báo 1 ở đầu file). p ≤ 0 bị bỏ qua để tránh log(0); trong
    phân bố dựng từ đếm đơn vị thì chuyện đó không xảy ra.
    """
    total = 0.0
    for lang, prob in distribution.items():
        if prob <= 0.0:
            continue
        if lang == target_lang:
            total -= (1.0 - prob) * math.log(prob)
        else:
            total -= prob * math.log(prob)
    return total


def _distribution(units: list[str], detect) -> dict[str, float]:
    """Tỉ lệ đơn vị theo ngôn ngữ. `unknown` gom vào ô `unk`, y như họ."""
    if not units:
        return {}
    counts = Counter(detect(u) or UNK for u in units)
    counts = Counter({(UNK if k in (None, "unknown") else k): v for k, v in counts.items()})
    n = sum(counts.values())
    return {lang: count / n for lang, count in counts.items()}


def sentences(text: str) -> list[str]:
    """Tách câu trả lời thành câu. Bỏ mảnh rỗng và mảnh chỉ có dấu câu."""
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text or "") if p and p.strip()]
    return [p for p in parts if normalize(p).strip()]


def words(text: str) -> list[str]:
    """Tách từ sau khi bỏ dấu câu, theo đúng cách Cohere tách (`line.split()`).

    Bỏ từ dài dưới 2 ký tự: fastText đoán ngôn ngữ của một từ một ký tự là tung đồng
    xu, và những từ ấy chiếm phần lớn nhiễu ở mức từ.
    """
    return [w for w in normalize(text).split() if len(w) >= 2]


def lce_sentence(text: str, target_lang: str, detect) -> Entropy:
    units = sentences(text)
    dist = _distribution(units, detect)
    return Entropy(reweighted_entropy(dist, target_lang), len(units), dist)


def lce_word(text: str, target_lang: str, detect) -> Entropy:
    units = words(text)
    dist = _distribution(units, detect)
    return Entropy(reweighted_entropy(dist, target_lang), len(units), dist)
