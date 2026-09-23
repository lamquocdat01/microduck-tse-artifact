r"""Chạy LẠI đúng những lượt ollama đã chạy, trên CÙNG host, sau một quãng thời gian.

    ..\..\desktop\.venv\Scripts\python.exe scripts\rerun_check.py --arm qwen2.5:7b --n 23

## Vì sao script này tồn tại, và nó KHÔNG phải `host_check.py`

Kế hoạch ban đầu là chuyển hai nhánh open-weight sang DeepInfra, và `host_check.py` là
cổng kiểm cho việc ấy: chạy lại cùng lượt trên host mới, lệch nhãn > 10 % thì dừng.

Chủ nhân chốt **ở lại ollama** (11/09/2026). Cổng ấy lập tức mất đối tượng — không còn
host thứ hai để mà so. Bỏ luôn thì mất một cổng kiểm; nên đổi nó thành phép kiểm mà
ollama-một-mình VẪN trả lời được, và hoá ra phép ấy còn đúng chủ đề bài báo hơn:

> Cùng model, cùng prompt, cùng `seed=0`, cùng `temperature`, cùng máy — chạy lại sau
> bốn ngày và sau khi dịch vụ đã tắt đi bật lại, chữ ra có còn như cũ không?

`OllamaBackend` ghim sẵn `seed=0` và `temperature`, tức là ở đây **mọi tham số ghim được
đều đã ghim**. Nếu vẫn lệch thì cái lệch ấy đến từ chỗ khác — thứ tự nhân số dấu phẩy
động theo số luồng, phiên bản runtime, trạng thái KV cache — và đó đúng là loại bất định
mà bài báo đang đo ở tầng khác.

Nên số ra từ đây đọc được theo hai nghĩa, và phải nói rõ đang dùng nghĩa nào:

- **như một CỔNG**: lệch > 10 % thì dừng, không chạy nhánh thứ hai;
- **như một KẾT QUẢ**: nó là đối chứng dương cho luận điểm "ghim được thì tất định" —
  cùng loại bằng chứng với ô STT cục bộ 0/31.

## So cái gì

Hai mức, vì chúng trả lời hai câu khác nhau:

- `text` — chữ ra có TRÙNG TỪNG KÝ TỰ không. Đây là mức chặt nhất và là mức duy nhất
  nói được "tất định".
- `lang` — nhãn ngôn ngữ có như cũ không. Đây mới là mức mà kết luận của bài dựa vào:
  bảng F4×F5 đếm "đúng ngôn ngữ người nói", nên chữ đổi mà nhãn không đổi thì bảng ấy
  không suy suyển.

Ngưỡng 10 % của chủ nhân áp cho **`lang`**, đúng như `host_check.py` đặt.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langconf.langid import DualLangID, _same_language     # noqa: E402
from langconf.models import OllamaBackend                  # noqa: E402

RESULTS = ROOT / "results"
DATA = ROOT / "data"
STOP_THRESHOLD = 0.10


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", default="qwen2.5:7b")
    parser.add_argument("--n", type=int, default=23)
    parser.add_argument("--seed", type=int, default=20260911,
                        help="hạt giống lấy mẫu — ghim để mẻ này lặp lại được")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    slug = args.arm.replace(":", "-").replace("/", "_")
    src = RESULTS / f"main_{slug}.jsonl"
    if not src.exists():
        raise SystemExit(f"chưa có {src}")
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("reply_text") and not r.get("model_error")]
    print(f"{src.name}: {len(rows)} lượt dùng được")

    # Lấy mẫu NGẪU NHIÊN có ghim hạt giống, không lấy 23 lượt đầu: 23 lượt đầu đều ở
    # cùng vài ô của lưới, mà cái cần biết là host có ổn định trên CẢ lưới hay không.
    rng = random.Random(args.seed)
    mau = rng.sample(rows, min(args.n, len(rows)))
    print(f"lấy mẫu {len(mau)} lượt (seed {args.seed})\n")

    lid = DualLangID(DATA / "lid" / "lid.176.bin")
    backend = OllamaBackend(args.arm, timeout_s=900)

    ket = []
    trung_chu = trung_nhan = 0
    for i, r in enumerate(mau, 1):
        t0 = time.perf_counter()
        rep = backend.chat(r["messages"])
        dt = time.perf_counter() - t0
        if rep.error:
            print(f"  [{i:2d}/{len(mau)}] LỖI {rep.error}")
            ket.append({"probe_id": r.get("probe_id"), "loi": rep.error})
            continue
        cu, moi = r["reply_text"], rep.text
        l_cu = lid.detect(cu)
        l_moi = lid.detect(moi)
        same_text = (cu == moi)
        same_lang = _same_language(l_cu.fasttext, l_moi.fasttext)
        trung_chu += same_text
        trung_nhan += same_lang
        print(f"  [{i:2d}/{len(mau)}] chữ {'=' if same_text else 'KHÁC'} · "
              f"nhãn {l_cu.fasttext}->{l_moi.fasttext} {'=' if same_lang else 'KHÁC'} · "
              f"{dt:.1f}s")
        ket.append({
            "probe_id": r.get("probe_id"), "depth": r.get("depth"),
            "label_position": r.get("label_position"), "spoken_lang": r.get("spoken_lang"),
            "cu": cu, "moi": moi,
            "lang_cu": l_cu.fasttext, "lang_moi": l_moi.fasttext,
            "trung_chu": same_text, "trung_nhan": same_lang,
            "latency_cu_ms": r.get("latency_ms"), "latency_moi_ms": round(dt * 1000, 1),
        })

    n = sum(1 for k in ket if "loi" not in k)
    if n == 0:
        raise SystemExit("không lượt nào chạy được")
    ti_chu, ti_nhan = trung_chu / n, trung_nhan / n
    lech_nhan = 1.0 - ti_nhan

    out = Path(args.out) if args.out else RESULTS / f"rerun_check_{slug}.json"
    out.write_text(json.dumps({
        "arm": args.arm, "n": n, "seed": args.seed,
        "ngay": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "trung_chu": trung_chu, "trung_nhan": trung_nhan,
        "ti_le_trung_chu": round(ti_chu, 4), "ti_le_trung_nhan": round(ti_nhan, 4),
        "nguong_dung": STOP_THRESHOLD, "luot": ket,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n  trùng TỪNG KÝ TỰ : {trung_chu}/{n} = {ti_chu:.3f}")
    print(f"  trùng NHÃN NGÔN NGỮ: {trung_nhan}/{n} = {ti_nhan:.3f}  (lệch {lech_nhan:.3f})")
    print(f"  -> {out}")
    if lech_nhan > STOP_THRESHOLD:
        print(f"\n  DỪNG: lệch nhãn {lech_nhan:.1%} > ngưỡng {STOP_THRESHOLD:.0%} "
              f"của chủ nhân. Không chạy nhánh thứ hai.")
        return 2
    print(f"\n  QUA CỔNG: lệch nhãn {lech_nhan:.1%} <= {STOP_THRESHOLD:.0%}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
