# INU 전자공학부 게시판 알리미

인천대학교 전자공학부 홈페이지 게시판에 새 글이 올라오면 텔레그램으로 즉시 알림을 보내는 시스템.
GitHub Actions에서 5분마다 자동 실행되며, 로그인·비밀번호가 필요 없다.

## 감시 대상

| 게시판 | 데이터 소스 | 비고 |
|---|---|---|
| 공지사항 | 메인 페이지 위젯 (최신 8개) | 글 본문은 학교 로그인 필요 |
| 장학게시판 | 메인 페이지 위젯 (최신 8개) | 글 본문은 학교 로그인 필요 |
| 학과NEWS | subview 3377 | 전체 공개 |
| 홍보/취업 게시판 | subview 3379 | 전체 공개 |
| 대학원공지 | subview 3372 | — |

## 동작 방식

1. 5분마다 `check_boards.py`가 게시판 목록을 읽는다 (HTTP 요청 4번).
2. `state.json`에 저장된 "본 글 번호"와 비교해 새 글만 골라낸다.
3. 새 글은 텔레그램 봇으로 제목·날짜·링크를 전송한다.
4. 갱신된 `state.json`을 저장(커밋)해 중복 알림을 막는다.

- 첫 실행 때는 기존 글을 등록만 하고 알림을 보내지 않는다.
- 학교 서버가 일시적으로 응답하지 않으면 그 회차는 건너뛰고 다음 회차에 재시도한다.
- GitHub Actions 스케줄 특성상 실제 알림까지 5~15분 지연될 수 있다.

## 설정 방법

### 1. 텔레그램 봇 만들기 (폰에서, 약 2분)

1. 텔레그램에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력 → 봇 이름(아무거나) → 봇 아이디(`..._bot`으로 끝나야 함) 입력
3. BotFather가 주는 **토큰**(예: `1234567:AAE...`) 복사해두기
4. 방금 만든 봇을 검색해 들어가서 **아무 메시지나 하나 보내기** (`/start` 등)

### 2. chat ID 확인 (컴퓨터에서)

```bash
python3 get_chat_id.py
```

토큰을 붙여넣으면 chat ID(숫자)가 출력된다.

### 3. GitHub 리포지토리 + Secrets 등록

```bash
gh repo create inu-ee-notifier --public --source . --push
gh secret set TELEGRAM_BOT_TOKEN   # 프롬프트에 토큰 붙여넣기
gh secret set TELEGRAM_CHAT_ID    # 프롬프트에 chat ID 입력
```

### 4. 첫 실행 테스트

```bash
gh workflow run watch-boards
gh run watch
```

첫 실행은 "등록만" 하므로 알림이 오지 않는 게 정상. 이후 새 글이 올라오면 알림이 온다.

## 로컬 테스트

```bash
python3 check_boards.py --dry-run
```

토큰 없이 실행되며, 보낼 알림 내용을 화면에 출력만 한다.

## Mac 로컬 병행 실행 (5분 간격)

GitHub Actions 무료 스케줄러는 실제로 1~3시간 간격으로만 실행되는 경우가 많다.
그래서 Mac이 켜져 있는 동안은 launchd로 정확히 5분마다 병행 실행한다.

- 실행 사본 위치: `~/.inu-ee-notifier` (원본은 `Documents/Codex/inu-ee-notifier`)
- **`~/Documents` 아래에서 직접 돌리면 안 된다.** macOS 보안(TCC)이 launchd의 Documents 접근을
  차단해 `Operation not permitted`(exit 126)로 실패한다.
- 토큰은 `.env.local`(권한 600, git 제외)에 저장. `setup_local_token.py`로 생성.
- 로그: `~/.inu-ee-notifier/local_run.log`

설치:

```bash
git clone https://github.com/junlikeme/inu-ee-notifier.git ~/.inu-ee-notifier
cd ~/.inu-ee-notifier && python3 setup_local_token.py
cp com.junhyuk.inu-ee-notifier.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.junhyuk.inu-ee-notifier.plist
```

plist를 수정했다면 `launchctl bootout gui/$(id -u)/com.junhyuk.inu-ee-notifier`로 먼저 내린 뒤
다시 복사·bootstrap 해야 반영된다. 상태 확인:

```bash
launchctl print gui/$(id -u)/com.junhyuk.inu-ee-notifier | grep -E "state|last exit"
```

## 주의

- GitHub는 60일간 리포지토리에 활동이 없으면 스케줄 실행을 자동 중지한다.
  (새 글이 올라올 때마다 state 커밋이 생기므로 보통은 문제없지만, 방학 등으로 오래 조용하면
  깃허브에서 온 "workflow disabled" 메일을 확인하고 Actions 탭에서 다시 켜면 된다.)
- 홈페이지 HTML 구조가 바뀌면 파싱이 실패할 수 있다. Actions 로그에 "글을 찾지 못함" 경고가
  계속 찍히면 파싱 정규식을 손봐야 한다.
