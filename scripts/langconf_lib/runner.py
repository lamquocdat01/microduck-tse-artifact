"""Chạy lượt và GHI RA jsonl. Không chấm điểm ở đây.

Chủ nhân dặn ba việc, cả ba nằm ở file này:

1. **Một dòng một lượt, đủ để chấm lại offline mà không gọi API lần nữa.** Nên mỗi
   dòng chép NGUYÊN VĂN prompt đã gửi (`messages`) và nguyên văn câu trả lời. File
   to hơn, nhưng đổi lại: sửa bộ chấm rồi chấm lại không tốn một đồng nào.
2. **Resume nếu đứt.** Khoá là `trial_key` (băm cả `Cell` lẫn `probe_id`). Khởi động
   thì đọc jsonl có sẵn, bỏ qua mọi khoá đã xong.
3. **Kiểm nhiễm mỗi lượt.** `audit_messages()` chạy TRƯỚC khi gửi và ném lỗi. Một
   prompt bẩn lọt qua là cả bảng vô nghĩa, nên thà dừng.

Chép ASR được lưu bộ nhớ đệm riêng (`asr_cache.jsonl`): một câu thăm dò xuất hiện ở
hàng chục ô, chép lại mỗi lần vừa tốn tiền vừa làm nhãn dao động.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import design, prompts
from .design import Cell, Spec, Trial
from .fleurs import FleursText, Selection


@dataclass
class ProbeItem:
    """Một câu thăm dò ở một ngôn ngữ: chữ chuẩn + (nếu có) file audio."""

    probe_id: str
    lang: str
    gold_text: str
    wav: Path | None = None
    source: str = "fleurs"


class ASRCache:
    """{(wav, backend, tier): Heard} lưu bền, để chép mỗi file đúng một lần."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, dict] = {}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        self.entries[row["key"]] = row

    @staticmethod
    def key(wav: Path, backend: str, tier: str) -> str:
        """Khoá phải chứa **cả thư mục**, không chỉ tên file.

        FLEURS đặt tên WAV theo id câu FLoRes, nên `data/audio/en/1518.wav` và
        `data/audio/vi/1518.wav` **trùng tên**. Bản đầu khoá theo `Path(wav).name` và
        hậu quả im lặng: ngôn ngữ nào được chép trước (en, theo thứ tự chữ cái) thì ba
        ngôn ngữ còn lại nhận đúng bản chép tiếng Anh đó từ bộ đệm — toàn bộ nhánh F1
        sẽ là số rác mà không có một dòng lỗi nào. Bắt được vì bộ đệm dừng ở 100 mục
        thay vì 400.
        """
        path = Path(wav).resolve()
        return f"{tier}|{backend}|{path.parent.name}/{path.name}"

    def get(self, wav: Path, backend: str, tier: str) -> dict | None:
        return self.entries.get(self.key(wav, backend, tier))

    def put(self, wav: Path, backend: str, tier: str, heard: dict) -> dict:
        row = {"key": self.key(wav, backend, tier), "wav": str(wav),
               "backend": backend, "tier": tier, **heard}
        self.entries[row["key"]] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


