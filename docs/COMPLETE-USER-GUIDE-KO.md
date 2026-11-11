# 휴자인 CARLA 통합 사용 설명서

노트북·연구실 PC / SSD·Google Drive·GitHub / 2026-11-11

Windows 노트북과 연구실 PC에서 같은 시나리오·내비·설정을 사용하는 방법입니다. 노트북은 작은 미리보기 창으로 실행하고, 연구실에서는 3면 영상과 기존 6축 연결을 선택합니다.

## 바로 가기

[GitHub 공유 브랜치](https://github.com/jungmin5589-del/hongik-carla-hmi/tree/codex/portable-motion-20261111)

[Google Drive 전달 폴더](https://drive.google.com/drive/folders/1W-h_GiLCqybHn4jzeNg_gRI3eTw0wFz2)

[최신 휴대용 업데이트 ZIP](https://drive.google.com/file/d/1khfw4bvxm6Etyb-1cT48wvPLEa0CoT3o/view)

[공통 카메라 설정 JSON](https://github.com/jungmin5589-del/hongik-carla-hmi/blob/codex/portable-motion-20261111/settings/lab-shared.json)

[공통 모션·웹소켓 설정 JSON](https://github.com/jungmin5589-del/hongik-carla-hmi/blob/codex/portable-motion-20261111/settings/portable-motion.json)

## 처음 실행할 때의 선택

- 노트북 미리보기: Hongik-CARLA-Lab-20261107\START_LAPTOP.bat

- 연구실 3면 영상: live\61_START_LAB_PROFILE.bat

- 연구실 3면 영상 + 6축·웹소켓: START_MOTION_PROFILE.bat 또는 live\62_START_MOTION_PROFILE.bat

기존 PC의 HJI-2026-2\START_HONGIK_MOTION.bat도 기존 연결 방식으로 사용할 수 있습니다. 새 공통 프로파일은 SSD·Drive 전달본에 포함되어 있습니다.

## 실행 전 준비

전달본의 Python과 CARLA 엔진은 Windows x64용입니다. macOS에서는 GitHub 소스 편집을 이어갈 수 있지만 이 .bat와 .exe는 실행할 수 없습니다.

노트북에서도 CARLA를 구동하려면 GPU와 최소 16GiB의 시스템 커밋 여유가 필요합니다. 16GiB는 설치된 RAM 용량이나 여유 VRAM을 뜻하지 않습니다. 미리보기 모드도 CARLA 엔진을 사용합니다.

기존 CARLA 주행 프로그램을 정상 종료한 다음 업데이트합니다. 실행 중인 연구실 프로그램을 강제로 종료하거나 다른 CARLA 설치에 덮어쓰지 않습니다.

## SSD에서 노트북으로 복사

1. SSD의 Hongik-CARLA-Lab-20261107 폴더를 노트북 내부 SSD로 통째로 복사합니다.

2. live, data-server-py, python, cache와 CARLA_0.9.16 폴더 또는 CARLA_0.9.16.zip이 함께 있는지 확인합니다.

3. 복사한 폴더에서 START_LAPTOP.bat을 실행합니다. 폴더 전체 대신 .bat 파일만 옮기면 실행되지 않습니다.

4. 첫 실행에서는 엔진 준비와 사전 점검을 진행합니다. 준비된 엔진은 다시 압축 해제하지 않습니다.

5. 열린 내비에서 시나리오를 고르고 준비가 끝나면 출발합니다. 주행 화면은 작은 3면 미리보기로 열리고 모션은 꺼져 있습니다.

공유용 ZIP·Git 소스 백업·간단 안내서는 SSD의 F:\Hongik-CARLA-Shared-20261111 폴더에도 모아두었습니다. 노트북에서 SSD 드라이브 문자는 F:와 다를 수 있습니다.

### 폴더 구성

```text
Hongik-CARLA-Lab-20261107\
  START_LAPTOP.bat
  START_MOTION_PROFILE.bat
  live\
  data-server-py\
  python\
  cache\
  CARLA_0.9.16\ 또는 CARLA_0.9.16.zip
```

## Google Drive에서 새 설치

[기존 앱·Python·음성 ZIP](https://drive.google.com/file/d/1T8mAnT7SU-kurOYdPcE-EzSRh2DbD5NW/view)

[CARLA 0.9.16 엔진 ZIP](https://drive.google.com/file/d/1xwlyE0iy7PC9VNs0hlxJp2u5I1wADdu_/view)

[2026-11-11 휴대용·모션 업데이트 ZIP](https://drive.google.com/file/d/1khfw4bvxm6Etyb-1cT48wvPLEa0CoT3o/view)

1. 기존 앱·Python·음성 ZIP을 다운로드하고 압축을 풉니다. Hongik-CARLA-Lab-20261107 폴더가 생깁니다.

2. 엔진 ZIP을 다운로드하고 파일 이름을 CARLA_0.9.16.zip으로 유지한 채 위 폴더 안에 둡니다. 엔진은 실행기가 준비합니다.

3. 최신 업데이트 ZIP은 별도 위치에 압축을 풉니다. 그 안의 APPLY_PORTABLE_UPDATE.bat을 찾습니다.

4. 앞에서 준비한 Hongik-CARLA-Lab-20261107 폴더를 APPLY_PORTABLE_UPDATE.bat 위로 끌어 놓습니다.

5. 완료 메시지를 확인한 다음 기존 폴더 안의 START_LAPTOP.bat으로 실행합니다.

이미 실행본이 있다면 최신 업데이트 ZIP만 적용하면 됩니다. 이번 패키지에는 최신 앱 소스와 기존 앱 ZIP 이후 추가된 캐시·Python 파일이 들어 있어 11월 9일 업데이트를 먼저 적용할 필요가 없습니다.

업데이터는 교체 파일을 update-backups 아래에 백업하고, lab.local.json·페어링 데이터·기존 연구 기록을 보존합니다. 설치 결과는 PORTABLE-SHARE-20261111.json으로 확인합니다.

## 연구실 3면·6축 실행

### 영상만 확인할 때

live\61_START_LAB_PROFILE.bat을 실행합니다. 5760×1080 주행 창과 조작용 내비를 사용합니다. 현재 PC처럼 Surround가 5760×1200이면 기존 크기의 주행 창을 세로 중앙에 배치합니다. 시스템 해상도와 카메라 보정값은 유지합니다.

### 6축을 함께 사용할 때

1. 기존 장비 절차에 따라 MHServicer와 중립·정지 상태를 확인합니다.

2. START_MOTION_PROFILE.bat 또는 live\62_START_MOTION_PROFILE.bat을 실행합니다.

3. 내비에서 시나리오를 선택합니다. 연결기는 해당 시나리오의 ego 차량을 따라 기존 data-server-py 계산으로 모션과 웹소켓 데이터를 보냅니다.

4. 주행을 멈출 때는 먼저 일시정지하고 장비의 기존 중립·정지 절차를 따른 뒤 프로그램을 종료합니다.

통합 모션 실행기와 별도 RUN_6DOF_LINK.bat을 동시에 실행하지 마세요. 같은 수신기에 중복 송신할 수 있습니다. 첫 현장 확인은 기존 장비 점검 절차에 따라 진행합니다.

## 내비·아이패드·연결 확인

[PC 내비: http://127.0.0.1:8774/](http://127.0.0.1:8774/)

[PC의 아이패드 연결 안내: http://127.0.0.1:8776/connect](http://127.0.0.1:8776/connect)

아이패드를 PC와 같은 네트워크에 연결하고 PC에 표시된 QR이나 연결 안내 주소를 사용합니다. 아이패드에 127.0.0.1 주소를 직접 입력하면 PC에 접속되지 않습니다. Wi-Fi가 바뀌면 새 연결 주소를 확인합니다.

WebSocket 8765는 위치·모션 텔레메트리용입니다. 현재 내비는 8774의 앱 API를 사용하므로 웹소켓만 켜졌다고 내비 준비가 끝난 것은 아닙니다.

- 읽기 전용 점검: live\54_LAB_CHECK.bat

- 연결 보고서: live\55_LAB_CONNECTION_CHECK.bat. 결과는 lab-reports 폴더에 저장합니다.

## GitHub에서 작업 이어가기

현재 전달 기준은 codex/portable-motion-20261111 브랜치입니다. main과 구분해 선택합니다. GitHub에는 소스와 공통 설정을 보관하고, 엔진·휴대용 Python·음성 캐시는 SSD 또는 Drive에서 받습니다.

### Git 없이 다운로드

1. GitHub 공유 브랜치 링크를 열고 브랜치 이름이 codex/portable-motion-20261111인지 확인합니다.

2. Code → Download ZIP을 눌러 소스를 다운로드합니다.

3. 실행본을 종료하고 기존 live 폴더를 백업한 다음 필요한 소스 파일을 반영합니다. GitHub ZIP만으로는 전체 실행 환경이 구성되지 않습니다.

### Git으로 소스 편집

처음에는 터미널에서 별도 작업 폴더로 복제합니다. 아래의 carla-work는 소스를 편집하는 폴더이며 전체 휴대용 실행본은 별도로 유지합니다.

```text
git clone --branch codex/portable-motion-20261111 https://github.com/jungmin5589-del/hongik-carla-hmi.git carla-work
cd carla-work
```

다음 작업을 시작할 때 먼저 변경 상태를 확인하고 공유 브랜치의 최신 내용을 받습니다.

```text
git status
git pull --ff-only
```

설정을 수정했다면 변경 내용을 확인한 뒤 해당 파일만 저장합니다. 아래는 공통 설정 두 파일을 수정한 경우의 예입니다.

```text
git diff
git add settings/lab-shared.json settings/portable-motion.json
git commit -m "Update shared lab settings"
git push
```

처음부터 수정한 파일이 있으면 내용을 먼저 보관·커밋한 후 pull합니다. 충돌이 나면 덮어쓰거나 초기화하지 말고 변경 내용을 비교합니다. 저장소에 쓰려면 쓰기 권한이 있는 GitHub 계정이 필요합니다.

GitHub 변경은 실행 중인 프로그램이나 SSD·Drive에 자동 반영되지 않습니다. 검증한 파일을 실행본에 적용하고 SSD를 갱신한 뒤, 새 전달 패키지를 Drive에 올리는 순서로 공유합니다.

## 공통 설정과 PC별 설정

- 화면·카메라 기준: live\settings\lab-shared.json

- 모션·포트·백엔드 기준: live\settings\portable-motion.json

- 해당 PC의 경로와 예외값: live\lab.local.json. 개인 PC 전용 파일로 유지합니다.

카메라 설정은 기본값 → 공통 JSON → lab.local.json 순서로 적용합니다. lab.local.json의 같은 항목이 우선하므로 공통 값을 바꿔도 이 PC 값이 그대로라면 이 파일을 확인합니다. 모션 환경변수는 portable-motion.json보다 우선합니다.

lab-shared.json의 motion_enabled가 false인 것은 영상 실행의 기본값입니다. 6축 사용 여부는 선택한 실행 프로파일이 결정합니다. 이 값을 true로 바꾸지 말고 모션 실행 파일을 사용합니다.

### MHServicer가 별도 PC에 있을 때

기존 연구실 수신기 IP를 확인한 뒤 해당 PC에서만 환경변수로 지정합니다. 아래 주소는 예시이며 실제 수신기 IP로 바꿔야 합니다.

```text
set "SIXDOF_UDP_HOST=수신기_IP"
call START_MOTION_PROFILE.bat
```

### GitHub에 올리지 않는 파일

CARLA 엔진, 음원·음성 캐시, 모델, 참가자 연구 데이터, 실행 로그, 인증서·개인 키, Git 인증정보, lab.local.json은 GitHub에 올리지 않습니다. 개인 자료가 포함된 폴더 전체를 git add로 추가하지 않습니다.

## 자주 생기는 문제

### 메모리 부족으로 실행 중단

Less than 16 GiB commit headroom 메시지는 시스템 커밋 여유가 기준보다 적다는 뜻입니다. 사용하지 않는 프로그램을 닫고 재시도합니다. 시작 기준을 임의로 낮추지 않습니다.

### 3면 화면을 찾지 못한 경우

노트북에서는 START_LAPTOP.bat을 사용합니다. 연구실에서는 기존 NVIDIA Surround 설정을 확인합니다. 지원하는 전체 화면은 5760×1080이며 5760×1200에서는 가운데에 같은 크기 창을 배치합니다.

### WebSocket은 연결됐지만 내비가 빈 경우

8774 내비가 열리는지, CARLA 2026에 시나리오가 준비됐는지 확인하고 연결 보고서를 저장합니다. 예전 WebSocket 8766과 이번 통합 모션의 기본값 8765를 혼동하지 않습니다.

### 모션이 움직이지 않는 경우

모션 프로파일로 실행했는지, data-server-py가 함께 있는지, MHServicer의 IP·UDP 포트가 맞는지 확인합니다. 연결을 확인하기 전 필터나 게인부터 바꾸지 않습니다.

### GitHub 권한 오류

Permission denied 또는 403이면 Git에 저장된 계정을 확인합니다. 브라우저 로그인과 PC Git 인증은 별개일 수 있습니다. 계정과 저장소 권한을 확인한 다음 다시 push합니다.

### 업데이트가 실행 중인 앱을 감지한 경우

Close the running driving app normally first 메시지가 나오면 기존 주행 앱을 정상 종료한 뒤 적용합니다. 다른 앱의 프로세스를 강제로 종료하지 않습니다.

## 검증 범위와 백업

공유 프로파일·모션 텔레메트리·중립 복귀 등 관련 자동 검증 55개를 통과했고, SSD 설치 파일 574개의 해시를 확인했습니다. 이 결과는 실제 6축 장비의 방향·크기·반응 검증을 대신하지 않습니다. 실제 플랫폼 움직임은 별도로 현장에서 확인해야 합니다.

이번 SSD 적용의 백업은 update-backups\portable-share-503d0da90b174c77829bdc1d0edcea0f에 있습니다. 직접 복원하기 전 현재 실행본도 별도로 백업하고 복원할 파일과 버전을 확인합니다.

[Git 소스 오프라인 백업](https://drive.google.com/file/d/1wsppUdpjiQ6HpuLV0M4YZl37x87RZsXu/view)

Git 소스 백업은 이력과 공유 브랜치를 보관한 .bundle 파일입니다. 앱 실행 ZIP이나 엔진을 대신하지 않습니다.

## 설정값 빠른 확인

| 항목 | 공유 기준 |
|---|---|
| 실행 버전 | CARLA 0.9.16 / Python 3.12.10 |
| RPC / 내비 | 2026 / 8774 |
| 모션 WebSocket | 8765 |
| MotionHouse UDP | 127.0.0.1:10000 |
| 모션 프로파일 / 패킷 | A / legacy 69바이트 / deg2rad |
| 샘플링 / Rust 출력 | 25Hz / 100Hz 보간 |
| 가속도 사전 필터 / hold | 0 / 0 |
| 주행 창 / 각 면 렌더 | 5760×1080 / 1280×720 |
| 카메라 화각 / yaw / pitch | 72° / +6° / -4° |
| 좌·중·우 시야 | -66° / +6° / +78° |
| 기본 눈 위치 | (0, -0.35, 1.2)m |
| 카풀 눈 위치 | (0.9, -0.35, 1.6)m |
| 목표 FPS | 30, 실제 성능은 현장 확인 |

[편집 가능한 Google 설명서](https://docs.google.com/document/d/1W_Dxo7VV-BwCVcCsfQggS7lbRbohHPLF5G30roEA7as/edit)

