"""FLEURS: chọn câu SONG SONG và lấy audio cho đúng những câu ấy.

Vì sao dùng FLEURS mà không phải bộ nào khác: transcript của nó gắn với **id câu
FLoRes**, mà FLoRes là bộ dịch song song — cùng một id ở `vi_vn`, `en_us`, `id_id`,
`ko_kr` là cùng một câu, chỉ khác thứ tiếng. Nhờ vậy nội dung ngữ nghĩa được giữ CỐ
ĐỊNH khi ta đổi ngôn ngữ, và mọi chênh lệch đo được không thể đổ cho "câu tiếng Hàn
khó hơn câu tiếng Việt".

Bốn ngôn ngữ và lý do (chủ nhân chọn):
    vi–en, id–en   cùng hệ chữ Latin
    ko–en          khác hệ chữ  -> kiểm "nhiễu mạnh hơn khi chung hệ chữ"
    id             gần vi về mức tài nguyên nhưng KHÔNG dấu thanh
                   -> tách "dấu phụ" khỏi "mức tài nguyên"
    vi–ko          không có tiếng Anh -> kiểm en có phải "hố hút" không

Chỉ tải **metadata TSV** (vài trăm KB) là đủ cho phần văn bản. Audio (`fetch_audio`)
chỉ cần cho điều kiện F1 = ASR, và chỉ tải đúng những file đã chọn.

Không sửa gì trong `desktop/`. Dữ liệu nằm ở `study/langconf/data/`.
"""

from __future__ import annotations

import csv
import io
import random
import tarfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

HF_BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data"

# Mã FLEURS <-> mã ISO hai chữ dùng khắp phần còn lại của bộ thí nghiệm.
FLEURS_CODE = {"vi": "vi_vn", "en": "en_us", "id": "id_id", "ko": "ko_kr"}
LANGUAGES = tuple(FLEURS_CODE)

# Cột của TSV FLEURS: id, file_name, raw_transcription, transcription, char_tokens,
# num_samples, gender. Ta dùng `raw_transcription` — có hoa/thường và dấu câu, tức là
# gần với chữ mà một trợ lý thật nhìn thấy nhất. `transcription` đã bị chuẩn hoá về
# thường và bỏ dấu câu, dùng nó thì fastText mất tín hiệu và LPR lệch.
COL_ID, COL_FILE, COL_RAW = 0, 1, 2


@dataclass(frozen=True)
class Sentence:
    flores_id: str
    lang: str
    text: str
    wav_name: str      # tên file trong tar audio của FLEURS


class FleursText:
    """Bảng câu song song. Không đụng tới audio."""

    def __init__(self, meta_dir: str | Path, splits: tuple[str, ...] = ("dev",)) -> None:
        self.meta_dir = Path(meta_dir)
        self.splits = splits
        # {lang: {flores_id: Sentence}} — mỗi id giữ BẢN GHI ĐẦU TIÊN gặp được.
        # FLEURS có nhiều người đọc cùng một câu; lấy bản đầu theo thứ tự file cho
        # tất định. Ai muốn đổi người đọc thì đổi ở đây, đừng đổi ở chỗ dùng.
        self.by_lang: dict[str, dict[str, Sentence]] = {}
        self.split_of: dict[tuple[str, str], str] = {}
        for lang in LANGUAGES:
            table: dict[str, Sentence] = {}
            for split in splits:
                path = self.meta_dir / f"{FLEURS_CODE[lang]}.{split}.tsv"
                with open(path, encoding="utf-8", newline="") as handle:
                    for row in csv.reader(handle, delimiter="\t"):
                        if len(row) <= COL_RAW:
                            continue
                        sid = row[COL_ID]
                        if sid in table:
                            continue
                        table[sid] = Sentence(sid, lang, row[COL_RAW].strip(), row[COL_FILE])
                        self.split_of[(lang, sid)] = split
            self.by_lang[lang] = table

    def parallel_ids(self) -> list[str]:
        """id có mặt ở CẢ BỐN ngôn ngữ, sắp theo số để tất định."""
        common = set.intersection(*(set(t) for t in self.by_lang.values()))
        return sorted(common, key=lambda s: (len(s), s))

    def counts(self) -> dict:
        return {
            "splits": list(self.splits),
            "per_language": {l: len(t) for l, t in self.by_lang.items()},
            "parallel": len(self.parallel_ids()),
        }

    def text(self, flores_id: str, lang: str) -> str:
        return self.by_lang[lang][flores_id].text

    def sentence(self, flores_id: str, lang: str) -> Sentence:
        return self.by_lang[lang][flores_id]

    def pool(self, ids: list[str]) -> dict[str, dict[str, str]]:
        """{flores_id: {lang: text}} — dạng mà `prompts.audit_messages` cần."""
        return {sid: {l: self.text(sid, l) for l in LANGUAGES} for sid in ids}


