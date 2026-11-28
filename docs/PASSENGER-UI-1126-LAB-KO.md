# 11월 26일 팀원 UI · 연구실 제어 보존 업데이트

디자인 원본은 `design/passenger-ui-1126`의 a3d08f0이며 4a8a4e2에서 실험 브랜치에 병합됐습니다. 왼쪽 주행·상황 알림 / 오른쪽 설명·대응 선택, 고정 레이아웃, 독립 설문 화면과 작은 음악 위젯, 진행자 Geist 글꼴이 주요 변경입니다. 웹 데모는 CARLA 없이 모의 상태를 사용하므로 실제 주행의 증거가 아닙니다.

## 연구실 적용

연구실에서 잘 작동한 코드와 Rust 엔진을 먼저 백업합니다. **11월 22일 전체 업데이트 ZIP을 연구실 수정본 위에 다시 적용하지 마세요.** 주행·모션 소스와 DLL이 과거 버전으로 바뀔 수 있습니다.

최신 소스를 별도 폴더에서 받고, 다음 도구를 사용합니다. TARGET은 연구실의 기존 live 폴더입니다.

```powershell
python apply_passenger_ui.py --target-live "TARGET"
python apply_passenger_ui.py --target-live "TARGET" --apply
```

첫 명령은 검사만 합니다. 두 번째 명령은 앱을 정상 종료한 뒤 실행합니다. UI 파일·글꼴을 복사하고 서버 코드의 CSS 제공·중복 헤더 링크 두 부분만 수정합니다. native_carla.py 전체를 복사하지 않습니다. 교체 파일은 live/backups/passenger-ui-*에 백업합니다. 주행·모션 제어·설정·Rust DLL의 해시가 유지되는지도 검사합니다. 실행본의 앱을 완전히 종료하고 다시 켜야 반영됩니다.

## 6축 PDF와 코드의 관계

제공 PDF는 2026-11-25 s1/Town04/프로파일 A 시험 기록입니다. 다음 수치는 PDF 보고값이며 여기서 재측정하지 않았습니다.

| 수정 | 다른 주행에도 유지 가능한 조건 |
| --- | --- |
| ego 접근 속도 보정·페달 평활 | vehicle_following.py와 native_carla.py 호출부를 함께 보존해야 함. 새 제어기가 직접 throttle/brake를 쓰면 우회될 수 있음 |
| 단발 가속도 튐 필터 | collector에 유지되면 위치·시간을 바꿔도 작동. PDF 기본 적용은 정체·야간 |
| surge .6 / sway .8 / heave .7 / roll .5와 roll .4초 평활 | motion_link의 s1 판별과 collector 매개변수 전달이 유지돼야 함. 다른 시나리오 전체에 자동 적용된다는 뜻 아님 |
| 내리막 pitch | 실제 도로 경사를 입력하므로 같은 맵의 시간표보다 재사용성이 높음. motion_link·collector·transforms_A·재빌드한 Rust DLL이 모두 필요 |

시나리오 시간·출발 위치·교통 배치를 바꿔도 알고리즘은 유지할 수 있지만, 움직임의 크기와 안전 간격은 다시 검증해야 합니다. PDF의 0:43·1:41 등은 분석 구간이지 새 도로의 보정 시각으로 사용하면 안 됩니다. 프로파일 ID·ego 교체 시 collector 재연결도 확인합니다. UI 변경 자체는 모션 수식을 바꾸지 않습니다.

PDF의 최종 surge 표준편차 .113→.009와 pitch 약 −.073은 로그 결과이며 최종 리그 체감 검증은 남아 있습니다. 1:22 heave 단발 튐, 커브 heave 기준 이동, 4:13 주변 차량끼리 충돌도 미해결로 기록돼 있습니다.

## 현재 확보하지 못한 연구실 수정본

현재 GitHub와 연결 SSD 복사본에는 PDF의 EGO_CLOSING_GAIN, EGO_PEDAL_SMOOTHING, HONGIK_MOTION_SPIKE_GUARD, PROFILE_SCALES·pitch_down 변경이 없습니다. PDF만 보고 구현된 것으로 간주하거나 수식·DLL을 임의 대체하지 않습니다.

연구실에서 live/vehicle_following.py, native_carla.py, motion_link.py, test_accel_spike_guard.py, test_vehicle_following.py와 data-server-py/collector/carla_collector.py, processing/transforms_A.py, sixdof_rs.pyd 및 Rust 원본·빌드 정보를 가져와야 최종 통합 검증이 가능합니다. DLL은 Git 대신 기존 제한된 배포 경로로 전달합니다. 테스트·로그·참가자 데이터는 구분합니다.

## 재검증 순서

1. 모션 OFF로 UI·알림·대응 실행·음성·설문·아이패드 연결을 확인합니다.
2. 주행 제어와 모션 코드·DLL 해시, 재시작 후 Collector 입력 축소 로그를 확인합니다.
3. s1 OFF/ON과 s2를 각각 돌려 시각 외에 위치·속도·접근 속도·페달·6축 신호·충돌 주체를 비교합니다.
4. 급제동·언덕 꼭대기·도로 이음매·내리막·정차·시나리오 전환을 확인합니다. 실제 리그는 담당자와 중립·비상정지 절차로 별도 시험합니다.

## 2026-11-28 적용·검사 결과

연결 SSD의 CARLA 실행본에 UI 전용 업데이트를 실제 적용하고 보호 대상 해시가 유지됨을 확인했습니다. 이는 연구실 수정본을 확보했다는 뜻이 아닙니다. 관련 Python 검사 42개 중 41개 통과·1개 건너뜀, 전용 배포 검사와 NuRec 관련 검사 27개 통과를 확인했습니다(중복 포함). 브라우저에서 요청 확인·취소·OFF/ON·재알림·시작 화면·모바일 알림·동작 줄이기 검사가 통과했습니다. 새 UI 7단계 화면을 별도 상태 재현으로 확인했습니다. 실제 CARLA 물리·음성·아이패드 기기·6축 리그 재시험은 아직 수행하지 않았습니다.

새 패키지의 APPLY_PASSENGER_UI.bat에 기존 완전 실행 폴더를 끌어 놓으면 UI만 적용됩니다. 하단 고객센터·정차 표시는 요청 버튼이며 실제 상담 연결이나 갓길 확보를 보장하는 표시가 아닙니다.
