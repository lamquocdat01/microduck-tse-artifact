r"""Runner nền DUY NHẤT cho mẻ đo M1–M4 (đợt 27b). Luật ở `desktop/mrunner/core.py`.

    python scripts\run_m_all.py plan --m3-first 2026-09-16T21:00+07:00 --free-per-day 500
    python scripts\run_m_all.py --ensure      # cho watchdog Task Scheduler (15 phút/lần)
    python scripts\run_m_all.py status
    python scripts\run_m_all.py status-log    # Task Scheduler 09:05 & 21:05 → runner\status_log.md (việc 121)
    python scripts\run_m_all.py doctor
    python scripts\run_m_all.py run           # chạy tiền cảnh (--ensure tự gọi lệnh này)

`PAUSE`: tạo `docs\benchmark\runner\PAUSE` ⇒ runner làm xong task đang chạy rồi chỉ nhận
task M3 đến hạn. Dùng khi cần `pytest` (test đồng hồ treo tường). Xoá file ⇒ chạy tiếp.

`--root` / `--plan` / `--dry-run` chỉ dùng cho cổng kiểm: `--dry-run` thay executor thật
bằng executor giả (không gọi API, không nạp model).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1]
REPO = DESKTOP.parent
sys.path.insert(0, str(DESKTOP))

# AMENDMENT 05: offline Hugging Face TRƯỚC mọi import có thể kéo huggingface_hub vào (nó đọc biến
# lúc import). Áp cho mọi lệnh: watchdog (--ensure), run, status, doctor, và tiến trình con.
from mrunner import hf_pin  # noqa: E402

hf_pin.dat_moi_truong()

from mrunner.core import Lock, Runner, from_iso, to_iso  # noqa: E402

PLAN_MAC_DINH = REPO / "docs/benchmark/runner/plan.json"


def nap_plan(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def runner_dir(plan: dict, root: Path) -> Path:
    return Path(root) / plan["runner_dir"]


class DryExec:
    """Executor giả cho cổng kiểm. Hosted giả khai usage để trần tiền đếm được."""

    def __init__(self, hosted: bool) -> None:
        self.hosted = hosted

    def manifest(self, t: dict) -> dict:
        return {"kind": "dry", "hosted": self.hosted}

    def run(self, t: dict) -> dict:
        time.sleep(float(os.environ.get("MRUNNER_DRY_SLEEP", "0")))
        out = {"dry": True}
        if self.hosted:
            out["usage"] = {"in_text": 1000, "in_audio": 0, "out": 100, "grounded": 0}
        return out


def dry_executors(plan: dict) -> dict:
    kinds = {t["kind"]: bool(t.get("hosted")) for t in plan["tasks"]}
    return {k: DryExec(h) for k, h in kinds.items()}


_CPU_DO: list[tuple[float, bool]] = []
CPU_DUNG_LAI_S = 120


def cpu_ban() -> bool:
    """CPU trung bình 30 s > 60 % do tiến trình KHÁC (runner đang đứng chờ nên phần của nó ≈ 0).

    Đo CHẶN 30 s lúc runner rảnh — không đo nền liên tục, vì khi đó CPU của chính ollama
    (task vừa xong) bị tính là "tiến trình khác" và runner tự thấy máy luôn bận. Kết quả dùng
    lại trong 120 s: đo trước MỖI task nặng thì cộng 30 s vào mỗi task (M1 local ~7 h thêm)
    và kéo giãn mốc "tức thì" thành ≥ 30 s. Cache này là bộ nhớ tạm vô hại (luật 1 của core).
    """
    import time as _t
    import psutil
    if _CPU_DO and _t.time() - _CPU_DO[-1][0] < CPU_DUNG_LAI_S:
        return _CPU_DO[-1][1]
    me = psutil.Process()
    me.cpu_percent(None)
    tong = psutil.cpu_percent(interval=30)
    cua_toi = me.cpu_percent(None) / (psutil.cpu_count() or 1)
    ban = (tong - cua_toi) > 60.0
    _CPU_DO[:] = [(_t.time(), ban)]
    logging.info("cảm biến CPU: %.0f %% (khác runner %.0f %%) → %s", tong, tong - cua_toi,
                 "BẬN" if ban else "rảnh")
    return ban


def cai_log(plan: dict, root: Path) -> None:
    d = runner_dir(plan, root)
    d.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(d / "runner.log", maxBytes=5 * 1024 * 1024,
                                             backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root_log = logging.getLogger()
    root_log.handlers[:] = [h]
    root_log.setLevel(logging.INFO)


def ha_uu_tien() -> None:
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass


REPO_RUNNER = ("mobiuslabsgmbh/faster-whisper-large-v3-turbo",)


def kiem_hf_runner(plan: dict) -> list[str]:
    """Cổng A05 cho runner thật: plan phải khai hf_pin, trùng pin trong mã, và model runner nạp khớp."""
    if "hf_pin" not in plan:
        return ["plan.json không có hf_pin (chạy `plan --amend 05`)"]
    if plan["hf_pin"] != hf_pin.PIN:
        return ["plan.hf_pin khác mrunner/hf_pin.PIN — mã và plan không cùng một bản ghim"]
    return hf_pin.kiem(plan["hf_pin"], repos=REPO_RUNNER)


def git_goc() -> Path:
    """Repo chứa MÃ runner (không phải --root dữ liệu). MRUNNER_GIT_ROOT chỉ cho cổng kiểm."""
    return Path(os.environ.get("MRUNNER_GIT_ROOT") or REPO)


def lenh_run(args) -> int:
    from mrunner import cay_git
    plan = nap_plan(args.plan)
    root = Path(args.root)
    cai_log(plan, root)
    lock = Lock(runner_dir(plan, root) / "LOCK")
    them = None
    if not args.dry_run:
        ban_ = cay_git.ban(git_goc())
        if ban_:
            logging.error("TỪ CHỐI CHẠY (cây làm việc bẩn trong phạm vi %s): %s",
                          ",".join(cay_git.PHAM_VI), "; ".join(ban_[:10]))
            return 1
        them = {"commit": cay_git.head(git_goc())}
    if not lock.acquire(them):
        logging.info("đã có runner sống (%s), thoát", lock.holder())
        return 0
    import atexit
    atexit.register(lock.release)
    ha_uu_tien()
    n = str(max(2, (os.cpu_count() or 4) - 2))
    os.environ.setdefault("OMP_NUM_THREADS", n)
    if args.dry_run:
        ex = dry_executors(plan)
        busy = None
    else:
        loi = kiem_hf_runner(plan)
        if loi:
            for x in loi:
                logging.error("TỪ CHỐI CHẠY (A05 hf_pin): %s", x)
            lock.release()
            return 1
        logging.info("hf_pin đạt: offline=1, revision ghim khớp SHA-256 (%s)",
                     ", ".join(f"{r}@{v['revision'][:12]}" for r, v in plan["hf_pin"].items()))
        from mrunner.thuc import executors
        ex = executors(plan)
        busy = cpu_ban
    logging.info("runner bắt đầu pid=%d dry=%s", os.getpid(), args.dry_run)
    r = Runner(plan, root, ex, cpu_busy=busy)
    r.loop(max_steps=args.max_steps, stop_when_idle=args.stop_when_idle)
    return 0


def lenh_ensure(args) -> int:
    plan = nap_plan(args.plan)
    root = Path(args.root)
    lock = Lock(runner_dir(plan, root) / "LOCK")
    h = lock.holder()
    if not args.dry_run:
        from mrunner import cay_git
        rd = runner_dir(plan, root)
        hd, ban_ = cay_git.head(git_goc()), cay_git.ban(git_goc())
        loi = []
        if ban_:
            loi.append(f"cây làm việc bẩn trong phạm vi {','.join(cay_git.PHAM_VI)}: {'; '.join(ban_[:10])}")
        if h is not None and h.get("commit") != hd:
            loi.append(f"runner pid {h['pid']} chạy commit {str(h.get('commit'))[:12]} ≠ HEAD {str(hd)[:12]} "
                       "(PAUSE → dừng runner → --ensure để chạy mã HEAD)")
        if loi:
            msg = "TỪ CHỐI --ensure: " + " | ".join(loi)
            # watchdog gọi mỗi 15 phút: ghi log khi thông điệp ĐỔI, không lặp 96 dòng/ngày
            f = rd / "ENSURE_TU_CHOI"
            try:
                cu = f.read_text(encoding="utf-8")
            except OSError:
                cu = ""
            if cu != msg:
                cay_git.ghi_log(rd, "ERROR" if h is None else "WARNING", msg)
                f.write_text(msg, encoding="utf-8")
            print(msg)
            return 1
        try:
            (rd / "ENSURE_TU_CHOI").unlink()
        except OSError:
            pass
    if h is not None:
        print(f"runner đang sống: pid {h['pid']} từ {h['ts']} (commit {str(h.get('commit'))[:12]}) — không mở thêm.")
        return 0
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else py)
    cmd = [exe, str(Path(__file__).resolve()), "--plan", str(args.plan), "--root", str(root), "run"]
    if args.dry_run:
        cmd.append("--dry-run")
    from mrunner.thuc import an_cua_so
    kw = an_cua_so()
    if os.name == "nt":
        # pythonw không có console; nếu phải rơi về python.exe thì console ẩn (CREATE_NO_WINDOW).
        kw["creationflags"] |= subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.BELOW_NORMAL_PRIORITY_CLASS
    p = subprocess.Popen(cmd, cwd=str(REPO), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, env={**os.environ, **hf_pin.BIEN}, **kw)
    print(f"khởi động runner pid {p.pid}")
    return 0


def lenh_status(args) -> int:
    plan = nap_plan(args.plan)
    root = Path(args.root)
    ex = dry_executors(plan) if args.dry_run else None
    if ex is None:
        from mrunner.thuc import DauVaoM1

        class _San:
            def __init__(self, dv): self.dv = dv
            def ready(self, t): return self.dv.wav(t) is not None
        dv = DauVaoM1(plan)
        ex = {"m1_hosted": _San(dv), "m1_local": _San(dv)}
    r = Runner(plan, root, ex)
    rows, s = r.status_rows()
    lock = Lock(runner_dir(plan, root) / "LOCK")
    h = lock.holder()
    pf = runner_dir(plan, root) / "PAUSE"
    pause = pf.exists()
    tt = ""
    if pause:
        tt = "   · PAUSE đang bật — runner CHƯA xác nhận (có thể đang giữa task)"
        try:
            ack = json.loads((runner_dir(plan, root) / "PAUSED_ACK").read_text(encoding="utf-8"))
            if h and ack["pid"] == h["pid"] and from_iso(ack["ts"]) >= pf.stat().st_mtime:
                tt = f"   · PAUSE đang bật — paused (runner xác nhận rảnh lúc {ack['ts']})"
        except Exception:
            pass
    print(f"bây giờ {to_iso(time.time())}")
    ck = f" · commit {str(h.get('commit'))[:12]}" if h else ""
    print(f"runner: {'SỐNG pid ' + str(h['pid']) + ' từ ' + h['ts'] if h else 'KHÔNG sống'}{ck}{tt}")
    print(f"USD cộng dồn: {s.spent_usd:.4f} / trần {plan['budget_usd']:.2f}"
          f"   · grounding theo ngày: {s.grounded_by_day or '{}'}"
          f"   · dòng hỏng bỏ qua: {s.bad_lines}")
    print(f"\n{'M':3} {'xong/tổng':>12} {'error':>6} {'missed':>7} {'budget_stop':>12} {'chờ đầu vào':>12}  mốc kế tiếp")
    for x in rows:
        mk = f"{x['moc_ke'][0]}  {x['moc_ke'][1]}" if x["moc_ke"] else "—"
        print(f"{x['m']:3} {x['xong']:>5}/{x['tong']:<6} {x['error']:>6} {x['missed']:>7} "
              f"{x['budget_stop']:>12} {x['cho_dau_vao']:>12}  {mk}")
    kt = r.khoang_trong(s, time.time())
    if kt:
        gan = " · ".join(f"{to_iso(a)} → {to_iso(b)} ({(b - a) / 3600:.1f} h)" for a, b in kt[-3:])
        print(f"\nCẢNH BÁO khoảng trống > 60 phút không bản ghi trong lúc có task đến hạn: {len(kt)} — gần nhất: {gan}")
    else:
        print("\nkhoảng trống > 60 phút có task đến hạn: 0")
    return 0


def _doi_chung(plan: dict, root: Path) -> dict:
    """Số đối chứng việc 132: task xong theo M (chỉ task còn trong plan), USD, lịch M3."""
    r = Runner(plan, root, {})
    s = r.snapshot()
    from collections import Counter
    xong = Counter(t["m"] for t in plan["tasks"] if t["id"] in s.done)
    return {"xong": dict(sorted(xong.items())), "usd": round(s.spent_usd, 6),
            "m3_lich": sorted({t["at"] for t in plan["tasks"] if t["m"] == "M3" and t.get("at")}),
            "tong": dict(sorted(Counter(t["m"] for t in plan["tasks"]).items()))}


def lenh_amend(args) -> int:
    from mrunner.core import Store
    from mrunner.kehoach import amend04
    if args.amend == "05b":
        # A05.7: chỉ THÊM repo vào hf_pin; repo đã ghim phải giữ nguyên từng byte.
        pf = Path(args.plan)
        plan = nap_plan(pf)
        cu = plan.get("hf_pin") or {}
        if any(hf_pin.PIN.get(r) != v for r, v in cu.items()):
            print("hf_pin trong mã ĐỔI một repo đã ghim — amend 05b chỉ cho thêm repo"); return 2
        them = sorted(set(hf_pin.PIN) - set(cu))
        if not them:
            print("không có repo mới"); return 2
        truoc = _doi_chung(plan, Path(args.root))
        moi = {**plan, "hf_pin": hf_pin.PIN,
               "amendment_05b": {"luc": to_iso(time.time()), "them": them,
                                 "prereg": "docs/benchmark/PREREG_M1-M4_20260916.md §A05.7"}}
        if _doi_chung(moi, Path(args.root)) != truoc or moi["tasks"] != plan["tasks"]:
            print("ĐỐI CHỨNG HỎNG — không ghi"); return 1
        tmp = pf.with_suffix(".amend05b.tmp")
        tmp.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pf)
        print(f"plan → A05b: thêm {them}; task/xong/USD/M3 không đổi")
        print(f"plan sha256 {hashlib.sha256(pf.read_bytes()).hexdigest()}")
        return 0
    if args.amend == "05":
        pf = Path(args.plan)
        plan = nap_plan(pf)
        if "hf_pin" in plan:
            print("plan đã có hf_pin"); return 2
        truoc = _doi_chung(plan, Path(args.root))
        moi = {**plan, "hf_pin": hf_pin.PIN,
               "amendment_05": {"luc": to_iso(time.time()),
                                "prereg": "docs/benchmark/PREREG_M1-M4_20260916.md §AMENDMENT 05"}}
        sau = _doi_chung(moi, Path(args.root))
        if truoc != sau or moi["tasks"] != plan["tasks"]:
            print("ĐỐI CHỨNG HỎNG — không ghi"); return 1
        tmp = pf.with_suffix(".amend05.tmp")
        tmp.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pf)
        ghim = ", ".join(r + "@" + v["revision"][:12] for r, v in hf_pin.PIN.items())
        print(f"plan → A05: hf_pin {ghim}; "
              f"task/xong/USD/M3 không đổi: {json.dumps(sau['xong'])}, {sau['usd']}")
        print(f"plan sha256 {hashlib.sha256(pf.read_bytes()).hexdigest()}")
        return 0
    if args.amend == "08":
        # A08: M6 có luật missed như M3. Chỉ đổi cờ khong_missed của task M6; xong/USD/lịch không đổi.
        from mrunner.kehoach import amend08
        pf = Path(args.plan)
        plan = nap_plan(pf)
        truoc = _doi_chung(plan, Path(args.root))
        try:
            moi = amend08(plan)
        except ValueError as e:
            print(e); return 2
        moi["amendment_08"]["luc"] = to_iso(time.time())
        doi = [a["id"] for a, b in zip(plan["tasks"], moi["tasks"]) if a != b]
        if (_doi_chung(moi, Path(args.root)) != truoc or len(doi) != sum(t["m"] == "M6" for t in plan["tasks"])
                or any(not i.startswith("M6|") for i in doi)):
            print("ĐỐI CHỨNG HỎNG — không ghi"); return 1
        tmp = pf.with_suffix(".amend08.tmp")
        tmp.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pf)
        print(f"plan → A08: {len(doi)} task M6 bỏ khong_missed (ngưỡng {moi['amendment_08']['m6_late_missed_s']:.0f} s); "
              f"task/xong/USD/M3 không đổi")
        print(f"plan sha256 {hashlib.sha256(pf.read_bytes()).hexdigest()}")
        return 0
    if args.amend != "04":
        print("chỉ có --amend 04 | 05 | 05b | 08"); return 2
    pf = Path(args.plan)
    plan = nap_plan(pf)
    root = Path(args.root)
    rd = runner_dir(plan, root)
    h = Lock(rd / "LOCK").holder()
    if h is not None:
        try:
            ack = json.loads((rd / "PAUSED_ACK").read_text(encoding="utf-8"))
            ok = (rd / "PAUSE").exists() and ack["pid"] == h["pid"] \
                and from_iso(ack["ts"]) >= (rd / "PAUSE").stat().st_mtime
        except Exception:
            ok = False
        if not ok:
            print("runner đang sống mà chưa xác nhận PAUSE — tạo PAUSE, chờ status báo paused rồi chạy lại.")
            return 3
    truoc = _doi_chung(plan, root)
    moi, huy = amend04(plan)
    goc_text = pf.read_text(encoding="utf-8")
    tmp = pf.with_suffix(".amend04.tmp")
    tmp.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, pf)
    sau = _doi_chung(moi, root)
    kept = {m: n for m, n in truoc["xong"].items()}
    if sau["xong"] != kept or sau["usd"] != truoc["usd"] or sau["m3_lich"] != truoc["m3_lich"]:
        pf.write_text(goc_text, encoding="utf-8")
        print("ĐỐI CHỨNG HỎNG — đã trả plan cũ.", json.dumps({"truoc": truoc, "sau": sau}, ensure_ascii=False))
        return 1
    st = Store(root / plan["results"]["M1"])
    co, _ = st.read()
    da_huy = {r["task_id"] for r in co if r.get("status") == "cancelled_amend04"}
    now = to_iso(time.time())
    n = 0
    for t in huy:
        if t["id"] not in da_huy:
            st.append({"task_id": t["id"], "m": "M1", "status": "cancelled_amend04", "ts": now,
                       "amendment": "docs/benchmark/PREREG_M1-M4_20260916.md §A04.1",
                       "wav": t["params"]["wav"]})
            n += 1
    print(f"plan → AMENDMENT 04: huỷ {len(huy)} task rv2 (ghi mới {n} dòng cancelled_amend04)")
    print(f"{'':12s} {'trước':>28s}   {'sau':>28s}")
    print(f"{'task xong':12s} {json.dumps(truoc['xong']):>28s}   {json.dumps(sau['xong']):>28s}")
    print(f"{'USD':12s} {truoc['usd']:>28.4f}   {sau['usd']:>28.4f}")
    print(f"{'mốc M3':12s} {len(truoc['m3_lich']):>22d} mốc   {len(sau['m3_lich']):>22d} mốc  (giống hệt: {truoc['m3_lich'] == sau['m3_lich']})")
    print(f"{'tổng task':12s} {json.dumps(truoc['tong']):>28s}   {json.dumps(sau['tong'])}")
    print(f"plan sha256 {hashlib.sha256(pf.read_bytes()).hexdigest()}")
    return 0


def lenh_status_log(args) -> int:
    """Việc 121: tác vụ Scheduler 09:05/21:05 chạy bằng pythonw (không cửa sổ ⇒ không stdout), nên bắt
    đầu ra của `status` trong tiến trình rồi NỐI vào `docs/benchmark/runner/status_log.md`.
    Kèm hai dòng cổng (cây sạch, LOCK commit == HEAD) để chủ nhân đọc một file thay vì hỏi."""
    import contextlib
    import io
    from mrunner import cay_git
    plan = nap_plan(args.plan)
    root = Path(args.root)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = lenh_status(args)
    except Exception as exc:                               # status hỏng cũng phải để lại dấu
        rc = 1
        buf.write(f"\nstatus LỖI: {type(exc).__name__}: {exc}\n")
    h = Lock(runner_dir(plan, root) / "LOCK").holder()
    hd, ban_ = cay_git.head(git_goc()), cay_git.ban(git_goc())
    cong = (f"cây phạm vi runner: {'sạch' if not ban_ else 'BẨN — ' + '; '.join(ban_[:5])} · "
            f"LOCK commit {str((h or {}).get('commit'))[:12]} {'==' if h and h.get('commit') == hd else '≠'} "
            f"HEAD {str(hd)[:12]}")
    f = runner_dir(plan, root) / "status_log.md"
    moi = not f.exists()
    with f.open("a", encoding="utf-8") as out:
        if moi:
            out.write("# status_log — ghi tự động 09:05 và 21:05 (việc 121)\n\n"
                      "Mỗi khối là nguyên văn `run_m_all.py status` lúc ấy + hai dòng cổng. Không sửa tay.\n")
        out.write(f"\n## {to_iso(time.time())}{'' if rc == 0 else '  ⚠ status rc=' + str(rc)}\n\n"
                  f"```\n{buf.getvalue().rstrip()}\n{cong}\n```\n")
    return rc


def lenh_plan(args) -> int:
    if getattr(args, "amend", None):
        return lenh_amend(args)
    if not (args.m3_first and args.free_per_day is not None and args.tier):
        print("plan mới cần --m3-first, --free-per-day, --tier (hoặc --amend 04)"); return 2
    from mrunner.kehoach import build
    out = Path(args.plan)
    if out.exists() and not args.force:
        print(f"{out} đã có. Plan sinh MỘT lần và commit; muốn sinh lại phải --force và ghi AMENDMENT.")
        return 1
    plan = build(datetime.fromisoformat(args.m3_first))
    plan["price"]["grounding_free_per_day"] = args.free_per_day
    plan["tier"] = args.tier
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"{out}: {len(plan['tasks'])} task", dict(Counter(t['m'] for t in plan['tasks'])))
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default=str(PLAN_MAC_DINH))
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--ensure", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="lenh")
    pr = sub.add_parser("run")
    pr.add_argument("--dry-run", action="store_true", dest="dry_run_sub")
    pr.add_argument("--max-steps", type=int, default=None)
    pr.add_argument("--stop-when-idle", action="store_true")
    pp = sub.add_parser("plan")
    pp.add_argument("--m3-first")
    pp.add_argument("--free-per-day", type=int)
    pp.add_argument("--tier", choices=["free", "paid"])
    pp.add_argument("--force", action="store_true")
    pp.add_argument("--amend", help="sửa plan đang chạy theo amendment (hiện có: 04, 05, 05b, 08)")
    sub.add_parser("status")
    sub.add_parser("status-log")
    sub.add_parser("doctor")
    args = ap.parse_args()
    if getattr(args, "dry_run_sub", False):
        args.dry_run = True
    if args.ensure:
        return lenh_ensure(args)
    if args.lenh == "run":
        return lenh_run(args)
    if args.lenh == "plan":
        return lenh_plan(args)
    if args.lenh == "status":
        return lenh_status(args)
    if args.lenh == "status-log":
        return lenh_status_log(args)
    if args.lenh == "doctor":
        from mrunner.doctor import doctor
        return doctor(nap_plan(args.plan) if Path(args.plan).exists() else None)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
