"""Dựng prompt. **Đây là chỗ DUY NHẤT sinh ra chữ gửi cho model.**

Nếu một chuỗi không được định nghĩa ở file này hoặc không đến từ FLEURS / bản chép
ASR, thì nó không có quyền xuất hiện trong prompt. `audit_messages()` ở cuối file là
bộ kiểm nhiễm tự động, chạy mỗi lượt, và ném lỗi chứ không cảnh báo.

## Khung nhiệm vụ hằng định (`TASK_FRAME`)

Mọi điều kiện đều có cùng một `TASK_FRAME` tiếng Anh, không đổi một chữ. Ba lý do:

1. F5 (vị trí nhãn) phải chỉ đo **vị trí của nhãn ngôn ngữ**. Nếu mức "không nhãn"
   cũng đồng thời là "không có system prompt", ta đo lẫn hai thứ.
2. Cohere ở thiết lập crosslingual cũng để chỉ thị bằng tiếng Anh. Giữ như họ thì
   bảng của ta đặt cạnh bảng của họ được.
3. `>= 5 token/dòng` là điều kiện sống còn của LPR (xem `cohere_metrics`): dòng ngắn
   hơn bị BỎ khỏi mẫu số. Câu mở "2 to 3 sentences" là cách duy nhất để trợ lý giọng
   nói không trả lời cụt và làm rỗng bảng. Con số bị bỏ vẫn được báo (`skipped`).

**Đây là một thiên lệch tiếng Anh có chủ ý và phải ghi vào phần Hạn chế.** Chính vì
vậy mà cặp `vi-ko` tồn tại: nếu tiếng Anh rò vào câu trả lời ở cặp không có tiếng Anh,
`TASK_FRAME` là nghi phạm đầu tiên và ta đo được điều đó.

## Nhãn ngôn ngữ (`LANGUAGE_LABEL`)

Viết bằng CHÍNH ngôn ngữ đích, đúng như hệ thống đang chạy thật (`docs/ADR-008`,
`LANGUAGE_TURN_TAG`). Câu chữ giống hệt nhau ở cả hai vị trí system/user, nên phép so
F5 là công bằng.

## Đơn vị nhiễm

Đặt T = ngôn ngữ đích của lượt đang hỏi, C = ngôn ngữ gây nhiễu (ngôn ngữ kia của cặp).

    một đơn vị nhiễm  = (người dùng nói bằng T, trợ lý đáp bằng **C**)
    một đơn vị sạch   = (người dùng nói bằng T, trợ lý đáp bằng **T**)

Nội dung hai bên **giống hệt** — cùng câu FLEURS, chỉ khác bản dịch. Nên biến duy
nhất thay đổi giữa sạch và nhiễm là NGÔN NGỮ của lượt trợ lý, không phải nội dung.
Đây đúng là khuôn "EN hỏi → VI đáp" đã tái lập được ở `docs/ADR-008` (2/15).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]
LabelPosition = Literal["none", "system", "user"]
InjectSource = Literal["history", "memory"]
HistoryKind = Literal["clean", "contaminated"]

# ---------------------------------------------------------------------------
# Chữ hằng định. KHÔNG sửa mà không cập nhật README + chạy lại toàn bộ.
# ---------------------------------------------------------------------------

TASK_FRAME = (
    "You are a voice assistant talking with a user. "
    "Respond naturally to what the user says, using 2 to 3 sentences."
)

# Nhãn viết bằng chính ngôn ngữ đích (docs/ADR-008). Ngoặc vuông giữ nguyên để nhãn
# tách bạch khỏi lời người dùng, y như bản đang chạy thật.
LANGUAGE_LABEL: dict[str, str] = {
    "vi": "[Trả lời bằng tiếng Việt.]",
    "en": "[Reply in English.]",
    "id": "[Jawab dalam bahasa Indonesia.]",
    "ko": "[한국어로 답하세요.]",
}

# Tiêu đề khối ký ức (F6 = memory). Tiếng Anh, hằng định, y hệt ở điều kiện sạch và
# nhiễm — nên nó không thể làm lợi cho bên nào.
MEMORY_HEADER = "Context retrieved from memory:"

LANGUAGES = ("vi", "en", "id", "ko")


@dataclass
class Turn:
    role: Role
    content: str

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class BuiltPrompt:
    """Prompt đã dựng xong + đủ siêu dữ liệu để kiểm lại mà không cần dựng lại."""

    messages: list[Turn]
    target_lang: str            # T — ngôn ngữ đáng lẽ phải trả lời
    label_lang: str | None      # nhãn NÓI ngôn ngữ nào (None nếu F5 = none)
    confuse_lang: str | None    # C
    label_position: LabelPosition
    depth: int
    history_kind: HistoryKind | None
    inject_source: InjectSource | None
    probe_id: str
    probe_text: str             # chữ thật sự nằm ở lượt người dùng (gold hoặc ASR)
    history_ids: list[str] = field(default_factory=list)

    def as_dicts(self) -> list[dict]:
        return [t.as_dict() for t in self.messages]


# ---------------------------------------------------------------------------
# Dựng
# ---------------------------------------------------------------------------


def build_prompt(
    *,
    probe_id: str,
    probe_text: str,
    target_lang: str,
    confuse_lang: str | None,
    label_lang: str | None,
    label_position: LabelPosition,
    depth: int,
    history_kind: HistoryKind | None,
    inject_source: InjectSource | None,
    history_user: list[tuple[str, str]],
    history_assistant: list[tuple[str, str]],
) -> BuiltPrompt:
    """Dựng danh sách lượt hội thoại.

    `history_user` / `history_assistant`: danh sách `(floresID, text)` đã ở ĐÚNG ngôn
    ngữ cần dùng, do `design.py` chọn. Hàm này không tự dịch, không tự chọn câu — nó
    chỉ ghép. Tách như vậy để bộ kiểm nhiễm còn kiểm được đầu vào.

    `depth = 0` -> không lịch sử, không ký ức, `history_kind`/`inject_source` là None.
    """
    if label_position != "none" and label_lang is None:
        raise ValueError("label_position != none thì phải có label_lang")
    if label_position == "none" and label_lang is not None:
        raise ValueError("label_position = none thì không được có label_lang")
    if depth == 0 and (history_kind is not None or inject_source is not None):
        raise ValueError("depth = 0 là ô dùng chung, không mang history_kind/inject_source")
    if depth > 0 and (history_kind is None or inject_source is None):
        raise ValueError("depth > 0 phải nói rõ history_kind và inject_source")

    system = TASK_FRAME

    if depth > 0 and inject_source == "memory":
        if len(history_assistant) != depth:
            raise ValueError(f"ký ức sâu {depth} cần {depth} mục, có {len(history_assistant)}")
        items = "\n".join(f"- {text}" for _, text in history_assistant)
        system = f"{system}\n\n{MEMORY_HEADER}\n{items}"

    if label_position == "system":
        system = f"{system}\n\n{LANGUAGE_LABEL[label_lang]}"

    messages: list[Turn] = [Turn("system", system)]
    history_ids: list[str] = []

    if depth > 0 and inject_source == "history":
        if len(history_user) != depth or len(history_assistant) != depth:
            raise ValueError(f"lịch sử sâu {depth} cần {depth} cặp")
        for (uid, utext), (aid, atext) in zip(history_user, history_assistant):
            messages.append(Turn("user", utext))
            messages.append(Turn("assistant", atext))
            history_ids += [uid, aid]
    elif depth > 0:
        history_ids = [aid for aid, _ in history_assistant]

    probe = probe_text
    if label_position == "user":
        # Nhãn CHỈ nằm ở bản gửi đi, không bao giờ được lưu vào lịch sử — nếu lưu thì
        # lượt sau model thấy nhãn trong lịch sử và bắt chước (docs/ADR-008). Ở đây
        # lịch sử là tổng hợp nên điều đó tự đúng, nhưng ghi lại để ai sửa còn biết.
        probe = f"{probe}\n\n{LANGUAGE_LABEL[label_lang]}"
    messages.append(Turn("user", probe))

    return BuiltPrompt(
        messages=messages,
        target_lang=target_lang,
        label_lang=label_lang,
        confuse_lang=confuse_lang,
        label_position=label_position,
        depth=depth,
        history_kind=history_kind,
        inject_source=inject_source,
        probe_id=probe_id,
        probe_text=probe_text,
        history_ids=history_ids,
    )


# ---------------------------------------------------------------------------
# Kiểm nhiễm test set — dựng lại nguyên văn, chạy MỖI lượt, ném lỗi chứ không cảnh báo
# ---------------------------------------------------------------------------
#
# Cách làm: KHÔNG dò chuỗi con. Dò chuỗi con vừa lọt vừa báo động giả — câu FLEURS
# tiếng Indonesia có chữ "bahasa" (nghĩa là "ngôn ngữ"), câu tiếng Việt có "Việt Nam",
# nên mọi bộ lọc từ khoá đều sẽ kêu oan trên chính dữ liệu thật.
#
# Thay vào đó: **dựng lại prompt từ các mảnh được phép rồi so từng ký tự**. Mảnh được
# phép chỉ gồm (a) hằng số khai báo ở đầu file này, (b) chuỗi lấy nguyên văn từ FLEURS
# hoặc từ bản chép ASR. Khớp tuyệt đối nghĩa là không một ký tự nào lọt vào ngoài
# thiết kế — mạnh hơn mọi danh sách từ cấm.
#
# Gợi ý ngôn ngữ trong CHÍNH nội dung FLEURS (một câu nào đó tình cờ nói về tiếng Anh)
# là chuyện khác: không phải nhiễm, nhưng có thể gây nhiễu. Nó được BÁO CÁO qua
# `flag_language_mentions()`, để chủ nhân quyết loại hay giữ — script không tự quyết.

_LANGUAGE_HINTS = (
    "vietnamese", "tieng viet", "english", "tieng anh", "korean", "hanguk",
    "indonesian", "bahasa indonesia", "language", "ngon ngu", "linguistic",
)

_HANGUL = re.compile(r"[\uac00-\ud7af]")


def _fold(text: str) -> str:
    """Bỏ dấu, về chữ thường, gộp khoảng trắng — để dò gợi ý không né được bằng dấu."""
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    stripped = stripped.replace("\u0111", "d").replace("\u0110", "D")
    return re.sub(r"\s+", " ", stripped.lower()).strip()


class ContaminationError(AssertionError):
    """Prompt chứa thứ không nằm trong thiết kế. Dừng chạy, không chấm tiếp."""


def check_scaffolding_is_neutral() -> None:
    """Kiểm HẰNG SỐ của ta (không kiểm dữ liệu): khung + tiêu đề ký ức phải trung tính.

    Chạy một lần lúc khởi động. Nếu ai sửa `TASK_FRAME` thành "Reply in the user's
    language" thì cả thí nghiệm mất nghĩa, và chỗ này bắt được ngay.
    """
    for name, text in (("TASK_FRAME", TASK_FRAME), ("MEMORY_HEADER", MEMORY_HEADER)):
        folded = _fold(text)
        for hint in _LANGUAGE_HINTS:
            if hint in folded:
                raise ContaminationError(f"{name} chứa gợi ý ngôn ngữ {hint!r}")
        if _HANGUL.search(text):
            raise ContaminationError(f"{name} chứa chữ Hangul")
    for lang, label in LANGUAGE_LABEL.items():
        if lang not in LANGUAGES:
            raise ContaminationError(f"nhãn thừa cho ngôn ngữ {lang!r}")


def audit_messages(
    built: BuiltPrompt,
    *,
    allowed_texts: set[str],
    allowed_history_ids: set[str],
) -> None:
    """Dựng lại prompt từ mảnh được phép và so từng ký tự. Sai một ký tự là ném lỗi.

    `allowed_texts`: mọi chuỗi được phép làm nội dung một lượt — các câu FLEURS trong
    kho lịch sử, cộng chính `built.probe_text`. Câu thăm dò KHÁC không nằm trong tập
    này, nên một câu thăm dò lọt vào lịch sử sẽ bị bắt.
    `allowed_history_ids`: id được phép làm lịch sử/ký ức (phải rời khỏi tập thăm dò).
    """
    messages = built.messages
    roles = [t.role for t in messages]

    # 1. Khung hội thoại.
    if roles[0] != "system" or roles.count("system") != 1:
        raise ContaminationError(f"phải có đúng 1 lượt system ở đầu, thấy {roles}")
    if roles[-1] != "user":
        raise ContaminationError("lượt cuối phải là lượt thăm dò của người dùng")
    n_pairs = built.depth if built.inject_source == "history" else 0
    if roles[1:-1] != ["user", "assistant"] * n_pairs:
        raise ContaminationError(
            f"chờ {n_pairs} cặp user/assistant, thấy {roles[1:-1]}"
        )

    # 2. Dựng lại system prompt nguyên văn.
    expected_system = TASK_FRAME
    if built.depth > 0 and built.inject_source == "memory":
        # Bóc lại các mục ký ức rồi dựng lại khung quanh chúng: bước này kiểm KHUNG
        # (tiêu đề, dấu đầu dòng, chỗ đặt nhãn), còn NỘI DUNG từng mục do bước 3 kiểm
        # bằng cách đối chiếu với kho được phép. Tách hai việc để lỗi báo đúng chỗ.
        bullets = _memory_texts(messages[0].content)
        if len(bullets) != built.depth:
            raise ContaminationError(
                f"khối ký ức có {len(bullets)} mục, thiết kế đòi {built.depth}"
            )
        expected_system += "\n\n" + MEMORY_HEADER + "\n" + "\n".join(f"- {t}" for t in bullets)
    if built.label_position == "system":
        expected_system += "\n\n" + LANGUAGE_LABEL[built.label_lang]
    if messages[0].content != expected_system:
        raise ContaminationError(
            "system prompt không dựng lại được từ các mảnh được phép:\n"
            f"  có   : {messages[0].content!r}\n  chờ  : {expected_system!r}"
        )

    # 3. Mọi mảnh nội dung phải nằm trong tập được phép.
    body_texts = [t.content for t in messages[1:-1]]
    if built.depth > 0 and built.inject_source == "memory":
        body_texts += _memory_texts(messages[0].content)
    for text in body_texts:
        if text not in allowed_texts:
            raise ContaminationError(f"chuỗi ngoài kho được phép lọt vào prompt: {text!r}")

    # 4. Lượt thăm dò = probe_text [+ nhãn], khớp từng ký tự.
    expected_probe = built.probe_text
    if built.label_position == "user":
        expected_probe += "\n\n" + LANGUAGE_LABEL[built.label_lang]
    if messages[-1].content != expected_probe:
        raise ContaminationError(
            f"lượt thăm dò sai:\n  có  : {messages[-1].content!r}\n  chờ : {expected_probe!r}"
        )

    # 5. Nhãn xuất hiện đúng số lần trên TOÀN prompt (bắt nhãn lọt vào lịch sử).
    text_all = "\n".join(t.content for t in messages)
    for lang, label in LANGUAGE_LABEL.items():
        expected = 1 if (built.label_position != "none" and lang == built.label_lang) else 0
        if text_all.count(label) != expected:
            raise ContaminationError(
                f"nhãn {lang!r} xuất hiện {text_all.count(label)} lần, chờ {expected}"
            )

    # 6. id lịch sử phải thuộc kho dành riêng.
    stray = set(built.history_ids) - allowed_history_ids
    if stray:
        raise ContaminationError(f"lịch sử dùng id ngoài kho dành riêng: {sorted(stray)}")


def _memory_texts(system_content: str) -> list[str]:
    """Bóc lại các mục ký ức từ system prompt để đối chiếu với kho được phép."""
    if MEMORY_HEADER not in system_content:
        return []
    block = system_content.split(MEMORY_HEADER, 1)[1]
    # Nhãn ở system prompt (nếu có) nằm sau một dòng trống -> cắt ở đó.
    block = block.split("\n\n", 1)[0]
    return [line[2:] for line in block.strip().split("\n") if line.startswith("- ")]


def flag_language_mentions(pool: dict[str, dict[str, str]]) -> list[dict]:
    """BÁO CÁO (không chặn) câu FLEURS nào tự nhắc tới một ngôn ngữ.

    Không phải nhiễm — dữ liệu là dữ liệu — nhưng một câu thăm dò nói về tiếng Anh có
    thể tự nó kéo câu trả lời sang tiếng Anh. Chủ nhân xem danh sách rồi quyết loại
    hay giữ; script không tự loại vì loại đi là làm lệch mẫu.
    """
    flagged = []
    for sid, by_lang in sorted(pool.items()):
        for lang, text in by_lang.items():
            folded = _fold(text)
            hits = [h for h in _LANGUAGE_HINTS if h in folded]
            if hits:
                flagged.append({"id": sid, "lang": lang, "hints": hits, "text": text})
    return flagged


def render_verbatim(built: BuiltPrompt) -> str:
    """In NGUYÊN VĂN prompt để người soi. Không cắt, không tóm tắt."""
    out = []
    for i, turn in enumerate(built.messages):
        out.append(f"--- [{i}] {turn.role.upper()} ---")
        out.append(turn.content)
    return "\n".join(out)
