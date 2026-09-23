r"""Tính tất định của grounding qua 24 giờ — ô số 6 của Bảng 1 (việc 14).

    python scripts\bench_grounding_stability.py --run 1            # hôm nay
    python scripts\bench_grounding_stability.py --run 2 --same-as docs\benchmark\grounding_stability_<ngày>_run1.jsonl
    python scripts\bench_grounding_stability.py --compare <run1> <run2>

Luận điểm xương sống của bài — *"tầng cuối không tái lập được"* — hiện đang được
KHẲNG ĐỊNH chứ chưa được CHỨNG MINH. Chứng minh nó cần đúng một thứ mà không phép
đo nào rút ngắn được: **một đêm trôi qua**. Web đổi, chỉ mục của Google đổi, nên
cùng một câu hỏi qua cùng một đường mã có thể ra đáp án khác — và đó chính là điều
phải đo, không phải điều phải chữa.

## Đo cái gì

Mỗi lượt ghi NGUYÊN VĂN: câu vịt nói ra, câu do pha hai trả về, và **toàn bộ danh
sách nguồn** (cả `uri` lẫn `title`). Ngày sau chạy lại đúng bộ đó rồi so ba thứ:
bao nhiêu câu đổi đáp án, bao nhiêu câu đổi tập nguồn, và giao/hợp của hai tập
nguồn từng câu.

## Bẫy: `uri` của Gemini KHÔNG dùng để so được

`grounding_chunks[].web.uri` là đường vòng qua `vertexaisearch.cloud.google.com/
grounding-api-redirect/<token>`, mà token sinh mới theo TỪNG lời gọi. So bằng
`uri` thì mọi câu đều "đổi nguồn" 100% — một con số đúng về mặt chuỗi ký tự và vô
nghĩa về mặt khoa học. Nên `--compare` so bằng `title`, là **tên miền** nguồn
(`reuters.com`, `vnexpress.net`). `uri` vẫn được ghi đủ vào file, để sau này còn
lần lại được nguồn thật nếu cần.

## Điều kiện

`search=True` bật cứng trong chính script, không đọc `.env` — hệt `bench_grounding`,
để lượt 2 ngày mai chạy ra cùng điều kiện với lượt 1 hôm nay. Lịch sử RỖNG cho từng
câu (hiệu ứng lịch sử là phép đo khác, Bảng 6). Không ghi vào `logs/latency.jsonl`,
không đụng `docs/baseline/`.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.persona import load_persona
from config import Config, enable_utf8_console
from handlers.llm_gemini import GeminiLLMHandler
from latency import LatencyTracker
from speech_to_speech.pipeline.messages import Transcription, TTSInput

REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "docs" / "benchmark"
SET_PATH = BENCH_DIR / "lookup_set_v1.jsonl"

# Như bench_grounding: mỗi lượt tra là HAI request và grounding có hạn mức riêng.
WORKERS = 3

# 30 câu, cân bằng bốn ô (loại sự kiện × ngôn ngữ). Cân bằng chứ không lấy 30 câu
# đầu: bộ xếp en trước vi, cắt thẳng là ra một mẻ toàn tiếng Anh.
CHIA = {("fast-changing", "vi"): 8, ("fast-changing", "en"): 8,
        ("slow-changing", "vi"): 7, ("slow-changing", "en"): 7}


def doc_bo() -> list[dict]:
    if not SET_PATH.exists():
        raise SystemExit(f"Chưa có {SET_PATH}. Chạy scripts\\build_lookup_set.py trước.")
    return [json.loads(line) for line in SET_PATH.read_text(encoding="utf-8").splitlines() if line]


def doc_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def chon_bo(bo: list[dict], same_as: Path | None) -> list[dict]:
    """Bộ câu của lượt này. `--same-as` thì lấy ĐÚNG id của lượt trước.

    Lượt 2 mà tự chọn lại thì phép so hỏng ngay từ đầu, nên đường an toàn là chép
    id từ file lượt 1 chứ không tin vào việc hai lần chọn cho ra cùng kết quả.
    """
    theo_id = {r["id"]: r for r in bo}
    if same_as is not None:
        ids = [r["id"] for r in doc_jsonl(same_as)]
        thieu = [i for i in ids if i not in theo_id]
        if thieu:
            raise SystemExit(f"{len(thieu)} id trong {same_as.name} không có trong bộ 120 câu: {thieu[:3]}")
        return [theo_id[i] for i in ids]
    ra: list[dict] = []
    for (fact_type, lang), n in CHIA.items():
        ung = sorted((r for r in bo if r["block"] == "A" and r["lang"] == lang
                      and r["fact_type"] == fact_type), key=lambda r: r["id"])
        if len(ung) < n:
            raise SystemExit(f"Chỉ có {len(ung)} câu {fact_type}/{lang}, cần {n}")
        ra += ung[:n]
    return ra


class Vit:
    """Một con vịt chỉ có não, có gài móc để bắt nguyên văn kết quả pha hai.

    Móc bằng cách bọc `_ground` chứ không dùng `on_grounding`: móc kia chỉ nổ khi
    Google trả kèm HTML Search Suggestions, mà lượt tra hỏng thì không có HTML —
    và lượt hỏng lại đúng là lượt cần ghi lại nhất.
    """

    def __init__(self, cfg: Config, prompt: str) -> None:
        self.tracker = LatencyTracker(path=None, echo=False)
        self.handler = GeminiLLMHandler(
            threading.Event(), queue_in=queue.Queue(), queue_out=queue.Queue(),
            setup_kwargs={
                "api_key": cfg.gemini_api_key,
                "model": cfg.gemini_model,
                "system_prompt": prompt,
                "tracker": self.tracker,
                "search_enabled": True,
            },
        )
        goc = self.handler._ground
        self.pha_hai: dict[str, Any] | None = None

        def bat(*args, **kwargs):
            ra = goc(*args, **kwargs)
            self.pha_hai = ra
            return ra

        self.handler._ground = bat                   # type: ignore[method-assign]

    def hoi(self, text: str, lang: str) -> dict[str, Any]:
        self.tracker.start_turn()
        self.pha_hai = None
        bat_dau = perf_counter()
        cau = [out.text for out in self.handler.process(Transcription(text=text, language_code=lang))
               if isinstance(out, TTSInput)]
        record = self.tracker.finish() or {}
        pha_hai = self.pha_hai or {}
        nguon = pha_hai.get("sources") or []
        return {
            "lookup": bool(record.get("lookup_flagged")),
            "grounded": bool(record.get("grounded")),
            "search_ms": record.get("search_ms"),
            "search_error": pha_hai.get("error"),
            "n_sources": len(nguon),
            "sources": nguon,                        # [{title, uri}] NGUYÊN VĂN
            "domains": sorted({(s.get("title") or "").strip().lower() for s in nguon if s.get("title")}),
            "answer": (pha_hai.get("text") or "").strip(),   # câu pha hai trả về
            "reply": " ".join(cau).strip(),                  # câu vịt NÓI RA
            "llm_total_ms": round((perf_counter() - bat_dau) * 1000.0, 1),
        }

    def quen(self) -> None:
        self.handler.on_session_end()


def chay_song_song(viec: list[Any], lam, nhan: str) -> list[Any]:
    xong = [0]
    khoa = threading.Lock()

    def boc(item):
        try:
            ket_qua = lam(item)
        except Exception as exc:
            ket_qua = {"error": f"{type(exc).__name__}: {exc}"}
        with khoa:
            xong[0] += 1
            if xong[0] % 5 == 0 or xong[0] == len(viec):
                print(f"  {nhan}: {xong[0]}/{len(viec)}")
        return ket_qua

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(boc, viec))


def ghi_them(out: Path, rows: list[dict]) -> None:
    """NỐI vào file, không ghi đè (đợt 27b, cổng 1).

    Bản cũ mở `"w"`: chạy lại cùng `--out` (hay cùng ngày, cùng `--run`) là xoá sạch
    lượt trước mà không báo gì. Với một mẻ nhiều mốc thì mỗi mốc xoá mốc trước.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def chay(args) -> int:
    cfg = Config.load()
    if not cfg.gemini_api_key:
        print("Thiếu GEMINI_API_KEY trong ..\\.env")
        return 1
    prompt = load_persona(cfg.persona_path).system_prompt()

    same_as = Path(args.same_as) if args.same_as else None
    bo = chon_bo(doc_bo(), same_as)
    print(f"Tính tất định grounding, lượt {args.run}: {len(bo)} câu"
          f"{f' (chép id từ {same_as.name})' if same_as else ''}, {WORKERS} luồng")

    cuc_bo = threading.local()

    def mot_luot(row: dict) -> dict:
        vit = getattr(cuc_bo, "vit", None)
        if vit is None:
            vit = cuc_bo.vit = Vit(cfg, prompt)
        vit.quen()                                   # lịch sử RỖNG cho từng câu
        ran_at = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
        ra = vit.hoi(row["question"], row["lang"])
        return {"id": row["id"], "run": args.run, "ran_at": ran_at,
                "lang": row["lang"], "fact_type": row["fact_type"],
                "question": row["question"], **ra}

    rows = chay_song_song(bo, mot_luot, "câu")
    hong = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]

    out = Path(args.out) if args.out else BENCH_DIR / f"grounding_stability_{date.today():%Y%m%d}_run{args.run}.jsonl"
    ghi_them(out, rows)
    print(f"\nGhi thêm {len(rows)} bản ghi vào {out}")
    if hong:
        print(f"({len(hong)} lượt lỗi, KHÔNG ghi: {hong[0]['error']})")

    co_tra = [r for r in rows if r["grounded"]]
    print(f"  {len(co_tra)}/{len(rows)} lượt đi tra thật; "
          f"{sum(1 for r in co_tra if r['n_sources'] == 0)} lượt tra mà không nguồn nào")
    print(f"  tổng {sum(len(r['domains']) for r in co_tra)} tên miền, "
          f"{len({d for r in co_tra for d in r['domains']})} tên miền khác nhau")
    print(f"\nNgày mai: python scripts\\bench_grounding_stability.py --run 2 --same-as {out}")
    return 0


