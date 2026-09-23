"""Sáu yếu tố -> danh sách ô (cell) -> danh sách lượt (trial). Không gọi API ở đây.

    F1 label_condition  oracle | asr           (asr còn kèm tên backend STT)
    F2 model            3 model
    F3 pair             hướng (T, C): vi-en, id-en, ko-en, vi-ko, mỗi cặp hai chiều
    F4 depth            0, 1, 2, 4, 8
    F5 label_position   none | system | user
    F6 inject_source    history | memory

Quy ước ký hiệu dùng khắp gói: **T** = ngôn ngữ đích (người dùng đang nói, và câu trả
lời phải bằng thứ tiếng ấy). **C** = ngôn ngữ gây nhiễu (ngôn ngữ kia của cặp).

Hai chỗ dễ đếm nhầm, ghi rõ ở đây:

- `depth = 0` là **một ô dùng chung**: không lịch sử thì không có "sạch" hay "nhiễm",
  cũng không có "từ lịch sử" hay "từ ký ức". Đếm nó bốn lần là tự thổi phồng mẫu.
- Ở `depth > 0` mỗi (F6, độ sâu) có **hai** ô: `clean` và `contaminated`. Điều kiện
  sạch không phải là `depth = 0` — nó là lịch sử CÙNG độ dài nhưng toàn ngôn ngữ đích.
  Thiếu nó thì mọi khác biệt đo được có thể chỉ là "prompt dài hơn".

`trial_key()` sinh khoá tất định để chạy lại bỏ qua được lượt đã xong (resume).
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Iterator, Literal, Sequence

LabelCondition = Literal["oracle", "asr"]

# Cặp ngôn ngữ theo chủ nhân chỉ định. Mỗi cặp chạy CẢ HAI chiều: T là bên nào cũng
# được, bên kia làm C. `vi-ko` là cặp không có tiếng Anh — nếu tiếng Anh vẫn rò vào
# câu trả lời ở đây thì nghi phạm là `TASK_FRAME` chứ không phải lịch sử.
PAIRS: tuple[tuple[str, str], ...] = (("vi", "en"), ("id", "en"), ("ko", "en"), ("vi", "ko"))

DEPTHS: tuple[int, ...] = (0, 1, 2, 4, 8)
LABEL_POSITIONS: tuple[str, ...] = ("none", "system", "user")
INJECT_SOURCES: tuple[str, ...] = ("history", "memory")
HISTORY_KINDS: tuple[str, ...] = ("clean", "contaminated")


def directions(pairs: Sequence[tuple[str, str]] = PAIRS) -> list[tuple[str, str]]:
    """Mỗi cặp -> hai hướng (T, C)."""
    out = []
    for a, b in pairs:
        out.append((a, b))
        out.append((b, a))
    return out


@dataclass(frozen=True)
class Cell:
    label_condition: str          # F1
    asr_backend: str | None       # None khi oracle
    model: str                    # F2
    target_lang: str              # F3 (T)
    confuse_lang: str             # F3 (C)
    depth: int                    # F4
    label_position: str           # F5
    inject_source: str | None     # F6 — None khi depth = 0
    history_kind: str | None      # None khi depth = 0

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def name(self) -> str:
        parts = [
            self.label_condition if self.label_condition == "oracle" else f"asr:{self.asr_backend}",
            self.model,
            f"{self.target_lang}<-{self.confuse_lang}",
            f"d{self.depth}",
            f"lbl:{self.label_position}",
        ]
        if self.depth:
            parts.append(f"{self.inject_source}/{self.history_kind}")
        return "|".join(parts)


@dataclass
class Spec:
    """Một lát cắt của lưới. Pilot và lượt chạy đầy đủ dùng chung lớp này."""

    label_conditions: Sequence[str] = ("oracle",)
    asr_backends: Sequence[str] = ()
    models: Sequence[str] = ("gemini-2.5-flash",)
    pairs: Sequence[tuple[str, str]] = PAIRS
    both_directions: bool = True
    depths: Sequence[int] = DEPTHS
    label_positions: Sequence[str] = LABEL_POSITIONS
    inject_sources: Sequence[str] = INJECT_SOURCES
    history_kinds: Sequence[str] = HISTORY_KINDS
    n_probe: int = 50

    def as_dict(self) -> dict:
        data = asdict(self)
        data["pairs"] = [list(p) for p in self.pairs]
        return data


def cells(spec: Spec) -> list[Cell]:
    """Nở `Spec` thành danh sách ô. Không nhân đôi ô `depth = 0`."""
    dirs = directions(spec.pairs) if spec.both_directions else list(spec.pairs)
    out: list[Cell] = []
    for label_condition in spec.label_conditions:
        backends = spec.asr_backends if label_condition == "asr" else (None,)
        if label_condition == "asr" and not backends:
            raise ValueError("F1 = asr thì phải nêu ít nhất một backend STT")
        for backend, model, (target, confuse), position in itertools.product(
            backends, spec.models, dirs, spec.label_positions
        ):
            for depth in spec.depths:
                if depth == 0:
                    out.append(Cell(label_condition, backend, model, target, confuse,
                                    0, position, None, None))
                    continue
                for source, kind in itertools.product(spec.inject_sources, spec.history_kinds):
                    out.append(Cell(label_condition, backend, model, target, confuse,
                                    depth, position, source, kind))
    return out


@dataclass(frozen=True)
class Trial:
    cell: Cell
    probe_id: str

    @property
    def key(self) -> str:
        return trial_key(self.cell, self.probe_id)


def trial_key(cell: Cell, probe_id: str) -> str:
    """Khoá tất định cho một lượt. Đổi thiết kế -> đổi khoá -> không lẫn với kết quả cũ.

    Băm cả `Cell` chứ không chỉ ghép tên: nếu ai thêm một trường vào `Cell` mà quên
    đưa vào tên, khoá vẫn đổi và lượt cũ không bị nhận nhầm là đã chạy.
    """
    payload = json.dumps({"cell": cell.as_dict(), "probe": probe_id},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def trials(spec: Spec, probe_ids: Sequence[str]) -> Iterator[Trial]:
    """Sinh lượt theo thứ tự **CÂU trước, Ô sau** — cố ý, và đây là chỗ dễ làm sai.

    Thứ tự tự nhiên là lặp ô ở ngoài, câu ở trong. Nhưng khi đó, dừng giữa chừng sẽ
    để lại một bảng **lệch**: những ô chạy trước có đủ 50 câu, những ô sau có 0. Không
    so ô với ô được nữa, và cả mẻ chạy dở thành vô dụng.

    Đảo lại thì mọi điểm dừng đều cho một thiết kế cân bằng: dừng sau câu thứ k là có
    đúng k câu cho MỌI ô. Với nhánh local chạy hàng chục giờ trên CPU, đó là khác biệt
    giữa "dừng sớm vẫn công bố được với n nhỏ hơn" và "dừng sớm là mất trắng".

    Resume không bị ảnh hưởng: khoá là `trial_key`, không phải thứ tự.
    """
    all_cells = cells(spec)
    for probe_id in probe_ids[: spec.n_probe]:
        for cell in all_cells:
            yield Trial(cell, probe_id)


def count(spec: Spec) -> dict:
    """Đếm ô và lượt gọi API — để ước chi phí TRƯỚC khi chạy."""
    all_cells = cells(spec)
    per_model: dict[str, int] = {}
    for cell in all_cells:
        per_model[cell.model] = per_model.get(cell.model, 0) + spec.n_probe
    return {
        "cells": len(all_cells),
        "trials": len(all_cells) * spec.n_probe,
        "trials_per_model": per_model,
    }


def history_for(
    cell: Cell,
    *,
    history_user_ids: Sequence[str],
    history_assistant_ids: Sequence[str],
    text_of,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Chọn câu cho lịch sử/ký ức của một ô. `text_of(flores_id, lang) -> str`.

    Điểm mấu chốt của thiết kế nằm ở hai dòng cuối: nội dung là **cùng những câu
    FLoRes** ở điều kiện sạch và điều kiện nhiễm; thứ duy nhất đổi là NGÔN NGỮ của
    lượt trợ lý (T hay C). Nên khác biệt đo được không thể đổ cho nội dung.

    Lượt người dùng trong lịch sử LUÔN bằng T — vì khuôn nhiễm cần tái lập là
    "người hỏi bằng T → trợ lý đáp bằng C" (docs/ADR-008: EN hỏi → VI đáp).
    """
    if cell.depth == 0:
        return [], []
    uids = list(history_user_ids)[: cell.depth]
    aids = list(history_assistant_ids)[: cell.depth]
    if len(uids) < cell.depth or len(aids) < cell.depth:
        raise ValueError(f"kho lịch sử không đủ cho độ sâu {cell.depth}")

    assistant_lang = cell.target_lang if cell.history_kind == "clean" else cell.confuse_lang
    history_user = [(sid, text_of(sid, cell.target_lang)) for sid in uids]
    history_assistant = [(sid, text_of(sid, assistant_lang)) for sid in aids]
    return history_user, history_assistant
