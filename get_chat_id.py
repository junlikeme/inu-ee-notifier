#!/usr/bin/env python3
"""텔레그램 chat ID 확인용 헬퍼.

사용법:
  1. 봇에게 아무 메시지나 하나 보낸다 (텔레그램 앱에서)
  2. python3 get_chat_id.py 실행 → 토큰 입력 → chat ID 출력
토큰은 화면에 표시되지 않고 어디에도 저장되지 않는다.
"""

import getpass
import json
import urllib.request

token = getpass.getpass("봇 토큰 붙여넣기 (화면에 안 보임): ").strip()
with urllib.request.urlopen(
    f"https://api.telegram.org/bot{token}/getUpdates", timeout=15
) as resp:
    data = json.load(resp)

chats = {}
for upd in data.get("result", []):
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat", {})
    if "id" in chat:
        name = chat.get("first_name") or chat.get("title") or ""
        chats[chat["id"]] = name

if not chats:
    print("메시지를 찾지 못했습니다. 봇에게 먼저 메시지를 보낸 뒤 다시 실행하세요.")
else:
    for cid, name in chats.items():
        print(f"chat ID: {cid}  ({name})")