def load_done(path: str | Path) -> set[str]:
    """Khoá của những lượt đã ghi. Dòng hỏng bị bỏ qua chứ không làm đổ cả mẻ."""
    path = Path(path)
    done: set[str] = set()
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["trial_key"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


class Runner:
    def __init__(
        self,
        *,
        table: FleursText,
        selection: Selection,
        backends: dict[str, object],      # {tên model: Backend}
        out_path: str | Path,
        asr_bank_for: Callable[[str], object] | None = None,   # tier -> ASRBank
        asr_cache_path: str | Path | None = None,
        probe_items: dict[tuple[str, str], ProbeItem] | None = None,
        progress: Callable[[str], None] = print,
    ) -> None:
        self.table = table
        self.selection = selection
        self.backends = backends
        self.out_path = Path(out_path)
        self.asr_bank_for = asr_bank_for
        self.asr_cache = ASRCache(asr_cache_path or self.out_path.with_name("asr_cache.jsonl"))
        self.probe_items = probe_items or {}
        self.progress = progress
        self.allowed_history_ids = selection.history_ids
        self._frozen_asr = False        # bật sau prefetch_asr(); chặn chép lẻ khi đa luồng

        prompts.check_scaffolding_is_neutral()

        # Kho chuỗi được phép: mọi câu lịch sử ở mọi ngôn ngữ. Câu thăm dò KHÔNG nằm
        # trong kho — nó được thêm riêng cho từng lượt, nên một câu thăm dò lạc vào
        # lịch sử sẽ bị `audit_messages` bắt.
        self.history_texts = {
            table.text(sid, lang)
            for sid in selection.history_ids
            for lang in table.by_lang
        }

    # -- ASR -----------------------------------------------------------------

    def _heard(self, item: ProbeItem, backend: str, tier: str) -> dict:
        if item.wav is None:
            raise SystemExit(f"F1 = asr nhưng không có audio cho {item.lang}/{item.probe_id}")
        cached = self.asr_cache.get(item.wav, backend, tier)
        if cached is not None:
            return cached
        if self._frozen_asr:
            # Chạy nhiều luồng: model Whisper không an toàn đa luồng và `ASRCache.put`
            # ghi nối vào file. Nên bộ nhớ đệm phải ĐẦY trước khi mở luồng.
            raise SystemExit(
                f"thiếu bản chép ASR cho {item.lang}/{item.probe_id} ({backend}/{tier}) — "
                f"chạy prefetch_asr() trước khi chạy nhiều luồng"
            )
        bank = self.asr_bank_for(tier)
        heard = bank.transcribe(item.wav, backend)
        return self.asr_cache.put(item.wav, backend, tier, heard.as_dict())

    def prefetch_asr(self, spec: Spec) -> dict:
        """Chép TRƯỚC mọi WAV mà `spec` cần, tuần tự, rồi đóng băng bộ nhớ đệm.

        Tách hẳn khỏi lúc gọi LLM vì hai lý do: model Whisper không an toàn đa luồng,
        và nhãn ASR phải CỐ ĐỊNH trong suốt mẻ chạy — một câu xuất hiện ở hàng chục ô,
        chép lại mỗi lần thì cùng một audio có thể ra hai nhãn và F1 mất ý nghĩa.
        """
        wanted: set[tuple[str, str, str, str]] = set()
        for cell in design.cells(spec):
            if cell.label_condition != "asr":
                continue
            tier = "DESKTOP_V3" if (cell.asr_backend or "").endswith("@v3") else "STUDY_4L"
            backend = (cell.asr_backend or "").removesuffix("@v3")
            for probe_id in self.selection.probe_ids[: spec.n_probe]:
                wanted.add((cell.target_lang, probe_id, backend, tier))

        self._frozen_asr = False
        done = 0
        for index, (lang, probe_id, backend, tier) in enumerate(sorted(wanted), start=1):
            item = self.probe_items.get((lang, probe_id))
            if item is None:
                raise SystemExit(f"F1 = asr nhưng chưa khai audio cho {lang}/{probe_id}")
            before = len(self.asr_cache.entries)
            self._heard(item, backend, tier)
            done += len(self.asr_cache.entries) > before
            if index % 25 == 0 or index == len(wanted):
                self.progress(f"  [asr] {index}/{len(wanted)} (chép mới {done})")

        # Chốt kiểm: mỗi tổ hợp cần chép phải ra một khoá RIÊNG trong bộ đệm. Bộ đệm
        # ít mục hơn số cần là dấu hiệu khoá bị đụng nhau — đúng lỗi đã dính một lần
        # (tên file FLEURS trùng nhau giữa bốn ngôn ngữ). Thà dừng còn hơn chạy 61 200
        # lượt trên nhãn của sai ngôn ngữ.
        keys = set()
        for lang, probe_id, backend, tier in wanted:
            item = self.probe_items[(lang, probe_id)]
            keys.add(ASRCache.key(item.wav, backend, tier))
        if len(keys) != len(wanted):
            raise SystemExit(
                f"khoá bộ đệm ASR đụng nhau: {len(wanted)} tổ hợp cần chép nhưng chỉ "
                f"sinh ra {len(keys)} khoá. Bản chép sẽ bị dùng lẫn giữa các ngôn ngữ."
            )
        missing = keys - set(self.asr_cache.entries)
        if missing:
            raise SystemExit(f"bộ đệm ASR thiếu {len(missing)} mục sau khi chép")

        self._frozen_asr = True
        return {"needed": len(wanted), "transcribed": done, "cached": len(keys)}

    # -- một lượt ------------------------------------------------------------

    def build(self, trial: Trial) -> tuple[prompts.BuiltPrompt, dict]:
        """Dựng prompt + phần siêu dữ liệu của dòng jsonl. Chưa gọi model."""
        cell = trial.cell
        item = self.probe_items.get((cell.target_lang, trial.probe_id))
        if item is None:
            item = ProbeItem(trial.probe_id, cell.target_lang,
                             self.table.text(trial.probe_id, cell.target_lang))

        meta: dict = {"probe_source": item.source, "gold_text": item.gold_text}

        if cell.label_condition == "oracle":
            probe_text = item.gold_text
            label_lang = cell.target_lang
        else:
            tier = "DESKTOP_V3" if cell.asr_backend and cell.asr_backend.endswith("@v3") else "STUDY_4L"
            backend = (cell.asr_backend or "").removesuffix("@v3")
            heard = self._heard(item, backend, tier)
            meta.update({k: v for k, v in heard.items() if k not in ("key", "wav")})
            meta["asr_tier"] = tier
            # Chữ ở lượt người dùng cũng là bản chép của ASR, không phải chữ chuẩn:
            # lỗi cộng dồn hai tầng nằm ở ĐÂY. Chép hỏng thì cả nội dung lẫn nhãn
            # đều lệch, và đó chính là thứ bản text-only không đo được.
            probe_text = heard["asr_text"]
            label_lang = heard["asr_lang"]

        if cell.label_position == "none":
            label_lang = None

        history_user, history_assistant = design.history_for(
            cell,
            history_user_ids=self.selection.history_user_ids,
            history_assistant_ids=self.selection.history_assistant_ids,
            text_of=self.table.text,
        )
        built = prompts.build_prompt(
            probe_id=trial.probe_id,
            probe_text=probe_text,
            target_lang=cell.target_lang,
            confuse_lang=cell.confuse_lang,
            label_lang=label_lang,
            label_position=cell.label_position,
            depth=cell.depth,
            history_kind=cell.history_kind,
            inject_source=cell.inject_source,
            history_user=history_user,
            history_assistant=history_assistant,
        )
        prompts.audit_messages(
            built,
            allowed_texts=self.history_texts | {probe_text},
            allowed_history_ids=self.allowed_history_ids,
        )
        return built, meta

    def run_one(self, trial: Trial) -> dict:
        built, meta = self.build(trial)
        backend = self.backends[trial.cell.model]
        reply = backend.chat(built.as_dicts())
        return {
            "trial_key": trial.key,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **trial.cell.as_dict(),
            "probe_id": trial.probe_id,
            "spoken_lang": trial.cell.target_lang,   # FLEURS: ngôn ngữ thật của audio
            "label_lang": built.label_lang,
            **meta,
            "messages": built.as_dicts(),            # nguyên văn, để chấm lại offline
            "reply_text": reply.text,
            "latency_ms": round(reply.latency_ms, 1),
            "model_error": reply.error,
            **reply.raw,
        }

    # -- cả mẻ ---------------------------------------------------------------

    def run(
        self,
        spec: Spec,
        *,
        limit: int | None = None,
        sleep_s: float = 0.0,
        workers: int = 1,
    ) -> dict:
        """Chạy phần còn thiếu của `spec`.

        `workers > 1` chỉ dành cho model API. **Ollama phải để 1**: CPU đã kín, mở
        luồng chỉ làm mỗi lượt chậm đi chứ không xong sớm hơn, và `latency_ms` ghi lại
        sẽ vô nghĩa. `prefetch_asr()` phải chạy xong trước nếu `spec` có F1 = asr.
        """
        done = load_done(self.out_path)
        todo = [t for t in design.trials(spec, self.selection.probe_ids) if t.key not in done]
        if limit is not None:
            todo = todo[:limit]

        self.progress(
            f"[chạy] {len(todo)} lượt còn lại (đã xong {len(done)}), {workers} luồng, "
            f"ghi vào {self.out_path}"
        )
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        state = {"errors": 0, "streak": 0, "index": 0}
        lock = threading.Lock()

        with open(self.out_path, "a", encoding="utf-8") as handle:

            def record(row: dict) -> None:
                with lock:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()            # đứt điện vẫn không mất dòng nào
                    state["index"] += 1
                    failed = bool(row.get("model_error"))
                    state["errors"] += failed
                    # Cầu chì. Lỗi cấu hình (key hỏng, endpoint sai) làm MỌI lượt hỏng
                    # mà vẫn ghi ra jsonl trơn tru — mẻ chạy "xong" với 100 % dòng rác.
                    # Đã dính một lần: key `.env` có chú thích cùng dòng, httpx nổ ascii
                    # ở header, 150/150 lượt hỏng trong 0,3 s.
                    state["streak"] = state["streak"] + 1 if failed else 0
                    index, errors = state["index"], state["errors"]
                if index % 25 == 0 or index == len(todo):
                    rate = index / max(1e-9, time.perf_counter() - started)
                    self.progress(
                        f"  {index}/{len(todo)}  {rate:.2f} lượt/s  "
                        f"còn ~{(len(todo) - index) / max(1e-9, rate) / 60:.0f} phút  "
                        f"lỗi {errors}"
                    )

            def work(trial: Trial) -> None:
                record(self.run_one(trial))
                if sleep_s:
                    time.sleep(sleep_s)

            if workers <= 1:
                for trial in todo:
                    work(trial)
                    if state["streak"] >= 10:
                        raise SystemExit("10 lượt hỏng liên tiếp, dừng.")
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(work, trial) for trial in todo]
                    for future in as_completed(futures):
                        future.result()       # lỗi lập trình phải nổ ra, không nuốt
                        if state["streak"] >= 10:
                            for pending in futures:
                                pending.cancel()
                            raise SystemExit("10 lượt hỏng liên tiếp, dừng.")

        return {"ran": len(todo), "errors": state["errors"],
                "seconds": round(time.perf_counter() - started, 1)}
