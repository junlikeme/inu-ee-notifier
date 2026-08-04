#!/usr/bin/env python3
"""로컬 실행용 토큰 설정. 토큰을 .env.local(git 제외, 본인만 읽기 가능)에 저장한다.

사용법: python3 setup_local_token.py → 토큰 붙여넣기 → 엔터
"""

import getpass
import json
import os
import urllib.request
from pathlib import Path

CHAT_ID = "5303045780"
ENV_FILE = Path(__file__).parent / ".env.local"

token = getpass.getpass("봇 토큰 붙여넣기 (화면에 안 보임): ").strip()

# 토큰이 유효한지 즉시 확인
try:
    with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getMe", timeout=15
    ) as resp:
        info = json.load(resp)
    bot_name = info["result"]["username"]
except Exception:
    raise SystemExit("토큰이 올바르지 않습니다. BotFather에서 /token 으로 다시 확인하세요.")

ENV_FILE.write_text(
    f'TELEGRAM_BOT_TOKEN="{token}"\nTELEGRAM_CHAT_ID="{CHAT_ID}"\n', encoding="utf-8"
)
os.chmod(ENV_FILE, 0o600)
print(f"확인 완료: @{bot_name} — {ENV_FILE.name} 저장됨")
