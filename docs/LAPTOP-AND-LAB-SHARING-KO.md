# 노트북과 연구실에서 같은 설정으로 작업하기

2026-11-11. 공통 설정은 `settings/lab-shared.json`과
`settings/portable-motion.json`에 저장합니다. PC마다 다른 절대 경로는 공유하지 않습니다.
`lab.local.json`은 해당 PC에서만 관리하며 공통 화면 설정보다 우선합니다.
수신기 주소 등을 환경변수로 지정한 경우에도 그 값을 우선합니다.

## 실행

Windows 노트북에서는 `live/60_START_LAPTOP.bat`을 실행합니다.
작은 3면 미리보기와 최신 내비를 띄우며 모션은 켜지지 않습니다.
연구실 영상 실행은 `live/61_START_LAB_PROFILE.bat`, 기존 6축·웹소켓 실행은
`live/62_START_MOTION_PROFILE.bat`입니다. `--check`를 붙이면 설정만 출력합니다.
현재 휴대용 Python과 CARLA 엔진은 Windows x64용입니다.
macOS에서는 GitHub 소스 편집은 가능하지만 이 Windows 실행 파일은 실행할 수 없습니다.
노트북도 CARLA 구동에는 GPU와 16GiB 시스템 커밋 여유가 필요합니다.

## 공통 설정

| 항목 | 값 |
|---|---|
| CARLA / Python | 0.9.16 / 3.12.10 |
| CARLA RPC / 내비 | 2026 / 8774 |
| 모션 WebSocket / MotionHouse UDP | 8765 / 127.0.0.1:10000 |
| 모션 프로파일 / 패킷 | A / legacy 69바이트, deg2rad |
| 샘플링 / Rust 송신 | 25Hz / 100Hz 보간 |
| 가속도 사전 필터 / hold | 0 / 0, 기존 보정 유지 |
| 주행 창 / 렌더 | 5760×1080 / 각 면 1280×720 |
| 화각 / yaw / pitch | 72° / +6° / -4° |
| 시야 방향 | 좌 -66°, 중앙 +6°, 우 +78° |

5760×1200 Surround는 기존 크기 창을 세로 가운데에 배치합니다.
`data-server-py`의 원본 transforms/filters 및 UDP 계산을 함께 전달합니다.
Rust 확장 파일은 SSD·Drive 패키지에 포함하고 GitHub에는 Python 소스를 보관합니다.
별도 `RUN_6DOF_LINK.bat`과 통합 모션 실행기를 동시에 켜지 마세요.

## SSD에서 노트북으로

SSD의 `Hongik-CARLA-Lab-20261107` 폴더를 노트북 내부 SSD로 복사합니다.
`live`, `data-server-py`, `python`, `cache`, 엔진 폴더/엔진 ZIP이 함께 있어야 합니다.
프로젝트를 옮겨도 실행기는 같은 폴더에 동봉된 엔진과 모션 프로그램을 찾습니다.

## Google Drive에서 새로 준비하기

[기존 전달 폴더](https://drive.google.com/drive/folders/1W-h_GiLCqybHn4jzeNg_gRI3eTw0wFz2)에서
기존 `Hongik-CARLA-Lab-20261107-App-Python-Audio.zip`과 `CARLA_0.9.16.zip`을 받습니다.
앱 ZIP을 풀고 엔진 ZIP을 생성된 폴더 안에 둡니다.
이번 `Hongik-CARLA-Portable-Motion-20261111.zip`을 별도 위치에 풀고
`APPLY_PORTABLE_UPDATE.bat`에 기존 `Hongik-CARLA-Lab-20261107` 폴더를 끌어 놓습니다.
업데이터는 교체 파일을 백업하며 PC의 `lab.local.json`, 개인 페어링, 기록은 보존합니다.
이번 패키지는 최신 전체 앱 소스와 이전 앱 ZIP 이후 변경된 캐시·Python 추가 파일을 포함하므로
11월 9일 업데이트를 먼저 적용하지 않아도 됩니다.

## GitHub에서 작업 이어가기

[저장소](https://github.com/jungmin5589-del/hongik-carla-hmi)의
`codex/portable-motion-20261111` 브랜치를 받습니다.
최초에는 저장소 소스들을 휴대용 폴더의 `live`에 두고, 저장소의 `data-server-py`는
`live/data-server-py`로 유지해도 연결기가 찾도록 지원합니다.
소스와 공통 JSON만 커밋합니다. 엔진, 음원, 모델, 연구 데이터, 인증서, 개인 경로는
SSD·Drive에 두며 GitHub에는 올리지 않습니다.

실제 장비로 실행하기 전 기존 중립·정지 절차를 따르세요.
로컬 가상 차량/임시 포트 검증과 실제 장비 검증은 구분합니다.
이번 공유 작업은 실제 플랫폼을 구동하지 않습니다.
