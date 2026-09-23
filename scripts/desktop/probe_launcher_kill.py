r"""Probe (đợt 27b): `kill` launcher venv có tới tiến trình làm việc không? — ứng viên ca hỏng-âm-thầm #7, ĐÃ BÁC.

    python scripts\probe_launcher_kill.py

Trên Windows, `desktop\.venv\Scripts\python.exe` là một launcher: nó sinh python gốc làm tiến
trình CON và chờ. `Popen(...).pid` là PID launcher. Cổng "kill giữa chừng rồi khởi động lại"
ban đầu gọi `Process(p.pid).kill()` — lệnh trả về thành công, `p.wait()` trả về, và cổng
XANH. Câu hỏi của probe này: con có sống tiếp và làm nốt việc không?

A/B, cùng plan giả 200 task × 0,1 s, runner `--dry-run`:
  A  kill PID launcher      → đo: con còn sống? số bản ghi có tăng sau kill?
  B  kill cả cây (con trước) → cùng hai phép đo
Ghi `docs/benchmark/probe_launcher_kill_20260916.json`.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

DESKTOP = Path(__file__).resolve().parents[1]
REPO = DESKTOP.parent
VENV_PY = DESKTOP / ".venv" / "Scripts" / "python.exe"
SCRIPT = DESKTOP / "scripts" / "run_m_all.py"
OUT = REPO / "docs/benchmark/probe_launcher_kill_20260916.json"


def dem(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for l in p.read_bytes().splitlines() if l.strip())


def mot_nhanh(ten: str, giet_cay: bool) -> dict:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        tasks = [{"id": f"MA|x{i:03d}|t0", "m": "MA", "kind": "loc", "order": 1} for i in range(200)]
        plan = root / "plan.json"
        plan.write_text(json.dumps({"runner_dir": "runner", "results": {"MA": "MA.jsonl"},
                                    "late_missed_s": 7200, "budget_usd": 5,
                                    "price": {"in_text": .3, "in_audio": 1, "out": 2.5,
                                              "grounding_per_1000": 35, "grounding_free_per_day": 0},
                                    "tasks": tasks}), encoding="utf-8")
        env = {**os.environ, "MRUNNER_DRY_SLEEP": "0.1"}
        p = subprocess.Popen([str(VENV_PY), str(SCRIPT), "--plan", str(plan), "--root", str(root),
                              "run", "--dry-run", "--stop-when-idle"], env=env)
        res = root / "MA.jsonl"
        han = time.time() + 60
        while dem(res) < 10 and time.time() < han:
            time.sleep(0.05)
        la = psutil.Process(p.pid)
        con = la.children(recursive=True)
        ghi = {"nhanh": ten, "launcher": {"pid": p.pid, "name": la.name()},
               "con": [{"pid": c.pid, "name": c.name()} for c in con]}
        n_luc_kill = dem(res)
        t_kill = time.time()
        if giet_cay:
            for c in con:
                c.kill()
        la.kill()
        rc = p.wait(timeout=30)
        ghi["kill_tra_ve"] = {"popen_wait_rc": rc, "giay": round(time.time() - t_kill, 3)}
        time.sleep(3.0)
        song = [c.pid for c in con if c.is_running() and c.status() != psutil.STATUS_ZOMBIE]
        n_sau_3s = dem(res)
        ghi.update({"ban_ghi_luc_kill": n_luc_kill, "ban_ghi_sau_3s": n_sau_3s,
                    "con_con_song_sau_3s": song})
        han = time.time() + 60
        while song and any(psutil.pid_exists(x) for x in song) and time.time() < han:
            time.sleep(0.2)
        ghi["ban_ghi_khi_con_tu_ket_thuc"] = dem(res)
        for x in song:                       # dọn nếu vẫn còn
            try:
                psutil.Process(x).kill()
            except psutil.NoSuchProcess:
                pass
        return ghi


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    kq = {"ngay": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "may": platform.platform(),
          "python_launcher": str(VENV_PY.relative_to(REPO)), "plan": "200 task giả × 0,1 s",
          "A_kill_launcher": mot_nhanh("A", giet_cay=False),
          "B_kill_ca_cay": mot_nhanh("B", giet_cay=True)}
    OUT.write_text(json.dumps(kq, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k in ("A_kill_launcher", "B_kill_ca_cay"):
        g = kq[k]
        print(f"{k}: launcher {g['launcher']['name']} → con {[c['name'] for c in g['con']]}; "
              f"wait rc={g['kill_tra_ve']['popen_wait_rc']}; bản ghi lúc kill {g['ban_ghi_luc_kill']}, "
              f"sau 3 s {g['ban_ghi_sau_3s']}, khi con tự kết thúc {g['ban_ghi_khi_con_tu_ket_thuc']}; "
              f"con sống sau 3 s: {g['con_con_song_sau_3s']}")
    print(f"-> {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
