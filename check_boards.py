#!/usr/bin/env python3
"""인천대 전자공학부 홈페이지 게시판 새 글 감지 → 텔레그램 알림.

로그인 불필요. 데이터 소스:
  - 메인 페이지(index.do) 위젯: 공지사항(367), 장학게시판(901) — 목록 페이지가 로그인 필요라 위젯 사용
  - subview 페이지: 학과NEWS(3377→368), 홍보/취업(3379→909), 대학원공지(3372→914)

상태 파일 state.json 에 "본 글 번호"를 저장하고, 처음 보는 글만 알림.
게시판이 처음 등장하면(첫 실행) 알림 없이 등록만 한다.
"""

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "https://ee.inu.ac.kr"
MAIN_URL = f"{BASE}/electron/index.do"
STATE_FILE = Path(__file__).parent / "state.json"
KEEP_PER_BOARD = 300  # state에 보관할 글 번호 수 (게시판당)

# 메인 페이지 위젯에서 읽는 게시판: fnct 번호 → 이름
MAIN_PAGE_BOARDS = {
    "367": "공지사항",
    "901": "장학게시판",
}

# subview 페이지에서 읽는 게시판: 메뉴 번호 → 이름
SUBVIEW_BOARDS = {
    "3377": "학과NEWS",
    "3379": "홍보/취업",
    "3372": "대학원공지",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fetch(url: str, opener) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def parse_main_page(page: str) -> dict:
    """메인 페이지 위젯에서 게시판별 글 목록 추출. {fnct: [(seq, title, date), ...]}"""
    out = {fnct: [] for fnct in MAIN_PAGE_BOARDS}
    seen = set()
    pattern = re.compile(
        r'href="/bbs/electron/(\d+)/(\d+)/artclView\.do[^"]*"[^>]*>(.*?)</a>', re.S
    )
    for fnct, seq, inner in pattern.findall(page):
        if fnct not in out or (fnct, seq) in seen:
            continue
        seen.add((fnct, seq))
        m = re.search(r'subjectText"[^>]*>\s*<span>(.*?)</span>', inner, re.S)
        title = clean(m.group(1)) if m else clean(inner)[:80]
        # 게시일은 dateA 클래스에 있음 (본문 미리보기 속 날짜와 혼동 방지)
        d = re.search(r'class="dateA"[^>]*>\s*(\d{4}\.\d{2}\.\d{2})', inner)
        out[fnct].append((seq, title, d.group(1) if d else ""))
    return out


def parse_subview(page: str) -> list:
    """subview 게시판 목록에서 글 추출. [(fnct, seq, title, date), ...]

    표 형태(board_normal)와 웹진 형태(board_webzine) 모두 앵커에
    data-fnct-no / data-bbs-artcl-seq 속성을 쓰므로 앵커 단위로 순회하고,
    날짜는 앵커 다음에 나오는 첫 날짜 문자열을 쓴다.
    """
    rows = []
    seen = set()
    pattern = re.compile(
        r'data-fnct-no="(\d+)" data-bbs-artcl-seq="(\d+)">(.*?)</a>', re.S
    )
    for m in pattern.finditer(page):
        fnct, seq, inner = m.groups()
        if (fnct, seq) in seen:
            continue
        seen.add((fnct, seq))
        title = re.sub(r"^(새글|NO\.\d+)\s*", "", clean(inner))
        title = re.sub(r"\s*(새글|새 글)$", "", title)
        d = re.search(r"\d{4}\.\d{2}\.\d{2}", page[m.end():m.end() + 600])
        rows.append((fnct, seq, title, d.group(0) if d else ""))
    return rows


def article_url(fnct: str, seq: str) -> str:
    return f"{BASE}/bbs/electron/{fnct}/{seq}/artclView.do?layout=unknown"


def send_telegram(token: str, chat_id: str, text: str) -> None:
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        # 텔레그램은 오류 원인을 JSON body로 알려준다 (예: chat not found)
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"텔레그램 전송 실패 {e.code}: {body}") from None


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not dry_run and not (token and chat_id):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다. --dry-run 으로 실행하세요.")
        return 1

    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar())
    )

    # 게시판별 수집: {fnct: {"name": ..., "posts": [(seq, title, date), ...]}}
    boards = {}
    errors = []

    try:
        page = fetch(MAIN_URL, opener)
        for fnct, posts in parse_main_page(page).items():
            if posts:
                boards[fnct] = {"name": MAIN_PAGE_BOARDS[fnct], "posts": posts}
            else:
                errors.append(f"메인 페이지에서 {MAIN_PAGE_BOARDS[fnct]}(fnct {fnct}) 글을 찾지 못함")
    except Exception as e:
        errors.append(f"메인 페이지 로드 실패: {e}")

    for menu, name in SUBVIEW_BOARDS.items():
        try:
            page = fetch(f"{BASE}/electron/{menu}/subview.do", opener)
            rows = parse_subview(page)
            if rows:
                fnct = rows[0][0]
                boards[fnct] = {
                    "name": name,
                    "posts": [(seq, title, date) for _, seq, title, date in rows],
                }
            else:
                errors.append(f"{name}(menu {menu}) 글을 찾지 못함")
        except Exception as e:
            errors.append(f"{name}(menu {menu}) 로드 실패: {e}")

    for msg in errors:
        print(f"경고: {msg}", file=sys.stderr)
    if not boards:
        print("모든 게시판 수집 실패", file=sys.stderr)
        return 1

    notified = 0
    for fnct, info in boards.items():
        posts = info["posts"]
        known = state.get(fnct)
        if known is None:
            # 첫 실행: 현재 글들을 등록만 하고 알림은 보내지 않음
            state[fnct] = [seq for seq, _, _ in posts]
            print(f"{info['name']}: 첫 실행, {len(posts)}개 글 등록 (알림 없음)")
            continue

        new_posts = [(s, t, d) for s, t, d in posts if s not in known]
        for seq, title, date in reversed(new_posts):  # 오래된 새 글부터 순서대로
            line_date = f"\n🗓 {date}" if date else ""
            text = (
                f"🔔 <b>[{info['name']}] 새 글</b>\n"
                f"{html.escape(title)}{line_date}\n"
                f"{article_url(fnct, seq)}"
            )
            if dry_run:
                print(f"--- DRY RUN 알림 ---\n{text}\n")
            else:
                send_telegram(token, chat_id, text)
            notified += 1

        merged = [seq for seq, _, _ in posts] + [s for s in known if s]
        deduped = list(dict.fromkeys(merged))
        state[fnct] = deduped[:KEEP_PER_BOARD]

    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"완료: 게시판 {len(boards)}개 확인, 새 글 알림 {notified}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
