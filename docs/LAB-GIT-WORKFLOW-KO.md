# 연구실 GitHub 연결과 일상 작업

저장소: https://github.com/jungmin5589-del/hongik-carla-hmi

Git은 파일의 변경 기록, GitHub는 그 기록을 주고받는 보관 장소입니다.
**Pull = 다른 PC의 변경을 가져오기 / Commit = 내 변경을 기록 / Push = GitHub에 보내기.**
CARLA 엔진·Python·지도 원본·음성·음악까지 다시 내려받는 작업은 아닙니다.
공개 저장소이지만 Push에는 쓰기 권한이 있는 본인 GitHub 계정이 필요합니다.

## 처음 한 번: 설치와 로그인

1. 연구실 PC에 [Git for Windows](https://git-scm.com/install/windows)를 설치합니다.
   설치 옵션에서 명령줄 PATH와 기본 Git Credential Manager를 유지합니다.
   설치 후 터미널이나 BAT 창을 새로 열어야 합니다.
2. 버튼으로 작업하려면 [GitHub Desktop](https://desktop.github.com/download/)도 설치합니다.
   `File → Options → Accounts`에서 본인 계정으로 로그인합니다.
   저장소 소유자는 `jungmin5589-del`입니다. 팀원은 자신의 쓰기 권한 계정을 씁니다.
   브라우저에 다른 계정이 로그인돼 있으면 인증할 계정을 확인합니다.
3. 공용 PC에서는 개인별 Windows 계정을 권장합니다. 계정 비밀번호나 토큰을
   프로젝트 파일에 저장하지 않습니다. Git 작성자 이름·이메일 설정은 로그인과 다릅니다.

## ZIP으로 전달한 기존 폴더를 연결하기

지금 연구실의 `live`는 ZIP에서 꺼낸 폴더라 `.git`이 없을 수 있습니다.
그 상태에서는 Pull/Push가 안 됩니다. **잘 작동한 WebSocket 수정분부터 보존합니다.**

다운로드한 Git 연결 ZIP을 아래처럼 배치합니다. 바깥 폴더 이름과 드라이브 문자는 달라도 됩니다.

```text
Hongik-CARLA-Lab-20261107/
  live/                       ← 연구실에서 실제 사용하는 폴더
  python/python.exe
  SOURCE-MANIFEST.json         ← 원래 전달한 파일 그대로 유지
  Git-Setup/
    58_GIT_LAB_SETUP.bat
    lab_git_setup.py
    LAB-GIT-WORKFLOW-KO.md
```

1. 주행 앱을 종료하고, 편집 중인 코드를 저장합니다.
2. `Git-Setup/58_GIT_LAB_SETUP.bat`를 실행합니다.
3. `connected`와 `codex/lab-integration`이 나오면 연결된 것입니다.
   기존 Git 저장소라면 `already-configured`로 현재 브랜치만 확인합니다.
4. GitHub Desktop에서 `File → Add local repository`로 **위의 live**를 선택합니다.
   `Create repository`나 기존 폴더 위에 `Clone repository`를 실행하지 않습니다.

도구는 원본 manifest의 **전체 파일 목록·SHA256**과 GitHub 기록을 비교해 정확한
전달 버전을 찾습니다. Git 기록과 인덱스만 연결하고 작업 파일을 체크아웃하지 않습니다.
현재 WebSocket 코드·로컬 설정·음성·인증서·실행 자산은 그대로 남습니다.
전달 버전이나 `.gitignore`가 맞지 않으면 덮어쓰지 않고 중단합니다.
중간 Git 기록은 같은 상위 폴더의 `git-setup-history-*`에 보관됩니다.
이 백업은 Git 기록 보관용이며 아직 Commit하지 않은 현장 수정분의 백업은 아닙니다.

`SOURCE-MANIFEST.json`이 없거나 새로 생성해버렸다면 임의로 `git init`하지 말고,
원래 받은 ZIP의 manifest와 현재 코드를 확인해야 합니다.
`SETUP STOPPED`가 나오면 강제 초기화 대신 출력 내용으로 버전을 확인합니다.

## 첫 Push: 연구실에서 성공한 코드 보존

최초 연결 직후에는 **Pull부터 누르지 않습니다.** 먼저 현장 수정분을 올립니다.

GitHub Desktop의 Changes에서 변경 파일과 내용을 읽고, 공유할 소스만 선택합니다.
음성·모델·영상·Python·인증서·`lab.local.json`·QR/연결 코드는 제외합니다.
기본 `.gitignore`가 이런 파일을 제외하지만 변경 목록도 직접 확인합니다.

터미널을 `live`에서 열어, 작성자 정보를 해당 저장소에만 설정합니다.
아래 이름·이메일은 본인의 것으로 바꿉니다. GitHub `Settings → Emails`의
비공개 커밋용 주소를 써도 됩니다. 다른 사람 계정의 주소를 복사하지 않습니다.

```powershell
git config user.name "본인 이름"
git config user.email "본인의 GitHub 커밋 이메일"
```

예를 들어 `native_carla.py`만 연구실에서 바꿨다면 다음과 같습니다.
다른 파일도 바꿨다면 실제 변경 파일명을 확인해 따로 추가합니다.

```powershell
git status --short
git diff -- native_carla.py
git add -- native_carla.py
..\python\python.exe repo_safety.py
git commit -m "Preserve working lab WebSocket integration"
git push -u origin codex/lab-integration
```

검사가 실패하면 원인을 수정한 뒤 Commit합니다. 변경이 없다면 빈 Commit은 필요 없습니다.
첫 HTTPS Push 때 Git Credential Manager의 브라우저 로그인 창이 뜰 수 있습니다.
본인 계정으로 인증합니다. **계정 비밀번호를 Git 명령에 붙여 넣지 않습니다.**
첫 Commit은 위 터미널 절차로 검사까지 진행하는 것이 확실합니다.
그 뒤 Desktop의 Publish branch/Push origin으로 전송해도 됩니다.

이 브랜치의 현장 WebSocket 변경과 최신 `main`의 정렬 수정을 비교해 합칩니다.
첫 통합 전에는 `main`을 강제로 덮어쓰거나 `Reset`, `Discard changes`,
`git clean`을 실행하지 않습니다. 현장 수정분이 GitHub에 올라온 뒤 통합을 검토합니다.

## 통합 이후 매번 하는 순서

**시작 전 Pull → 작업 → 변경 확인 → 검사 → Commit → Push.**

`main`은 실행 가능한 기준 버전으로 유지하고, 연구실 변경은 별도 브랜치로 올립니다.
작업 중인 파일이 있다면 먼저 해당 작업 브랜치에 Commit/Push하고 브랜치를 바꿉니다.

```powershell
# 현장 WebSocket 코드가 main에 합쳐진 뒤, 변경사항이 없는 상태에서
git switch main
git pull --ff-only origin main
git switch -c codex/lab-20261110
```

이후 수정 → 실제 실행 확인 → 바뀐 소스만 `git add -- 파일명` →
`..\python\python.exe repo_safety.py` → Commit →
`git push -u origin codex/lab-20261110` 순서입니다. 브랜치 날짜는 작업일로 바꿉니다.
이후에는 그 작업 브랜치에서 `git push`만 해도 됩니다.
GitHub에서 Pull request로 변경을 검토해 `main`에 합칩니다.
집 PC도 최신 `main`을 Pull하면 연구실 수정분을 받을 수 있습니다.

Desktop에서는 Current branch 확인 → Fetch origin → Pull origin → 수정 →
Changes 확인 → 검사 → Commit → Push origin 순서입니다.
검사는 터미널에서 검토한 파일만 `git add -- 파일명`으로 올린 뒤
`repo_safety.py`를 실행합니다. Desktop 체크박스만 선택한 상태에서는
Git 인덱스에 반영되지 않아 검사 대상이 비어 있을 수 있습니다.
실제 Commit할 파일도 검사한 목록과 같게 유지합니다.
같은 파일을 양쪽 PC에서 동시에 수정하면 충돌할 수 있으므로 먼저 Pull하고 시작합니다.

## 설정과 실행에서 주의할 차이

- 공유하는 것: 시나리오 소스, 내비 UI, 일반 설정값, 실행 BAT, 문서.
- 각 PC에 남기는 것: CARLA/Python 설치, 지도·NuRec 모델, 음성·음악,
  연구실 IP/장치 주소, 인증서·개인키, 모바일 페어링, 실험 기록.
- Push가 거절되면 원격 주소·로그인 계정·쓰기 권한을 확인합니다.
  공개 열람 권한만 있는 계정은 Push할 수 없습니다.
- Pull이 `Not possible to fast-forward`로 멈추면 두 PC 기록이 갈라진 것입니다.
  강제 Push/Reset 대신 현장 브랜치를 먼저 보존한 뒤 Merge를 검토합니다.
- 새 PC에 코드만 Clone하면 실행 자산까지 생기지는 않습니다.
  최초 실행 환경은 기존 연구실 배포 폴더가 필요합니다.
- Wi-Fi가 바뀌면 모바일 QR/IP는 다시 확인해야 합니다. Git 설정과는 별개입니다.

## 검증 범위

로컬 임시 Git 저장소에서 기존 파일 보존, 정확한 원본 버전 탐색,
로컬 자산 제외, 재실행 시 기존 Git 보존, 불일치 시 중단을 확인했습니다.
원래 전달한 두 manifest도 실제 저장소 이력과 대조했습니다.
연구실 PC의 Git 설치·본인 계정 인증·첫 Push는 현장에서 진행해야 합니다.
이 문서는 그 PC의 WebSocket 변경을 이미 가져왔다는 의미가 아닙니다.

공식 참고: [Windows Git 설치](https://git-scm.com/install/windows),
[GitHub 인증 저장](https://docs.github.com/en/get-started/git-basics/caching-your-github-credentials-in-git?platform=windows),
[Git Pull](https://git-scm.com/docs/git-pull).
