r"""Chạy MỘT việc nặng (pytest, đồng bộ mail, server.py để test giọng) mà không đè mẻ đo (CLAUDE.md).

    python scripts\runner_safe.py -- .venv\Scripts\python.exe -m pytest -q
    python scripts\runner_safe.py --minutes 25 -- .venv\Scripts\python.exe server.py
    python scripts\runner_safe.py --minutes 5 -- .venv\Scripts\python.exe scripts\mail_cli.py sync
    python scripts\runner_safe.py --status          # chỉ in trạng thái cổng, không làm gì

Thứ tự (mỗi bước kiểm bằng file/mã thoát, không bằng mắt), giống commit_safe.ps1:
  1. tạo PAUSE (nếu chưa có; nhớ là mình tạo)
  2. chờ `mrunner.gate.state` ra `free` hoặc `paused` (runner xác nhận rảnh); quá --wait -> thôi, rc 4
  3. cửa sổ M3 đè lên [bây giờ, bây giờ + --minutes] -> thôi, rc 3 (dưới PAUSE runner vẫn chạy M3)
  4. chạy lệnh; quá --minutes thì DỪNG nó (PAUSE chặn cả M6 có mốc: giữ lâu là làm lỡ mốc đo)
  5. xoá PAUSE nếu mình tạo — luôn luôn, kể cả khi hỏng hay Ctrl+C
Mã thoát = mã thoát của lệnh (hoặc 3/4 khi không chạy).

--minutes là thời gian DỰ KIẾN của việc: cửa sổ M3 kiểm trên cả khoảng ấy, và nó cũng là trần.
Việc chạy đè M6 có mốc: PAUSE làm M6 chờ — nên chọn lúc không có mốc M6 trong khoảng ấy
(`run_m_all.py status`, cột "mốc kế tiếp"); script cảnh báo nếu thấy.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESKTOP))

from mrunner import gate  # noqa: E402


def _say(msg: str) -> None:
    print(f"runner_safe: {msg}", flush=True)


def _next_m6(rd: Path, now: datetime, minutes: float) -> str | None:
    """Mốc M6 chưa xong trong khoảng việc chạy (chỉ để CẢNH BÁO; đọc plan + jsonl, hỏng thì im)."""
    try:
        import json

        plan = json.loads((rd / "plan.json").read_text(encoding="utf-8"))
        tasks = plan["tasks"] if isinstance(plan, dict) else plan
        done: set[str] = set()
        for f in rd.parent.glob("M6_*.jsonl"):
            if f.name.endswith((".manifest.jsonl", ".errors.jsonl")):
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    done.add(json.loads(line)["task_id"])
                except Exception:
                    pass
        end = now.timestamp() + minutes * 60
        for t in tasks:
            if str(t.get("id", "")).startswith("M6") and t.get("at") and t["id"] not in done:
                at = datetime.fromisoformat(t["at"]).timestamp()
                if at <= end:
                    return f"{t['id']} @ {t['at']}"
    except Exception:
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutes", type=float, default=10.0, help="thời gian dự kiến = trần (mặc định 10)")
    parser.add_argument("--wait", type=float, default=30.0, help="phút tối đa chờ runner xác nhận rảnh")
    parser.add_argument("--status", action="store_true", help="chỉ in trạng thái cổng")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="-- <lệnh> [tham số]")
    args = parser.parse_args(argv)

    if args.status:
        st = gate.state()
        _say(f"{st.verdict} — {st.reason}")
        return 0
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        parser.error("thiếu lệnh sau --")

    rd = gate.main_runner_dir()
    if rd is None or not rd.is_dir():
        _say(f"THÔI — không tìm ra thư mục runner của repo chính ({rd}); fail closed")
        return 4
    pause = rd / "PAUSE"
    created = False
    try:
        if not pause.exists():
            pause.touch()
            created = True
        _say(f"PAUSE {'đã tạo' if created else 'có sẵn (của người khác, sẽ KHÔNG xoá)'}")
        deadline = time.monotonic() + args.wait * 60
        while True:
            st = gate.state(rd)
            if st.verdict in ("free", "paused"):
                _say(f"cổng: {st.verdict} — {st.reason}")
                break
            if time.monotonic() > deadline:
                _say(f"THÔI — quá {args.wait:g} phút runner chưa xác nhận rảnh: {st.reason}")
                return 4
            time.sleep(5)
        now = datetime.now()
        if st.verdict == "paused":
            mark = gate.m3_conflict(now, args.minutes)
            if mark is not None:
                _say(f"THÔI — {args.minutes:g} phút tới đè cửa sổ M3 quanh {mark:%Y-%m-%d %H:%M}")
                return 3
            m6 = _next_m6(rd, now, args.minutes)
            if m6:
                _say(f"CẢNH BÁO: mốc {m6} rơi vào khoảng này — PAUSE làm nó chờ tới khi xong")
        # CreateProcess không tự tìm ".venv/Scripts/python.exe" (tương đối, dấu /): phân giải trước.
        exe = Path(cmd[0])
        if exe.exists():
            cmd = [str(exe.resolve()), *cmd[1:]]
        elif found := shutil.which(cmd[0]):
            cmd = [found, *cmd[1:]]
        _say(f"chạy (trần {args.minutes:g} phút): {' '.join(cmd)}")
        proc = subprocess.Popen(cmd)
        try:
            rc = proc.wait(timeout=args.minutes * 60)
        except subprocess.TimeoutExpired:
            _say(f"quá trần {args.minutes:g} phút -> dừng lệnh")
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            rc = 124
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait(timeout=15)
            rc = 130
        _say(f"lệnh xong rc={rc}")
        return rc
    finally:
        if created:
            try:
                pause.unlink()
            except FileNotFoundError:
                pass
        _say(f"PAUSE {'đã xoá' if created else 'giữ nguyên'}")


if __name__ == "__main__":
    raise SystemExit(main())
