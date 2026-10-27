"""Keep restricted images/performance private; record only our implementation on C."""
import hashlib
import json
import shutil
import time
import urllib.request
from pathlib import Path

L=Path(__file__).resolve().parent
T=L.parent
P=Path('C:/Users/서정민/Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인/CARLA-YOLO-실습')
F=Path('C:/Users/서정민/Documents/ChatGPT/포토폴리오/portfolio-records/carla-passenger-hmi')
stamp=time.strftime('%Y%m%d-%H%M%S')

def edit(path,text,prepend=False):
    if path.exists():
        shutil.copy2(path,Path(str(path)+'.bak-'+stamp))
        prior=path.read_text(encoding='utf-8-sig')
    else: prior=''
    path.write_text(text+'\n\n'+prior if prepend else prior+'\n\n'+text,encoding='utf-8')

with urllib.request.urlopen('http://127.0.0.1:8774/state',timeout=5) as r:
    state=json.load(r)
assert state['phase']=='live' and state['width']==1920 and state['height']==1080
assert state['mode']=='paused' and not state['scenario']['onset']
proof=L/'validation/navigation-20261019'
(proof/'ready-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
applied=[]
for run in sorted((L/'runs').iterdir()):
    events=run/'interactions.jsonl'
    if not events.exists():continue
    for line in events.read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['event'] in ('navigation_execution_confirmed','action_applied','action_completed') and row.get('utc','')>='2026-10-19T10:33:00':
            applied.append(dict(run=run.name,**row))
report=dict(phase='large_display_and_existing_navigation_verified',private_internal_trial=True,
    comparison='live/validation/native-1080-20261019-192912/result.json',
    still_model_retrained=False,old_smoke_output=[240,135],old_image_scale=.125,
    native_still_outputs=[[960,540],[1920,1080]],fullhd_physical_driving_checked=True,
    native_window_observed=True,fullscreen_key_implemented_but_not_confirmed_by_native_ui_qa=True,
    fullscreen_capture='invalid-occluded-window.png is invalid evidence and must not be published',
    browser_flow=['notification','detail','options','choice','execution_confirmation','feedback','close','reset'],
    distance_before_m=18.124,distance_after_m=33.9,actions=applied,
    tests=dict(adapter=5,scenario_rules=5,passed=10),
    ready_state=state,lab_hardware_unknown=True,lab_fullhd_fps_not_measured=True,
    source_quality_limits='Night bloom and reconstruction blur remain; no Harmonizer or source retraining',
    old36_preserved=True,old_navigation_assets_reused=True,old_voice_and_gestures_not_integrated_in_this_mode=True,
    no_participant_study=True)
(T/'reports/navigation-display-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

note='''# 大画面 주행과 기존 승객 내비 연결

2026-10-19 · 구현 및 개발 QA · 참가자 연구 아님

사용자는 실사 주행을 큰 별도 창에서 보고 기존 테슬라형 내비에서 상황 알림과 대응을 고르기를 원했다. 기존36의 내비 HTML·3D 차량 표시·지도·연구용 상세/옵션/실행 확인 UI를 별도47의 같은 CARLA 상태에 연결했다. 기존36의 실행 경로는 변경하지 않았다.

새 주행 창은 이미 생성된 최신 프레임을 구독한다. 두 창 때문에 신경 렌더 모델이나 CARLA 서버를 한 번 더 띄우지 않는다. 내비에서 자발적으로 알림을 열고, 대응 방법을 확인하고, 옵션을 선택한 뒤 실행을 승인한다. 설명을 열거나 옵션만 고르는 단계에서는 차량에 개입하지 않는다. 클락션/거리 넓히기/유지와 피드백·X 닫기·재시작을 연결했다.

실제 내비 버튼을 통한 거리 확대가 실제 물리 차량의 간격 증가로 이어지는지 확인했다. 클락션과 유지 요청, 선택 취소 및 이전 세션 입력 거부·중복 요청 억제는 구별해 검증했다. 좁은 내비 창에서 조작 패널이 알림 버튼을 가리는 문제와 매 갱신마다 옵션 DOM을 다시 만들던 문제를 수정했다. 내비 연결 상태는 실제 CARLA 값이며 YOLO의 졸음 검출 결과가 아니다.

같은 원본 모델에서 더 큰 시험 출력을 직접 생성했다. 이전의 낮은 시험 비율은 출력 해상도 설정이었고 모델을 저품질로 재학습한 것이 아니었다. 출력 크기를 높여도 야간 빛 번짐·재구성 누락은 남는다. 연구실 장비의 실시간 성능과 장시간 안정성을 측정했다고 하지 않는다.

새 모드는 시각적 연구 알림과 선택에 범위를 둔다. 기존36의 Qwen 음성·제스처·목적지 선택 전체를 새 장면에 통합했다고 표현하지 않는다. 내비 지도의 촬영 경로와 두 차로 개략도는 원본 전체 도로 토폴로지의 정확한 임포트가 아니다. OS/드라이버/보안·기존 CARLA 시작 메모리 조건은 유지했다.

직접 작성한 어댑터와 기존 시나리오 규칙을 합쳐 검사10개가 통과했다. 대형 실제 주행 창을 확인했으며 전체 화면 단축키는 구현했다. 전체 화면 키의 네이티브 자동 확인에는 다른 창이 겹쳐 해당 캡처를 성공 근거에서 제외했다.

원본/생성 화면/성능/상세 로그는 D 내부 reports/navigation-display-result.json 및 live/validation에 유지한다. 이 폴더에는 정성적 구현 기록과 자체 코드 SHA만 둔다. 참가자 행동이나 효과 검증 결과는 없다.
'''.replace('大画面','큰 화면')
new=F/'29-nurec-existing-navigation-display.md'
assert not new.exists()
new.write_text(note,encoding='utf-8')
evidence=F/'evidence'/('nurec-navigation-'+stamp)
evidence.mkdir(parents=True,exist_ok=False)
names=['navigation_adapter.py','navigation.js','navigation.css','navigation_boot.js','live_window.py','drive.html','scene_bridge.py','launch_live.py','stop_live.py','test_navigation_adapter.py','probe_1080.py']
(evidence/'own-code-sha256.json').write_text(json.dumps({n:hashlib.sha256((L/n).read_bytes()).hexdigest() for n in names},indent=2),encoding='utf-8')
(evidence/'implementation-status.json').write_text(json.dumps(dict(existing_navigation_reused=True,same_carla_session=True,
    large_window_verified=True,explicit_confirmation=True,adapter_tests_passed=5,participant_study=False,
    lab_performance_verified=False,restricted_outputs_copied=False),indent=2),encoding='utf-8')
edit(F/'README.md','[큰 주행 창과 기존 내비 연결](29-nurec-existing-navigation-display.md). 기존 연구 HMI를 같은 CARLA 상태에 연결했고 큰 별도 주행 창과 더 큰 출력 선택을 추가했다. 기존36은 보존했다. 실제 화면·성능은 D 내부에만 보관한다.',prepend=True)
edit(F/'current-native-progress.md','# LATEST — 큰 주행 창·기존 내비 알림/옵션 연동 및 확대 출력 QA 완료\n\n2026-10-19. 별도47에서 큰 주행 창과 기존36의 내비 자산을 같은 CARLA 세션에 연결했다. 자발적 알림 열기→설명→옵션→실행 확인→실제 거리 증가/클락션/유지→피드백→X 및 초기화를 확인했다. 어댑터5개+기존 규칙5개 검사 통과. 낮은 시험 출력 비율은 모델 학습 품질이 아니었으며 원본 재학습 없이 더 큰 출력을 확인했다. 새 모드는 기존 음성/제스처 전체 통합이 아니다. 마지막 화면은 큰 출력·시작 위치·정지 상태. 구체 수치·생성 화면·성능은 D 내부 reports/navigation-display-result.json, 정성 기록은29번. 전체 화면 단축키의 네이티브 자동 캡처는 다른 창이 겹쳐 성공 근거에서 제외했다. 연구실 장비 성능·참가자 연구 미검증.\n\n이전 체크포인트:',prepend=True)
edit(F/'03-worklog.md','## 2026-10-19 · 큰 주행 창과 기존 내비의 정보 탐색 단계 연결\n\n기존36의 내비/연구 알림 UI를 새 장면의 실제 CARLA 상태와 연결했다. 큰 주행 창은 같은 프레임을 구독하며 모델을 중복 기동하지 않는다. 상세/옵션 열기는 실행과 구분했고 승인 후 실제 거리 확보 및 피드백을 확인했다. 좁은 창의 알림 가림과 선택지 갱신 문제를 수정했다. 출력 크기 변경과 원본 재구성 품질을 구별해 실제 확대 렌더를 비교했다. 자체 규칙/어댑터 검사10개 통과. 제한과 증거 위치는29번 기록. 참가자 연구와 연구실 성능 확인은 아니다.')
edit(L/'README.md','''## 2026-10-19 · 큰 주행 창 + 기존 내비

47 실행 시 큰 별도 주행 창과 http://127.0.0.1:8774/navigation 이 함께 열린다. 기존36의 HTML/Three.js/cockpit/research-events 자산을 읽고, 이 경로에서만 NuRec용 상태/명령 어댑터를 적용한다. 기존36 파일과 서버는 그대로다.

내비에서 주행 시작 / 일시정지 / 처음으로 / 화질을 조작한다. 알림→상황 설명→대응 방법 보기→옵션 선택→실행 순서다. 클락션 / 차간 거리 넓히기 / 그냥 유지를 실제 같은 시나리오에 반영한다. 큰 창에서는 F11 전체 화면, Space 시작/정지, 창 닫기는 일시정지다. 브라우저 큰 화면 대안은 /drive, 이전 독립 시험 UI는 / 이다. 큰 창은 프레임 구독만 하며 NuRec를 중복 렌더하지 않는다.

1080p(1920×1080)도 화질 메뉴에 추가했다. 기본값540p는 보존하며 이번 종료 시점은1080p/시작 위치/정지 상태다. 최초 image_scale .125는240×135 시험 출력이었다. 원본 모델을 다운스케일 학습한 것이 아니다. 동일 pretrained 모델에서540p와1080p를 새 렌더해 비교했고1080p 짧은 물리 주행도 확인했다. 연구실 GPU 정보는 미확인이며 FPS/장시간 안정성/모든 장면 지원을 보증하지 않는다.

이 모드의 Qwen 음성·음성 인식·제스처는 아직 연결하지 않았다. 지도는 실제 촬영 궤적과 두 차로 개략 표시이며 기존 서울 목적지를 새 장면에 배치하지 않는다. 알림 노출과 클릭을 기록하며 시선/독해를 측정하지 않는다.

검사: test_navigation_adapter.py5개 + test_scenario2.py5개 통과. 실제 브라우저에서 거리 확대/클락션/유지/닫기/초기화를 확인. 네이티브 큰 창 확인 완료; F11 자동 확인에는 다른 창이 겹쳐 해당 캡처를 제외했다. 증거는 validation/navigation-20261019, native-1080-20261019-192912, reports/navigation-display-result.json. 원본·생성 화면·성능은 D 안에 둔다.
''')
edit(P/'README.md','''## 별도47 · 큰 화면과 기존 내비 연결

`47-NuRec-Live-Drive.bat`은 큰 주행 창과 `http://127.0.0.1:8774/navigation`을 함께 연다. 내비에서 주행 시작 후 하단 주행 상태 알림을 열고 설명→대응 방법→클락션/거리 넓히기/그냥 유지→실행을 선택한다. 두 창은 같은 CARLA 차량에 연결된다. 큰 창 F11 전체 화면, Space 시작/정지. 화질 메뉴에1080p를 추가했으며 원본 재학습 없이 출력 크기를 바꾼다. 연구실 실시간 성능은 아직 확인하지 않았다. 기존36은 보존했다. 새 모드의 음성/제스처 전체 통합은 아직 아니다. 자세한 범위는 D/live/README와 포트폴리오29번 기록.
''')
print('Private result and qualitative portfolio record saved:',evidence)
