"""In danh sách giọng có sẵn cho hai TTS, để điền TTS_VOICE_VI / TTS_VOICE_EN trong .env."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import enable_utf8_console  # noqa: E402


def main() -> int:
    enable_utf8_console()

    print("VieNeu-TTS v3 Turbo (tiếng Việt) — đang nạp...")
    from vieneu import Vieneu

    tts = Vieneu(mode="v3turbo", device="cpu", precision="fp32")
    for label, voice_id in tts.list_preset_voices():
        mark = "  <- mặc định của gói" if voice_id == tts._default_voice else ""
        print(f"  {voice_id:14} {label}{mark}")

    print("\nKokoro (tiếng Anh) — a=Mỹ, b=Anh; f=nữ, m=nam:")
    from speech_to_speech.TTS.kokoro_handler import KOKORO_LANG_DEFAULT_VOICES

    print("  af_heart, af_bella, af_nicole, af_sarah, am_adam, am_michael, am_puck,")
    print("  bf_emma, bf_alice, bf_isabella, bf_lily, bm_fable, bm_george, bm_lewis")
    print(f"  (mặc định theo ngôn ngữ trong package: {KOKORO_LANG_DEFAULT_VOICES})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
