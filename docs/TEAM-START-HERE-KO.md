# 홍익이 주행 실험 · 팀원 사용 안내

2026-11-22 배포 기준. 기존 Three.js 내비게이션과 CARLA 주행을 연결한 승객 상호작용 연구용 앱입니다. **실험 운영은 CARLA, 실사 배경 비교는 NuRec 개발 옵션**으로 구분합니다. GitHub는 코드·공통 설정, Drive는 업데이트 ZIP·음성·기본 실행본을 전달합니다.

## 받을 곳

- [최신 코드 · 공유 브랜치](https://github.com/jungmin5589-del/hongik-carla-hmi/tree/codex/portable-motion-20261111)
- [Google Drive · 실행본과 최신 업데이트](https://drive.google.com/drive/folders/1W-h_GiLCqybHn4jzeNg_gRI3eTw0wFz2)
- [이번 최신 업데이트 ZIP 직접 받기](https://drive.google.com/file/d/1SXdvhYvtkOcuSA5Tbausj3Lju7_5hIK1/view?usp=drivesdk)
- ZIP을 풀면 **00_팀원_사용안내.html**부터 엽니다. 브라우저로 읽을 수 있습니다.
- 최신 업데이트는 **Hongik-Experiment-Update-20261122.zip**입니다. 기존 실행본에 적용하는 파일이며 엔진이 들어 있는 완전 설치본은 아닙니다.
- GitHub는 공개 열람 가능합니다. Drive는 공유받은 Google 계정으로 접속합니다. 권한이 없으면 소유자에게 접근 요청을 보냅니다.

## 기존 설치가 있다면 · 업데이트 후 실행

1. 주행·내비 앱을 정상 종료하고 현장 수정분을 저장합니다. 연구실에서 잘 작동한 WebSocket 코드는 먼저 커밋하거나 별도 백업합니다.
2. 최신 ZIP을 받아 **기존 실행본과 다른 폴더**에 압축을 풉니다.
3. 기존 **Hongik-CARLA-Lab-20261107 폴더 전체**를 ZIP 안의 **APPLY_TEAM_UPDATE.bat** 위로 끌어 놓습니다. live 폴더나 BAT 하나만 옮기지 않습니다.
4. 해시 검사·파일 백업·설치 후 검사 완료를 확인합니다. 교체 전 파일은 update-backups에 남습니다. PC별 설정·기록·인증서·페어링은 교체하지 않습니다.
5. 대상 실행본의 **live/64_START_EXPERIMENT.bat**로 실험을 시작합니다. 이 실행의 모션 출력은 OFF입니다.

최신 앱 소스·공통 설정·한국어/영어/중국어 응답 음성과 기존 배포 이후 필요한 보조 파일을 함께 전달합니다. 과거 업데이트를 나중에 적용하면 코드가 과거로 돌아갈 수 있으므로 이번 업데이트를 마지막에 적용합니다.

## 새 PC에 처음 설치한다면

Drive 폴더에서 아래 파일을 받습니다.

| 파일 | 역할 |
| --- | --- |
| [Hongik-CARLA-Lab-20261107-App-Python-Audio.zip](https://drive.google.com/file/d/1T8mAnT7SU-kurOYdPcE-EzSRh2DbD5NW/view?usp=drivesdk) | 기본 앱·휴대용 Python·기본 음성 |
| [CARLA_0.9.16.zip](https://drive.google.com/file/d/1xwlyE0iy7PC9VNs0hlxJp2u5I1wADdu_/view?usp=drivesdk) | CARLA 엔진 · 약 6.8GB |
| Hongik-Experiment-Update-20261122.zip | 이번 최신 코드·설정·음성 |

기본 앱 ZIP을 풀어 생성된 Hongik-CARLA-Lab-20261107 폴더 안에 CARLA_0.9.16.zip을 둡니다. 그다음 위 업데이트 순서를 따릅니다. GitHub 소스 ZIP만으로는 전체 실행 환경이 구성되지 않습니다.

Windows x64·NVIDIA GPU 환경 기준입니다. 시작 시 **시스템 커밋 여유 16GiB**를 검사합니다. 설치 RAM 또는 GPU VRAM 16GB를 뜻하지 않습니다. 사용하지 않는 큰 앱을 저장 후 닫고, 시작 기준을 임의로 낮추지 않습니다.

## 무엇을 눌러 실행하나요?

| 목적 | 실행본 안의 파일 | 설명 |
| --- | --- | --- |
| 참가자 UX 실험 | live/64_START_EXPERIMENT.bat | 연습 → 정체 OFF/ON → 졸음운전 OFF/ON, 모션 OFF |
| 노트북 일반 시나리오 | START_LAPTOP.bat 또는 live/60_START_LAPTOP.bat | 기존 내비·작은 주행 미리보기 |
| 연구실 3면 영상 | live/61_START_LAB_PROFILE.bat | 공통 3면 설정, 모션 OFF |
| 기존 MotionHouse 연동 | START_MOTION_PROFILE.bat 또는 live/62_START_MOTION_PROFILE.bat | 장비 담당자와 기존 현장 연결 확인 후 사용 |
| 연결 상태 보고서 | live/55_LAB_CONNECTION_CHECK.bat | lab-reports에 보고서 저장; 주행 시작 버튼이 아님 |
| 음성 입력 최초 준비 | live/63_SETUP_LOCAL_STT.bat | PC마다 한 번, 시스템 Python 3.12 필요 |
| NuRec 환경 준비 / 선택 / 종료 | live/66_NUREC_SETUP.bat → 65_START_NUREC_LAB.bat → 67_STOP_NUREC_LAB.bat | 별도 SSD 모델·WSL 필요 |

## 실험 진행 순서

1. 64번 진행자 화면에서 참가자 ID를 입력합니다. **참가자 등록 없이 테스트**도 가능합니다.
2. 문구 순서를 확인하고 2분 연습 → 정체 AI OFF → ON → 졸음운전 AI OFF → ON 순으로 준비합니다.
3. 회차 선택 시 기존 내비가 열립니다. 차량·카메라 준비 완료 후 내비의 **출발**을 누릅니다.
4. AI ON에서는 상황 배너·짧은 설명·하단 컬러 웨이브가 반응합니다. **홍익이**를 누르면 상황 설명 후 선택지·직접 입력·말하기로 요청할 수 있습니다.
5. 해석한 요청을 확인하고 실행합니다. 대응 안내를 들은 뒤 실제 차량 반응과 결과를 관찰합니다. 불명확하거나 지원하지 않는 요청은 실행하지 않습니다.
6. 주행 완료 후 설문을 작성합니다. 진행자는 인터뷰를 마치고 다음 회차를 선택합니다. 진행 중인 회차를 덮어쓰지 않습니다.

AI OFF는 AI 알림·설명·입력을 숨깁니다. 음악·기존 내비·고정 도움/정차 버튼은 유지합니다. **예전 인터페이스 A/B와 이번 AI OFF/ON은 다른 구분**입니다.

전체 선택 화면에는 정체·불안정한 앞차·짙은 안개·보행자 상호 양보·카풀 대기 중 외부인 접근·차량 하부 이상음·낙하물이 있습니다. 이 전체 목록과 이번 OFF/ON 실험 순서를 구분합니다. 모든 대응이 교통 문제를 해결하는 것은 아닙니다.

## 아이패드에 기존 내비 전체 띄우기

PC와 아이패드를 같은 Wi-Fi에 연결합니다. PC의 QR 화면 또는 **http://127.0.0.1:8776/connect**를 열고, 표시된 QR을 아이패드 Safari로 엽니다. **기존 내비 전체 /m/navigation**을 선택하고 현재 연결 코드를 입력합니다.

아이패드는 PC가 표시한 LAN 주소를 사용합니다. 127.0.0.1은 아이패드 자신이므로 입력하지 않습니다. Wi-Fi·PC가 바뀌면 IP도 달라질 수 있습니다. 예전 채팅의 주소·QR·6자리 코드를 재사용하지 말고 연결 화면의 최신 값을 확인합니다.

화면·선택·텍스트 입력은 HTTP에서도 가능합니다. **마이크 입력은 HTTPS·해당 PC 인증서 신뢰·Safari 권한**이 필요합니다. 새 PC에서 예전 PC의 인증서·알림 등록이 유효하다고 가정하지 않습니다. 음성 중복을 피하려면 참가자 내비 탭은 하나로 유지합니다.

## 전체 구조와 음성 구현

```text
참가자 내비 / 아이패드
    ↕ 같은 PC·같은 네트워크의 앱 API
PC 앱 :8774 → 시나리오·요청 확인 → CARLA 차량 제어
    ├─ CARLA :2026 → 일반 주행 영상
    ├─ NuRec 옵션 :2016 + gRPC :46435 → 실사 배경 영상
    └─ 모션 선택 시 data-server-py → WebSocket :8765 / MotionHouse UDP :10000
```

아이패드 게이트웨이는 HTTP 8776 / HTTPS 8777입니다. GitHub나 Drive가 주행 명령을 중계하지 않습니다. WebSocket 8765는 위치·모션 신호용이고, 내비의 앱 API는 별도로 연결됩니다.

출력 음성은 Qwen3-TTS로 **미리 합성한 녹음**을 재생합니다. 한국어·영어 Sohee, 중국어 Vivian입니다. 주행 중 GPU에서 계속 합성하지 않습니다. 음성 캐시와 manifest를 함께 전달해야 합니다.

말하기는 로컬 **faster-whisper small / CPU INT8**로 음성을 텍스트로 바꿔 지원 요청에 연결합니다. 유료 API는 필수가 아닙니다. 자유 대화형 주행 판단 모델은 아니며, 실제 마이크·소음·억양에서 인식률과 지연은 현장 확인이 필요합니다. 새 PC의 STT 환경과 모델은 63번으로 따로 준비합니다.

## 수정 위치와 공통 세팅

| 위치 | 내용 |
| --- | --- |
| live/course_ui, navigation.js, midterm_panel.js/css | 기존 내비·지도·차량 3D·요청 패널·홍익이 |
| live/native_carla.py, midterm_study.py, passing_traffic.py | CARLA 시나리오·주행·차량 배치 |
| live/nurec_natural.py, scene_bridge.py | NuRec 차량 이동·렌더 연동 |
| live/settings/lab-shared.json | 공통 화면·카메라 설정 |
| live/settings/portable-motion.json | 모션·포트·패킷 설정 |
| live/lab.local.json | PC별 예외 설정; Git·이번 업데이트에서 제외 |
| cache/research-voice 및 음성 폴더 | 사전 음성·환경음; Drive/SSD로 전달 |

공통 주행 화면 **5760×1080, 16:3**, 각 면 화각 72도, 좌/중/우 yaw -66/+6/+78도입니다. CARLA 기본 각 면 렌더 1280×720, NuRec 기본 960×540입니다. **30fps 설정은 목표 상한이며 실측 성능 보장이 아닙니다.** 노트북 미리보기와 연구실 화면 배치는 다를 수 있습니다.

## GitHub Pull / Push

팀 공유 기준은 **codex/portable-motion-20261111**입니다. main만 받으면 최신 전달본과 다를 수 있습니다. 처음에는 별도 소스 작업 폴더에 복제합니다.

```powershell
git clone --branch codex/portable-motion-20261111 https://github.com/jungmin5589-del/hongik-carla-hmi.git hongik-carla-work
cd hongik-carla-work
git status
git pull --ff-only
```

수정 전 Pull, 수정 후 diff → 수정 파일만 add → 감사 검사 → Commit → Push 순서입니다. 쓰기에는 본인 GitHub 계정의 저장소 권한이 필요합니다. 현장 수정분이 있으면 보존부터 하고 Reset·강제 Push로 맞추지 않습니다.

```powershell
git diff
git add -- midterm_panel.css
python repo_safety.py
git commit -m "Update passenger interface styles"
git push
```

파일명은 예시입니다. 실제 바꾼 파일만 추가합니다. Pull은 코드 갱신이며 실행 중인 앱을 자동 교체하거나 음성을 받지 않습니다. 실행본에 반영 후 재시작합니다. Git 없는 기존 연구실 폴더는 [Git 연결 절차](LAB-GIT-WORKFLOW-KO.md)를 따릅니다.

## 참가자 기록과 Drive

등록 회차는 선택·실행·경과 시간·차량 신호·설문을 주행 ID와 연결해 저장합니다. 진행자 화면의 **관리자 · 기록** 또는 PC의 **http://127.0.0.1:8774/admin**에서 확인합니다.

원본은 해당 PC의 **%LOCALAPPDATA%/HongikDriveResearch/research.sqlite3**입니다. 비공개 실험 기록 Drive 폴더와 연결 설정을 검증한 PC에서만 백업합니다. **새 PC의 Drive 로그인과 기록 폴더 연결은 별도 확인**이 필요합니다. 배포 폴더와 참가자 기록 폴더는 구분합니다.

이번 ZIP에는 참가자 DB·설문 응답·입력 녹음·인증정보·인증서·개인키·연결 코드·PC별 동기화 설정을 넣지 않았습니다. 새 PC의 인증서·페어링·기록 연결은 해당 PC에서 준비합니다. 상용 음악과 NuRec 모델도 이번 ZIP에 포함하지 않습니다.

## NuRec 옵션과 현재 검증 범위

이번 NuRec 선택 화면의 정체·불안정한 앞차 두 조건은 CARLA 실험과 도로·차량·길이가 완전히 같지 않습니다. 동일 연구 조건으로 합쳐 분석하지 않습니다. CARLA만 사용할 때는 NuRec 설치가 필요 없습니다.

NuRec은 별도 SSD의 모델·원본·WSL VHD·Docker GPU 환경이 필요합니다. 이 ZIP은 모델·VHD를 업로드하지 않습니다. 원 제공처의 접근 권한·이용 조건에 따라 준비합니다. [NuRec 설치·실행 안내](NUREC-LAB-OPTION-KO.md)를 참고합니다.

노트북 RTX 5060 Laptop 8GB, 실제 3면×540p에서 정체 약 3.4fps / 앞차 흔들림 약 6.3fps가 측정됐습니다. **안정적인 30fps는 아직 달성하지 못했습니다. NuRec 모션은 OFF이고 실제 연구실 6축 장비 검증은 남아 있습니다.**

경로 끝에서 경적 뒤 차량이 크게 돌아가 깨져 보인 오류는 이동 거리에 맞춰 흔들림·회전을 계산하도록 수정했습니다. 관련 자동 검사 68개를 통과했으나 수정 후 실제 GPU 재주행 확인은 남아 있습니다. 미촬영 면·독립 바퀴 표현의 한계도 남습니다.

## 문제 해결

| 증상 | 먼저 확인 |
| --- | --- |
| 창이 안 뜸 | 완전 실행 폴더·엔진·Python, 시작 창의 오류 |
| 16GiB 대기 | 시스템 커밋 여유, 불필요한 큰 앱 저장 후 종료 |
| 업데이트 거부 | 주행 앱 정상 종료·완전 실행 폴더 선택·--check 결과 |
| 아이패드 접속 실패 | 같은 Wi-Fi·최신 QR/IP·PC 앱과 게이트웨이 |
| 음성 없음 | 음량·첫 클릭·최신 음성 캐시와 manifest 동시 반영 |
| 말하기 불가 | 63번 준비; 아이패드 HTTPS·마이크 권한 |
| Drive에 기록 없음 | PC 관리자 기록부터 확인, 비공개 동기화 연결 상태 |
| NuRec SSD 없음 | 드라이브 문자·모델·WSL VHD; CARLA는 별도 실행 가능 |

오류 화면과 55_LAB_CONNECTION_CHECK.bat의 보고서를 담당자에게 전달합니다. 참가자 데이터가 든 전체 폴더를 공개 채팅·GitHub에 올리지 않습니다.

## 팀 채팅에 붙여 넣을 안내

홍익이 주행 실험 최신 세팅과 설명을 정리했습니다. GitHub 공유 브랜치에서 코드·설정을, Drive에서 최신 업데이트 ZIP과 기본 실행본·음성을 받으면 됩니다. 기존 설치가 있으면 앱을 종료한 뒤 최신 ZIP의 APPLY_TEAM_UPDATE.bat에 기존 실행 폴더를 끌어 놓고 live/64_START_EXPERIMENT.bat로 시작해 주세요. 아이패드는 같은 Wi-Fi에서 PC 연결 화면의 최신 QR로 기존 내비 전체를 엽니다. 자세한 내용은 00_팀원_사용안내.html에 있습니다. NuRec은 별도 개발 옵션이며 CARLA 실험에는 설치하지 않아도 됩니다.
