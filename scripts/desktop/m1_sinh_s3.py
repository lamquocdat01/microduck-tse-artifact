r"""Sinh tầng S3 của M1 (AMENDMENT 04 §A04.2): 23 câu v3 × 3 giọng × 3 lần render, tổng hợp.

    python scripts\m1_sinh_s3.py            # sinh + kiểm + manifest (không ghi đè file đã có)
    python scripts\m1_sinh_s3.py --kiem     # chỉ kiểm lại SHA-256 các file theo manifest

Đường sinh = đường của bộ `realvoice_20260904` (`bench_stt.py::synthesize`): `DuckTTSHandler` của
pipeline — VieNeu cho câu vi, Kokoro (`_process_kokoro`, 24 kHz → 16 kHz, int16) cho câu en.

Mỗi render đi qua **VAD của app** (`DuckVADHandler`, tham số như `pipeline.py`: thresh 0,5,
min_silence 250 ms, khối 512 mẫu), đệm 0,5 s im lặng trước và 1,0 s sau. Chỉ giữ render mà VAD
cắt ra **đúng một** đoạn; WAV lưu là **đoạn VAD trả ra** — đúng thứ STT của app nhận, như 31 WAV
thật S1 (cũng là audio sau VAD). Render bị loại ghi lý do; S3 < 200 thì render lần 4 cho đúng
các (câu, giọng) bị loại.

Đầu ra: `desktop/logs/utts_s3/s3_sNN_vV_rK.wav` + `docs/benchmark/M1_s3_manifest.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from queue import Queue

import numpy as np

DESKTOP = Path(__file__).resolve().parents[1]
REPO = DESKTOP.parent
sys.path.insert(0, str(DESKTOP))

from mrunner import hf_pin as _hf  # noqa: E402

_hf.dat_moi_truong()                   # A05: trước mọi import kéo huggingface_hub

from audio_wav import SAMPLE_RATE, write_wav  # noqa: E402

CAU = REPO / "docs/benchmark/M1_rv2_sentences.json"
OUT = DESKTOP / "logs/utts_s3"
MANIFEST = REPO / "docs/benchmark/M1_s3_manifest.json"
S1_MAU = DESKTOP / "logs/utts/20260906_134002_001.wav"
GIONG = {"vi": ["Trúc Ly", "Xuân Vĩnh", "Quang Sơn"], "en": ["af_heart", "am_michael", "bm_fable"]}
LAN_RENDER = 3
TOI_THIEU = 200
VAD_KW = {"thresh": 0.5, "min_silence_ms": 250}
DEM_TRUOC_S, DEM_SAU_S, KHOI = 0.5, 1.0, 512


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dinh_dang(p: Path) -> dict:
    with wave.open(str(p), "rb") as w:
        return {"sample_rate": w.getframerate(), "channels": w.getnchannels(),
                "sample_width_bytes": w.getsampwidth(), "n_samples": w.getnframes()}


def dem_vad(audio_i16: np.ndarray) -> list[np.ndarray]:
    """Cho audio qua VAD của app theo khối 512 mẫu; trả các đoạn 'final' VAD cắt ra."""
    from speech_to_speech.pipeline.messages import VADAudio
    from handlers.vad_duck import DuckVADHandler

    listen = threading.Event()
    vad = DuckVADHandler(threading.Event(), queue_in=Queue(), queue_out=Queue(),
                         setup_args=(listen,), setup_kwargs=dict(VAD_KW))
    x = np.concatenate([np.zeros(int(DEM_TRUOC_S * SAMPLE_RATE), np.int16), audio_i16,
                        np.zeros(int(DEM_SAU_S * SAMPLE_RATE), np.int16)])
    x = np.pad(x, (0, (-len(x)) % KHOI))
    doan = []
    for i in range(0, len(x), KHOI):
        listen.set()                                   # app bật lại nghe sau mỗi lượt
        for out in vad.process(x[i:i + KHOI].tobytes()):
            if isinstance(out, VADAudio) and out.mode in (None, "final"):
                doan.append(np.asarray(out.audio))
    return doan


class Tts:
    def __init__(self) -> None:
        from handlers.tts_vieneu import DuckTTSHandler
        self.h = DuckTTSHandler(threading.Event(), queue_in=Queue(), queue_out=Queue(),
                                setup_args=(threading.Event(),),
                                setup_kwargs={"device": "cpu", "voice": "af_heart", "lang_code": "a",
                                              "blocksize": 512, "voice_vi": GIONG["vi"][0],
                                              "vieneu_precision": "fp32"})
        self._kp: dict[str, object] = {}

    def render(self, text: str, lang: str, giong: str) -> np.ndarray:
        if lang == "vi":
            chunks = list(self.h.vieneu.stream(text, voice=giong))
        else:
            from kokoro import KPipeline
            lc = giong[0]
            if lc not in self._kp:
                self._kp[lc] = KPipeline(lang_code=lc, repo_id="hexgrad/Kokoro-82M")
            self.h.voice, self.h.lang_code, self.h.pipeline = giong, lc, self._kp[lc]
            chunks = list(self.h._process_kokoro(text, None))   # None: không tự đổi giọng
        return np.concatenate(chunks).astype(np.int16)


VN_REPO = Path.home() / ".cache/huggingface/hub/models--pnnbao-ump--VieNeu-TTS-v3-Turbo"
VN_FILES = ("config.json", "denoiser.onnx", "onnx_update/config.json", "onnx_update/tokenizer.json",
            "onnx_update/vieneu_prefill.onnx", "onnx_update/vieneu_decode_step.onnx",
            "onnx_update/vieneu_acoustic_cached.onnx", "onnx_update/vieneu_v3_heads.npz",
            "onnx_update/vieneu_backbone_shared.data")


def mo_ta_vieneu() -> dict:
    """VieNeu nạp `pnnbao-ump/VieNeu-TTS-v3-Turbo/onnx_update` (fp32) qua hf_hub_download = snapshot
    mà `refs/main` trỏ tới LÚC NẠP. Thư viện tự tải revision mới khi có mạng — nên ghi cả revision
    lẫn SHA-256 từng file trọng số, và so với mọi snapshot khác trong cache."""
    rev = (VN_REPO / "refs/main").read_text().strip()
    snap = VN_REPO / "snapshots" / rev
    files = {f: sha_file((snap / f).resolve()) for f in VN_FILES}
    khac = {}
    for s in sorted((VN_REPO / "snapshots").glob("*")):
        if s.name != rev:
            khac[s.name] = all((s / f).exists() and sha_file((s / f).resolve()) == files[f] for f in VN_FILES)
    return {"vieneu_repo": "pnnbao-ump/VieNeu-TTS-v3-Turbo", "vieneu_revision_refs_main": rev,
            "vieneu_precision": "fp32 (onnx_update)", "vieneu_files_sha256": files,
            "vieneu_snapshot_khac_cung_trong_so": khac}


def mo_ta_model(tts: Tts) -> dict:
    import importlib.metadata as md
    hub = Path.home() / ".cache/huggingface/hub"
    goi = {}
    for p in ("vieneu", "kokoro", "misaki", "onnxruntime", "torch", "speech-to-speech", "scipy", "numpy"):
        try:
            goi[p] = md.version(p)
        except Exception:
            goi[p] = None
    kok = sorted((hub / "models--hexgrad--Kokoro-82M/snapshots").glob("*"))
    kok_files = {}
    if kok:
        for f in [kok[-1] / "kokoro-v1_0.pth", kok[-1] / "config.json"] + \
                 [kok[-1] / "voices" / f"{g}.pt" for g in GIONG["en"]]:
            if f.exists():
                kok_files[f.relative_to(kok[-1]).as_posix()] = sha_file(f.resolve())
    return {"goi": goi, **mo_ta_vieneu(),
            "kokoro_repo": "hexgrad/Kokoro-82M", "kokoro_snapshot": kok[-1].name if kok else None,
            "kokoro_files_sha256": kok_files,
            "license": {"VieNeu-TTS-v3-Turbo": "Apache-2.0 (model card, kiểm 17/09/2026; audio từ giọng preset được phép dùng, kể cả thương mại)",
                        "Kokoro-82M": "Apache-2.0", "S3 audio": "CC BY 4.0"}}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kiem", action="store_true")
    ap.add_argument("--ghi-vieneu", action="store_true",
                    help="bổ sung mô tả VieNeu vào manifest đã có (bản sinh 17/09 07:50 ghi rỗng)")
    args = ap.parse_args()

    if args.ghi_vieneu:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        vn = mo_ta_vieneu()
        man["model"].update(vn)
        man["model"]["vieneu_bo_sung"] = {
            "ghi_luc": datetime.now().astimezone().isoformat(timespec="seconds"),
            "script_sha256_luc_bo_sung": sha_file(Path(__file__)),
            "ly_do": "lần sinh ghi vieneu_files_sha256 rỗng (dò thuộc tính engine không ra đường dẫn). "
                     "refs/main đổi sang revision này lúc 2026-09-17 07:13:37 (+07:00) — thư viện tự tải khi nạp, "
                     "TRƯỚC lần sinh 07:50:59 và không đổi sau đó, nên đây là revision đã sinh S3. "
                     "Trọng số giống hệt các snapshot 04–05/09 (xem vieneu_snapshot_khac_cung_trong_so)."}
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(vn, ensure_ascii=False, indent=1))
        return 0

    if args.kiem:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        hong = [f["file"] for f in man["files"] if f["accepted"]
                and sha_file(REPO / f["file"]) != f["sha256"]]
        print(f"kiểm {sum(f['accepted'] for f in man['files'])} file: {len(hong)} lệch SHA-256", hong[:5])
        return 1 if hong else 0

    # A05: VieNeu nạp theo repo id (thư viện không nhận đường dẫn snapshot) ⇒ offline + refs/main
    # PHẢI trỏ đúng revision ghim + SHA-256 khớp; lệch thì không sinh.
    from mrunner import hf_pin
    tts_repos = ("pnnbao-ump/VieNeu-TTS-v3-Turbo", "hexgrad/Kokoro-82M")   # cả hai nạp theo repo id
    loi = hf_pin.kiem(repos=tts_repos)
    for vn in tts_repos:
        ref = hf_pin.HUB / ("models--" + vn.replace("/", "--")) / "refs/main"
        rm = ref.read_text().strip() if ref.exists() else "—"
        if rm != hf_pin.PIN[vn]["revision"]:
            loi.append(f"{vn}: refs/main {rm[:12]} ≠ revision ghim {hf_pin.PIN[vn]['revision'][:12]}")
    if loi:
        print("TỪ CHỐI SINH (A05):\n  " + "\n  ".join(loi))
        return 1
    bo = json.loads(CAU.read_text(encoding="utf-8"))
    assert bo["phien_ban"] == 3 and len(bo["cau"]) == 23, "cần bộ câu v3, 23 câu"
    s1 = dinh_dang(S1_MAU)
    OUT.mkdir(parents=True, exist_ok=True)
    bat_dau = datetime.now().astimezone().isoformat(timespec="seconds")
    tts = Tts()
    rec: list[dict] = []

    def mot(c: dict, vi: int, r: int) -> dict:
        lang, giong = c["lang"], GIONG[c["lang"]][vi - 1]
        f = OUT / f"s3_s{c['so']:02d}_v{vi}_r{r}.wav"
        if f.exists():
            raise SystemExit(f"{f} đã có — không ghi đè. Xoá thư mục có chủ ý rồi chạy lại.")
        t0 = time.perf_counter()
        raw = tts.render(c["text"], lang, giong)
        ms = (time.perf_counter() - t0) * 1000
        doan = dem_vad(raw)
        d = {"file": f.relative_to(REPO).as_posix(), "s": c["so"], "v": vi, "voice": giong, "lang": lang,
             "r": r, "text": c["text"], "render_ms": round(ms), "raw_n_samples": int(len(raw)),
             "raw_sha256": hashlib.sha256(raw.tobytes()).hexdigest(), "vad_segments": len(doan)}
        if len(doan) == 1:
            write_wav(f, doan[0])
            fm = dinh_dang(f)
            khop = all(fm[k] == s1[k] for k in ("sample_rate", "channels", "sample_width_bytes"))
            d.update(accepted=khop, sha256=sha_file(f), duration_s=round(fm["n_samples"] / fm["sample_rate"], 3),
                     **{k: fm[k] for k in ("sample_rate", "channels", "sample_width_bytes", "n_samples")})
            if not khop:
                d["reason"] = f"định dạng khác S1 {s1}"
                f.unlink()
        else:
            d.update(accepted=False, sha256=None,
                     reason=f"VAD cắt ra {len(doan)} đoạn (cần đúng 1)")
        print(f"{'✓' if d['accepted'] else '✗'} {f.name} {giong:10s} {d.get('duration_s', '-')} s "
              f"VAD={len(doan)} {c['text']}", flush=True)
        return d

    for c in bo["cau"]:
        for vi in (1, 2, 3):
            for r in range(1, LAN_RENDER + 1):
                rec.append(mot(c, vi, r))
    loai = [d for d in rec if not d["accepted"]]
    if sum(d["accepted"] for d in rec) < TOI_THIEU and loai:
        print(f"S3 < {TOI_THIEU}: render lần 4 cho {len({(d['s'], d['v']) for d in loai})} (câu, giọng) bị loại")
        for s, vi in sorted({(d["s"], d["v"]) for d in loai}):
            rec.append(mot(next(c for c in bo["cau"] if c["so"] == s), vi, LAN_RENDER + 1))

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    except Exception:
        commit = ""
    n_ok = sum(d["accepted"] for d in rec)
    man = {"prereg": "docs/benchmark/PREREG_M1-M4_20260916.md §AMENDMENT 04 A04.2",
           "tang": "S3", "tao_luc": bat_dau, "xong_luc": datetime.now().astimezone().isoformat(timespec="seconds"),
           "commit": commit, "script": "desktop/scripts/m1_sinh_s3.py",
           "script_sha256": sha_file(Path(__file__)), "python": sys.version, "may": platform.node(),
           "cau": {"file": CAU.relative_to(REPO).as_posix(), "phien_ban": bo["phien_ban"], "sha256": sha_file(CAU)},
           "giong": GIONG, "lan_render": LAN_RENDER,
           "tts_tat_dinh": False,
           "vad": {"handler": "handlers.vad_duck.DuckVADHandler", **VAD_KW, "khoi_mau": KHOI,
                   "dem_truoc_s": DEM_TRUOC_S, "dem_sau_s": DEM_SAU_S,
                   "luu": "đoạn VAD trả ra (đúng 1 đoạn), như S1"},
           "dinh_dang_S1": {**s1, "mau": S1_MAU.relative_to(REPO).as_posix()},
           "model": mo_ta_model(tts),
           "tong": {"render": len(rec), "nhan": n_ok, "loai": len(rec) - n_ok, "toi_thieu": TOI_THIEU},
           "files": rec}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nS3: nhận {n_ok}/{len(rec)} render → {MANIFEST.relative_to(REPO)}")
    return 0 if n_ok >= TOI_THIEU else 1


if __name__ == "__main__":
    raise SystemExit(main())