@dataclass
class Selection:
    """Chia id song song thành kho thăm dò và kho lịch sử. Rời nhau tuyệt đối."""

    probe_ids: list[str]
    history_user_ids: list[str]        # id cho lượt NGƯỜI DÙNG trong lịch sử
    history_assistant_ids: list[str]   # id cho lượt TRỢ LÝ / mục ký ức
    seed: int
    available: int

    @property
    def history_ids(self) -> set[str]:
        return set(self.history_user_ids) | set(self.history_assistant_ids)

    def as_dict(self) -> dict:
        return {
            "seed": self.seed,
            "available_parallel_ids": self.available,
            "n_probe": len(self.probe_ids),
            "probe_ids": self.probe_ids,
            "history_user_ids": self.history_user_ids,
            "history_assistant_ids": self.history_assistant_ids,
        }


def select(
    table: FleursText,
    *,
    n_probe: int = 50,
    max_depth: int = 8,
    seed: int = 20260926,
) -> Selection:
    """Chọn kho thăm dò + kho lịch sử.

    Seed 20260926 chọn có lý do, không phải bốc bừa: quét 40 seed liên tiếp thì đây là
    seed đầu tiên mà **cả kho lịch sử lẫn kho thăm dò đều không có câu nào tự nhắc tới
    một ngôn ngữ** (`prompts.flag_language_mentions`). Seed 20260907 dựng bộ này lần
    đầu để một câu tiếng Anh nói về "English saddles" rơi vào kho lịch sử — một câu như
    thế nằm trong lịch sử là gợi ý ngôn ngữ không nằm trong thiết kế. Đổi seed rẻ hơn
    nhiều so với việc phải bào chữa cho nó ở phần Hạn chế.

    Chủ nhân đã dặn: **thiếu thì hạ số câu, không lấy câu khác nhau.** Nên nếu id song
    song không đủ, hàm này cắt bớt `n_probe` và ghi lại `available` để báo cáo, thay vì
    lén lấy câu không song song cho đủ số.
    """
    ids = table.parallel_ids()
    need_history = 2 * max_depth
    if len(ids) < need_history + 1:
        raise SystemExit(
            f"chỉ có {len(ids)} id song song, không đủ cho kho lịch sử sâu {max_depth}"
        )
    rng = random.Random(seed)
    shuffled = list(ids)
    rng.shuffle(shuffled)

    history_user_ids = shuffled[:max_depth]
    history_assistant_ids = shuffled[max_depth:need_history]
    rest = shuffled[need_history:]
    probe_ids = rest[: min(n_probe, len(rest))]

    return Selection(
        probe_ids=sorted(probe_ids, key=lambda s: (len(s), s)),
        history_user_ids=history_user_ids,
        history_assistant_ids=history_assistant_ids,
        seed=seed,
        available=len(ids),
    )


# ---------------------------------------------------------------------------
# Audio — chỉ cần cho F1 = ASR
# ---------------------------------------------------------------------------


