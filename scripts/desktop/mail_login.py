r"""Đăng nhập Gmail MỘT LẦN — scope duy nhất gmail.readonly (docs/ADR-014).

    python scripts\mail_login.py
    python scripts\mail_login.py --no-browser      # in link, tự mở trình duyệt

Chuẩn bị (một lần, trên console.cloud.google.com, bằng chính tài khoản Gmail sẽ đọc):
  1. Tạo project -> APIs & Services -> bật "Gmail API".
  2. OAuth consent screen: External, trạng thái Testing, thêm chính mình vào Test users.
  3. Credentials -> Create OAuth client ID -> loại "Desktop app".
  4. Chép Client ID / Client secret vào ..\.env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET.

Token lưu ở desktop\.secrets\gmail_token.json — thư mục bị gitignore, và test_m11_mail
kiểm rằng không file nào ở đó được git theo dõi.

BẪY: app để ở trạng thái Testing thì refresh token HẾT HẠN SAU 7 NGÀY. Khi đó đồng bộ nền
ghi `status=auth`, vịt nói dữ liệu cũ tới lúc nào; chạy lại script này.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, enable_utf8_console  # noqa: E402
from mail import auth  # noqa: E402


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-browser", action="store_true", help="không tự mở trình duyệt")
    args = parser.parse_args()

    cfg = Config.load()
    if not cfg.gmail_client_id or not cfg.gmail_client_secret:
        print("Thiếu GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET trong ..\\.env — xem hướng dẫn đầu file này.")
        return 1

    print(f"Scope xin cấp: {auth.SCOPE}  (chỉ đọc, không gửi/sửa/xoá được)")
    creds = auth.login(cfg.gmail_client_id, cfg.gmail_client_secret, cfg.mail_token,
                       open_browser=not args.no_browser)
    print(f"Đã lưu token: {cfg.mail_token}")
    print(f"Scope đã cấp: {' '.join(creds.scopes or [])}")

    profile = auth.build_client(cfg.mail_token).profile()
    print(f"Tài khoản: {profile.get('emailAddress')} · {profile.get('messagesTotal')} mail")
    print("\nTiếp theo: python scripts\\mail_cli.py sync   rồi   python scripts\\mail_cli.py today")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
