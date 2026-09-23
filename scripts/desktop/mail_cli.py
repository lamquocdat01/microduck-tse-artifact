r"""Soi cache mail bằng mắt, so với Gmail web TRƯỚC khi nối vịt (docs/ADR-014).

    python scripts\mail_cli.py sync                    # đồng bộ một lần (đã chạy mail_login.py)
    python scripts\mail_cli.py sync --fixture          # nạp hộp thư GIẢ của test vào --db
    python scripts\mail_cli.py today
    python scripts\mail_cli.py unread
    python scripts\mail_cli.py search "review OR decision" --days 7 --editorial
    python scripts\mail_cli.py get <id>
    python scripts\mail_cli.py retag                   # tính lại cờ editorial sau khi sửa YAML
    python scripts\mail_cli.py why <id>                # luật editorial nào quyết cho mail này

Đọc ĐÚNG hàm mà tool của vịt đọc (`MailStore.query` / `.get`): thấy gì ở đây là vịt thấy nấy.
Chỉ in ra terminal, không ghi file log nào.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, enable_utf8_console  # noqa: E402
from mail.editorial import EditorialRules  # noqa: E402
from mail.store import MailStore  # noqa: E402
from mail.sync import MailSync  # noqa: E402
from mail.timerange import resolve_range  # noqa: E402


def _print_result(result: dict, full: bool) -> None:
    ago = result.get("synced_minutes_ago")
    print(f"{result['count']} mail{' (đã cắt bớt)' if result['truncated'] else ''} · "
          f"đồng bộ lúc {result.get('synced_at') or 'CHƯA BAO GIỜ'}"
          + (f" ({ago} phút trước)" if ago is not None else "")
          + (f" · LỖI ĐỒNG BỘ: {result['sync_error']}" if result.get("sync_error") else ""))
    for item in result["items"]:
        flag = "E" if item["editorial"] else " "
        print(f"\n[{flag}] {item['ts_local']}  {item['id']}\n    {item['from']}\n    {item['subject']}")
        print(f"    {item['snippet'][:160]}")
        if full and item.get("body_text"):
            print("    ---\n    " + item["body_text"].replace("\n", "\n    "))


def main(argv: list[str] | None = None) -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=None, help="file SQLite (mặc định desktop/.cache/mail.sqlite)")
    parser.add_argument("--now", default=None, help="giờ giả ISO có múi giờ (để test lặp lại được)")
    parser.add_argument("--full", action="store_true", help="in cả body (5 mail đầu, ≤ 1,5 KB)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sync_p = sub.add_parser("sync")
    sync_p.add_argument("--fixture", action="store_true", help="dùng hộp thư GIẢ tests/fixtures/mail/inbox.json")
    sub.add_parser("today")
    sub.add_parser("unread")
    search = sub.add_parser("search")
    search.add_argument("q")
    search.add_argument("--days", type=int, default=None)
    search.add_argument("--editorial", action="store_true")
    search.add_argument("--from", dest="sender", default=None)
    get = sub.add_parser("get")
    get.add_argument("id")
    sub.add_parser("retag")
    why = sub.add_parser("why")
    why.add_argument("id")
    args = parser.parse_args(argv)

    cfg = Config.load()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    store = MailStore(args.db or cfg.mail_db, cfg.mail_tz)
    rules = EditorialRules.load(cfg.mail_rules)

    if args.cmd == "sync":
        if args.fixture:
            from mail.fake import FakeGmail

            fake = FakeGmail.from_fixture(now=now)
            result = MailSync(store, lambda: fake, rules, days=cfg.mail_sync_days, tz_name=cfg.mail_tz,
                              clock=lambda: now).sync_once()
        else:
            from mail.auth import build_client
            from mrunner.gate import check

            if reason := check("mail_cli sync", minutes=5):   # CLAUDE.md: không đè mẻ đo
                print(reason)
                return 4
            result = MailSync(store, lambda: build_client(cfg.mail_token), rules, days=cfg.mail_sync_days,
                              tz_name=cfg.mail_tz).sync_once()
        print(result)
        return 0 if result.get("ok") else 1

    if args.cmd == "today":
        start, end = resolve_range("today", now, cfg.mail_tz)
        _print_result(store.query(start=start, end=end, limit=20, full=args.full, now=now), args.full)
    elif args.cmd == "unread":
        _print_result(store.query(unread_only=True, limit=20, full=args.full, now=now), args.full)
    elif args.cmd == "search":
        start = None
        if args.days is not None:
            day = (now.astimezone(ZoneInfo(cfg.mail_tz)) - timedelta(days=args.days)).date()
            start, _ = resolve_range(f"since:{day.isoformat()}", now, cfg.mail_tz)
        _print_result(store.query(start=start, topic=args.q, sender=args.sender, editorial_only=args.editorial,
                                  limit=20, full=args.full, now=now), args.full)
    elif args.cmd == "get":
        mail = store.get(args.id)
        if mail is None:
            print(f"Không có mail {args.id} trong cache.")
            return 1
        print(f"{mail['ts_local']}\nTừ: {mail['from']}\nTới: {mail['to']}\nTiêu đề: {mail['subject']}"
              f"\nĐính kèm: {'có' if mail['has_attachments'] else 'không'}\n---\n{mail['body_text']}")
    elif args.cmd == "retag":
        print(f"Đổi cờ editorial: {store.retag(rules)} mail")
    elif args.cmd == "why":
        row = store.conn().execute("SELECT from_addr, subject, body_text FROM messages WHERE id = ?",
                                   (args.id,)).fetchone()
        if row is None:
            print(f"Không có mail {args.id} trong cache.")
            return 1
        flag, reason = rules.decide(from_addr=row["from_addr"] or "", subject=row["subject"] or "",
                                    body=row["body_text"] or "")
        print(f"editorial={flag}  luật: {reason or '(không luật nào khớp)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