def normalize_wav(path: str | Path) -> bool:
    """Ép WAV về **16 kHz mono PCM 16-bit** — đúng định dạng audio mic thật của pipeline.

    FLEURS phát hành WAV 16 kHz mono nhưng subtype **FLOAT** (`wFormatTag = 3`).
    `desktop/audio_wav.read_wav()` dùng module `wave` của stdlib, và module đó từ chối
    thẳng format 3 (`wave.Error: unknown format: 3`). Không sửa `read_wav` được —
    baseline v3 đóng băng — nên sửa DỮ LIỆU cho khớp công cụ.

    Đây cũng là cách duy nhất để so công bằng với 31 WAV giọng thật: hai bộ audio phải
    vào cùng một đường ống, cùng độ sâu bit, thì số WER/nhãn mới đặt cạnh nhau được.

    Trả True nếu có chuyển đổi, False nếu file đã đúng định dạng.
    """
    import numpy as np
    import soundfile as sf

    path = Path(path)
    info = sf.info(str(path))
    if info.subtype == "PCM_16" and info.samplerate == 16_000 and info.channels == 1:
        return False
    audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != 16_000:
        raise SystemExit(f"{path}: {rate} Hz, bộ này chỉ nhận 16 kHz (FLEURS vốn 16 kHz)")
    # Cắt biên trước khi nhân 32767: float32 có mẫu vượt ±1,0 thì int16 sẽ tràn và
    # quấn vòng, biến đỉnh sóng thành tiếng nổ — nghe thì rõ, nhưng WER thì chỉ thấy
    # transcript tự dưng tệ đi mà không hiểu vì sao.
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(str(path), (audio * 32767.0).astype(np.int16), 16_000, subtype="PCM_16")
    return True


def fetch_audio(
    table: FleursText,
    flores_ids: list[str],
    out_dir: str | Path,
    *,
    langs: tuple[str, ...] = LANGUAGES,
    split: str = "dev",
    progress=print,
) -> dict[str, Path]:
    """Rút đúng những WAV cần từ tar audio của FLEURS, bỏ phần còn lại.

    FLEURS đóng gói audio thành `data/<lang>/audio/<split>.tar.gz`, không cho tải lẻ
    từng file. Nên phải chảy qua cả tar — nhưng chỉ GHI ra đĩa những file trong danh
    sách. dev của bốn ngôn ngữ cộng lại khoảng 730 MB tải về, ~50 MB giữ lại.

    Trả {"<lang>/<flores_id>": đường dẫn WAV}. Có sẵn thì bỏ qua (chạy lại được).
    """
    out_dir = Path(out_dir)
    result: dict[str, Path] = {}
    for lang in langs:
        wanted = {}
        for sid in flores_ids:
            sentence = table.sentence(sid, lang)
            target = out_dir / lang / f"{sid}.wav"
            result[f"{lang}/{sid}"] = target
            if not target.exists():
                wanted[sentence.wav_name] = target
        if not wanted:
            progress(f"[audio] {lang}: đủ rồi, bỏ qua")
            continue

        url = f"{HF_BASE}/{FLEURS_CODE[lang]}/audio/{split}.tar.gz"
        progress(f"[audio] {lang}: cần {len(wanted)} file, mở {url}")
        (out_dir / lang).mkdir(parents=True, exist_ok=True)
        with urlopen(url) as response:
            with tarfile.open(fileobj=response, mode="r|gz") as tar:
                for member in tar:
                    name = Path(member.name).name
                    target = wanted.pop(name, None)
                    if target is None:
                        continue
                    source = tar.extractfile(member)
                    if source is None:
                        continue
                    target.write_bytes(source.read())
                    normalize_wav(target)   # FLEURS ra float32; pipeline đòi PCM 16-bit
                    if not wanted:
                        break            # đủ rồi thì bỏ nốt phần đuôi của tar
        if wanted:
            raise SystemExit(
                f"{lang}: không tìm thấy {len(wanted)} file trong {split}.tar.gz: "
                f"{sorted(wanted)[:5]}"
            )
        progress(f"[audio] {lang}: xong")
    return result


def download_metadata(meta_dir: str | Path, splits: tuple[str, ...] = ("dev", "test")) -> None:
    """Tải TSV cho bốn ngôn ngữ. Vài trăm KB, không có audio."""
    meta_dir = Path(meta_dir)
    meta_dir.mkdir(parents=True, exist_ok=True)
    for lang in LANGUAGES:
        for split in splits:
            path = meta_dir / f"{FLEURS_CODE[lang]}.{split}.tsv"
            if path.exists():
                continue
            with urlopen(f"{HF_BASE}/{FLEURS_CODE[lang]}/{split}.tsv") as response:
                path.write_bytes(response.read())
