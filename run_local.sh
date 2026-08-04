#!/bin/bash
# 로컬(Mac) 5분 간격 실행용. launchd가 호출한다.
# GitHub Actions와 state.json을 공유하므로 실행 전 pull, 변경 시 push.
set -u
cd "$(dirname "$0")" || exit 1

export PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"

if [ ! -f .env.local ]; then
    echo "$(date '+%F %T') .env.local 없음 — setup_local_token.py 를 먼저 실행하세요"
    exit 0
fi
# shellcheck disable=SC1091
source .env.local
export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

git pull --rebase -q origin main 2>/dev/null

echo "$(date '+%F %T') 확인 시작"
/usr/bin/python3 check_boards.py || exit 1

if [ -n "$(git status --porcelain state.json)" ]; then
    git add state.json
    git commit -q -m "update state (local)"
    git push -q origin main 2>/dev/null || {
        git pull --rebase -q origin main && git push -q origin main
    }
fi
