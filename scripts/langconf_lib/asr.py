"""Nhãn ngôn ngữ do ASR đoán — F1, đóng góp riêng của bài này.

Import `desktop/handlers/*` **như thư viện, không sửa một dòng nào**. Baseline v3
đang đóng băng; mọi thứ cần khác đi đều làm bằng tham số của `setup()` hoặc bằng lớp
con khai báo tại đây.

## Một phát hiện phải nói ngay: baseline v3 chỉ biết hai thứ tiếng

`handlers/stt_gemini.py` ghim `RESPONSE_SCHEMA` với `enum: ["vi", "en"]`, và
`DuckSTTHandler.setup()` mặc định `languages_allowed=("vi", "en")` rồi
`_clean_language()` kẹp mọi kết quả về đúng hai mã đó. Nghĩa là **backend đang chạy
thật không thể trả nhãn `id` hay `ko`** — đưa nó câu tiếng Hàn thì nó buộc phải nói
"vi" hoặc "en".

Đó không phải lỗi của họ (vịt chỉ nói hai thứ tiếng), nhưng nó buộc bộ thí nghiệm
phải có hai hạng backend, và **không được trộn hai hạng vào một bảng**:

    DESKTOP_V3   y nguyên baseline, chỉ vi/en.
                 Dùng cho cặp vi-en và cho 31 WAV giọng thật.
                 Trên id/ko nó sai nhãn 100 % do thiết kế -> KHÔNG chạy, chạy là
                 báo cáo một con số vô nghĩa.
    STUDY_4L     cùng hai engine ấy, mở ra bốn ngôn ngữ (lớp con + tham số).
                 Dùng cho lưới FLEURS bốn ngôn ngữ.

`STUDY_4L` không phải baseline; nó là đối tượng nghiên cứu. Bảng nào dùng nó phải
ghi rõ, nếu không người đọc sẽ tưởng đó là số của hệ thống đang chạy.

## Hạn giờ Gemini: 60 s ở đây, không phải 4 s như sản phẩm

`GeminiAudioSTT` mặc định `timeout_s = 4.0`. Con số đó là quyết định về **độ trễ sản
phẩm** (`docs/ADR-004`, `ADR-009`): quá 4 s thì người dùng ngồi đợi trong im lặng, nên
thà lùi về Whisper. Nó KHÔNG phải quyết định về chất lượng chép.

Ở bộ thí nghiệm này ta đo *nhãn ngôn ngữ*, không đo độ trễ, và câu FLEURS dài 8–13 s
chứ không phải một mệnh lệnh 2 s. Giữ 4 s thì Gemini quá hạn và `transcribe_audio()`
**âm thầm lùi về Whisper trong khi dòng kết quả vẫn ghi `backend = "gemini-audio"`** —
tức là bảng so hai backend lẫn lượt của backend kia mà không ai thấy. Đo được: 3/193
lượt dính đúng chuyện đó trước khi sửa.

Nên: hạn 60 s, **và** cờ `asr_fell_back` ghi vào mọi dòng để ca còn sót vẫn nhìn thấy
được. Không sửa mặc định trong `desktop/` — sản phẩm vẫn phải giữ 4 s.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

DESKTOP_DIR = Path(__file__).resolve().parents[3] / "desktop"

FOUR = ("vi", "en", "id", "ko")


def _ensure_desktop_on_path() -> None:
    """`desktop/` phải nằm trên sys.path vì các module ở đó import phẳng (`from audio_wav ...`)."""
    path = str(DESKTOP_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


def build_language_detector(languages: Sequence[str] = FOUR):
    """Bản mở rộng của `pipeline.build_language_detector`, viết lại tại đây.

    Bản ở `desktop/pipeline.py` ghim cứng `by_code = {"vi": ..., "en": ...}` nên gọi
    nó với `id`/`ko` là KeyError. Sửa nó là sửa baseline -> không được. Viết bản riêng
    ở đây, **giữ nguyên hành vi** (ngưỡng 4 ký tự, trả None khi không chắc) và chỉ
    thêm ngôn ngữ.
    """
    from lingua import Language, LanguageDetectorBuilder

    by_code = {
        "vi": Language.VIETNAMESE,
        "en": Language.ENGLISH,
        "id": Language.INDONESIAN,
        "ko": Language.KOREAN,
    }
    iso_to_code = {v.name: k for k, v in by_code.items()}
    detector = (
        LanguageDetectorBuilder.from_languages(*(by_code[c] for c in languages))
        .with_preloaded_language_models()
        .build()
    )

    def detect(text: str, min_confidence: float = 0.0) -> str | None:
        if len(text.strip()) < 4:
            return None
        if min_confidence <= 0.0:
            result = detector.detect_language_of(text)
            return iso_to_code.get(result.name) if result is not None else None
        values = detector.compute_language_confidence_values(text)
        if values and values[0].value >= min_confidence:
            return iso_to_code.get(values[0].language.name)
        return None

    return detect


def build_gemini_stt(api_key: str, languages: Sequence[str] = FOUR,
                     model: str = "gemini-2.5-flash", timeout_s: float = 60.0):
    """`GeminiAudioSTT` mở ra nhiều ngôn ngữ bằng LỚP CON, không đụng file gốc.

    Chỉ ghi đè hai thứ: schema JSON (enum ngôn ngữ) và câu chỉ dẫn liệt kê ngôn ngữ.
    Giữ nguyên `temperature=0`, `thinking_budget=0`, hạn giờ, và cách bóc JSON —
    tức là vẫn cùng một engine, chỉ khác cái rọ ngôn ngữ.
    """
    _ensure_desktop_on_path()
    from handlers.stt_gemini import GeminiAudioSTT

    names = {"vi": "Vietnamese", "en": "English", "id": "Indonesian", "ko": "Korean"}
    listed = ", ".join(f'"{c}" ({names[c]})' for c in languages)

    class MultilingualGeminiSTT(GeminiAudioSTT):
        def _config(self, force_language: str | None = None):
            types = self._types
            instruction = (
                "Transcribe the speech in the audio exactly.\n\n"
                f"The speaker uses one of these languages: {listed}. Rules:\n"
                "- Transcribe verbatim, with full diacritics. Do not translate, "
                "do not summarise, do not add any word.\n"
                "- If you cannot make out any word, return an empty transcript.\n"
                "- lang: the language code of the speech.\n\n"
                "Return JSON matching the schema, with no explanation."
            )
            if force_language:
                instruction += (
                    f'\n\nThe speaker is definitely using {names[force_language]}. '
                    f'Always return lang="{force_language}".'
                )
            return types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "lang": {"type": "string", "enum": list(languages)},
                        "transcript": {"type": "string"},
                    },
                    "required": ["lang", "transcript"],
                },
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

    return MultilingualGeminiSTT(
        api_key=api_key, model=model, timeout_s=timeout_s,
        languages_allowed=tuple(languages),
    )


@dataclass
class Heard:
    """Kết quả một lượt chép. `lang` là NHÃN mà hệ thống tin, có thể sai."""

    text: str
    lang: str
    lang_p: float
    model: str
    low_confidence: bool
    backend: str
    fell_back: bool = False     # xin gemini-audio nhưng THỰC TẾ Whisper chép

    def as_dict(self) -> dict:
        return {
            "asr_text": self.text,
            "asr_lang": self.lang,
            "asr_lang_p": self.lang_p,
            "asr_model": self.model,
            "asr_low_confidence": self.low_confidence,
            # KHÔNG đặt tên `asr_backend`: `Cell.asr_backend` (thiết kế, ví dụ
            # "gemini-audio@v3") và trường này (quan sát, "gemini-audio") gặp nhau
            # trong cùng một dòng jsonl, và cái sau đè cái trước. Ở nhánh FLEURS hai
            # chuỗi trùng nhau nên không ai thấy; ở nhánh realvoice chúng khác nhau
            # đúng hậu tố @v3 và trường thiết kế biến mất khỏi dòng ghi.
            "asr_backend_used": self.backend,
            # PHẢI ghi lại: `transcribe_audio` lùi âm thầm về Whisper khi Gemini quá
            # hạn, và dòng kết quả vẫn ghi `backend = "gemini-audio"`. Không có cờ này
            # thì bảng so hai backend lẫn vài lượt của backend kia mà không ai thấy.
            "asr_fell_back": self.fell_back,
        }


class ASRBank:
    """Dựng cả hai backend một lần, chép WAV theo yêu cầu.

    `languages=("vi","en")` -> hạng DESKTOP_V3 (y baseline).
    `languages=FOUR`        -> hạng STUDY_4L.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        languages: Sequence[str] = FOUR,
        whisper_model: str | None = None,
        vi_model_path: str | None = None,
        gemini_model: str = "gemini-2.5-flash",
        gemini_timeout_s: float = 60.0,
    ) -> None:
        _ensure_desktop_on_path()
        from config import Config
        from handlers.stt_whisper import DuckSTTHandler

        cfg = Config.load()
        self.languages = tuple(languages)
        self.tier = "DESKTOP_V3" if self.languages == ("vi", "en") else "STUDY_4L"

        if self.tier == "DESKTOP_V3":
            from handlers.stt_gemini import GeminiAudioSTT

            gemini = (GeminiAudioSTT(api_key=api_key, model=gemini_model,
                                     timeout_s=gemini_timeout_s) if api_key else None)
            detector = None
            _ensure_desktop_on_path()
            from pipeline import build_language_detector as baseline_detector

            detector = baseline_detector()
        else:
            gemini = (build_gemini_stt(api_key, self.languages, gemini_model,
                                       timeout_s=gemini_timeout_s) if api_key else None)
            detector = build_language_detector(self.languages)

        stt = DuckSTTHandler.__new__(DuckSTTHandler)     # bỏ vòng đời thread, y như scripts/rescore_utts.py
        stt.setup(
            model_name=whisper_model or cfg.stt_model,
            device="cpu",
            compute_type="int8",
            language=None,
            language_mode="auto",
            languages_allowed=self.languages,
            tracker=None,
            detect_language=detector,
            vi_model_path=vi_model_path if vi_model_path is not None else cfg.stt_model_vi,
            backend="phowhisper-reread",
            gemini_stt=gemini,
            utt_dir=None,                                # chấm lại thì đừng ghi thêm WAV
            # temperature=0: tắt dải fallback ngẫu nhiên của faster-whisper (docs/ADR-007).
            # Bắt buộc ở đây — một câu chép ra hai kiểu là hai nhãn ngôn ngữ khác nhau,
            # và cả bảng F1 sẽ không lặp lại được.
            gen_kwargs={"temperature": 0.0},
        )
        self._stt = stt
        self.has_gemini = gemini is not None

    def transcribe(self, wav_path: str | Path, backend: str) -> Heard:
        """Chép một file WAV. `backend` = "gemini-audio" | "phowhisper-reread" | "base"."""
        _ensure_desktop_on_path()
        import wave

        from audio_wav import SAMPLE_RATE, read_wav

        # `read_wav` của desktop giả định 16 kHz int16 mono và không kiểm lại. WAV của
        # FLEURS đúng như thế, nhưng kiểm ở đây vẫn rẻ: sai tần số thì audio bị đọc
        # nhanh/chậm và cả bảng ASR lệch mà không có dấu hiệu nào.
        with wave.open(str(wav_path), "rb") as handle:
            rate, channels, width = handle.getframerate(), handle.getnchannels(), handle.getsampwidth()
        if (rate, channels, width) != (SAMPLE_RATE, 1, 2):
            raise SystemExit(
                f"{wav_path}: cần {SAMPLE_RATE} Hz mono 16-bit, thấy {rate} Hz "
                f"{channels} kênh {width * 8}-bit"
            )
        audio = read_wav(str(wav_path))
        # Xoá trí nhớ ngôn ngữ giữa các lượt: `_clean_language()` lấy `last_language`
        # làm nước cuối, nên chạy 200 file liền nhau sẽ sinh hiệu ứng thứ tự — file
        # thứ 8 được lợi vì 7 file trước cùng thứ tiếng. Ở đây mỗi lượt phải độc lập.
        self._stt.last_language = None
        heard = self._stt.transcribe_audio(audio, backend=backend)
        return Heard(
            text=heard["text"],
            lang=heard["language"],
            lang_p=float(heard.get("language_p") or 0.0),
            model=str(heard.get("model") or ""),
            low_confidence=bool(heard.get("low_confidence")),
            backend=backend,
            fell_back=bool(heard.get("stt_fallback")),
        )