def so_sanh(p1: Path, p2: Path) -> int:
    """Ba con số của ô 6: đổi đáp án, đổi tập nguồn, giao/hợp tập nguồn.

    "Đổi đáp án" so bằng chuỗi nguyên văn của câu pha hai trả về. Đây là **chặn
    trên** của tính tất định: hai câu chữ khác nhau vẫn có thể cùng một nội dung.
    Nên báo kèm nhánh nội dung do người đọc lại, đừng báo mỗi số này.
    """
    a = {r["id"]: r for r in doc_jsonl(p1)}
    b = {r["id"]: r for r in doc_jsonl(p2)}
    chung = sorted(set(a) & set(b))
    if not chung:
        raise SystemExit("Hai file không có id nào chung.")
    print(f"So {p1.name} × {p2.name}: {len(chung)} câu chung "
          f"(lượt 1 {len(a)} câu, lượt 2 {len(b)} câu)")

    doi_dap_an = [i for i in chung if a[i]["answer"] != b[i]["answer"]]
    doi_nguon = [i for i in chung if set(a[i]["domains"]) != set(b[i]["domains"])]
    jaccard: list[float] = []
    for i in chung:
        s1, s2 = set(a[i]["domains"]), set(b[i]["domains"])
        if s1 or s2:
            jaccard.append(len(s1 & s2) / len(s1 | s2))

    n = len(chung)
    print(f"\n  đổi đáp án (nguyên văn)   {len(doi_dap_an):3}/{n}  = {len(doi_dap_an)/n:.0%}")
    print(f"  đổi tập nguồn (tên miền)  {len(doi_nguon):3}/{n}  = {len(doi_nguon)/n:.0%}")
    if jaccard:
        giu = sum(1 for j in jaccard if j == 1.0)
        mat = sum(1 for j in jaccard if j == 0.0)
        print(f"  giao/hợp tên miền         tb {sum(jaccard)/len(jaccard):.2f}"
              f"   trùng khít {giu}/{len(jaccard)}   rời hẳn {mat}/{len(jaccard)}")

    print("\n  theo loại sự kiện:")
    for ft in ("fast-changing", "slow-changing"):
        ids = [i for i in chung if a[i]["fact_type"] == ft]
        if not ids:
            continue
        d = sum(1 for i in ids if a[i]["answer"] != b[i]["answer"])
        s = sum(1 for i in ids if set(a[i]["domains"]) != set(b[i]["domains"]))
        print(f"    {ft:<15} n={len(ids):<3} đổi đáp án {d}/{len(ids)}   đổi nguồn {s}/{len(ids)}")
    print("\n  theo ngôn ngữ:")
    for lang in ("vi", "en"):
        ids = [i for i in chung if a[i]["lang"] == lang]
        if not ids:
            continue
        d = sum(1 for i in ids if a[i]["answer"] != b[i]["answer"])
        s = sum(1 for i in ids if set(a[i]["domains"]) != set(b[i]["domains"]))
        print(f"    {lang:<15} n={len(ids):<3} đổi đáp án {d}/{len(ids)}   đổi nguồn {s}/{len(ids)}")

    print("\n  vài câu đổi đáp án (xem để phân biệt đổi CHỮ với đổi NGHĨA):")
    for i in doi_dap_an[:3]:
        print(f"    [{i}] {a[i]['question'][:70]}")
        print(f"      lượt 1: {a[i]['answer'][:110]}")
        print(f"      lượt 2: {b[i]['answer'][:110]}")
    return 0


def main() -> int:
    enable_utf8_console()
    from mrunner.khoa_grounding import chan_neu_m3   # cửa sổ M3: hạn grounding dùng chung
    chan_neu_m3(Path(__file__).name)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=int, default=1, help="số thứ tự lượt (1 hôm nay, 2 ngày mai)")
    parser.add_argument("--same-as", help="file lượt trước; chép ĐÚNG bộ id của nó")
    parser.add_argument("--out", help="ghi đè đường dẫn ra")
    parser.add_argument("--compare", nargs=2, metavar=("RUN1", "RUN2"),
                        help="chỉ so hai file đã có, không gọi API")
    args = parser.parse_args()
    if args.compare:
        return so_sanh(Path(args.compare[0]), Path(args.compare[1]))
    return chay(args)


if __name__ == "__main__":
    raise SystemExit(main())
