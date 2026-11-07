# 한국어 / English 내비게이션과 음성

기존 테슬라형 3D 차량·지도·음악 플레이어·하단 컨트롤을 그대로 사용합니다. 언어만 바꾸며, 새 주행을 만들거나 차량 제어 규칙을 바꾸지 않습니다.

## 사용하기

- 50번 CARLA 실행 후 상단 **Language → English**를 선택합니다. 좁은 화면에서는 설정 안에 있습니다.
- 영어 내비: `http://127.0.0.1:8774/navigation?lang=en&voice=1`
- 한국어 내비: `http://127.0.0.1:8774/navigation?lang=ko&voice=1`
- 출발 선택 화면: `http://127.0.0.1:8774/?lang=en`
- 언어 선택은 해당 기기·브라우저에 저장됩니다. PC와 휴대폰은 각각 선택합니다.
- 휴대폰은 기존 QR로 연결한 뒤 Language를 선택하거나 현재 보안 주소의 `/m/?lang=en`을 엽니다. IP와 인증서 설정은 기존 연결 방식을 따릅니다.

언어 변경은 화면을 다시 불러옵니다. 진행 중인 차량은 리셋되지 않지만, 열어둔 설명·확인창과 재생 중 음성은 닫힙니다. 실행 중인 요청은 서버에서 계속 진행됩니다. 참가자에게 보여주기 전에 언어를 선택해 두세요.

## 번역 범위

7개 CARLA 상황의 제목·설명·선택지, 실행 확인·취소·결과 안내, 출발 선택 화면과 내비 설정을 영어로 제공합니다. 모바일 연결·알림 설정 안내와 시스템 상황 알림도 영어를 지원합니다. 곡명·가수 같은 원래 음악 메타데이터는 번역하지 않습니다.

화면 번역은 `english_locale.py`와 `language.js`가 담당합니다. 서버에 보내는 행동 ID, 세션 ID, 취소·실행 조건은 그대로 유지합니다. 상황 설명은 기존 시나리오 상태를 바탕으로 한 문장입니다. LLM이 실시간으로 도로를 판단하는 기능은 아닙니다.

## 목소리

| 용도 | 모델 / 목소리 | 처리 방식 |
|---|---|---|
| 홍익 AI와 외부 안내 | Qwen3-TTS 0.6B CustomVoice / Sohee, English | 미리 생성한 WAV 재생 |
| 외부인의 영어 대사 | Qwen3-TTS 1.7B CustomVoice / Aiden, English | 감정 지시로 미리 생성한 WAV 재생 |

영어 22개 음성 파일을 로컬 캐시에 준비했습니다. 주행 중에는 모델을 올리거나 음성을 새로 합성하지 않습니다. 브라우저가 소리를 허용하려면 출발 또는 AI 버튼 클릭이 필요할 수 있습니다. 영어 발음·연기는 한국어 음성의 원음 녹음과 같지 않으며, 청취 품질은 실제 스피커에서 확인해야 합니다.

새 PC에서는 사용권이 있는 기존 모델과 `.tts-env`가 먼저 필요합니다. 주행을 종료하고 `python prepare_english_audio.py`로 캐시를 준비합니다. 스크립트는 설치된 로컬 모델만 사용하고, 메모리·GPU 여유를 확인합니다. 생성 음성·모델·음악·인증서·연결 정보는 Git에 넣지 않습니다. 캐시가 없으면 영어 음성을 준비하지 못한 상태로 표시하며, 다른 한국어 음성을 대신 섞지 않습니다.

## 검증 범위

- 실제 CARLA: 영어 졸음운전 선택지, 실행 전 취소 시 클락션 미작동, 재요청 후 한 번 작동, 결과 관찰·종료를 확인했습니다.
- 실제 CARLA 카풀: 뒤에서 먼저 영어 Aiden 음성이 들리고, 옆 유리창에 도착한 뒤 문 두드림·다음 대사가 시작되는 순서와 이동 요청의 완료·접촉 없음 상태를 확인했습니다.
- 실제 브라우저: 영어 Sohee WAV가 재생되고 원래 차량·지도·음악 레이아웃이 유지되는지 확인했습니다. 작은 화면의 언어 선택기는 설정으로 이동합니다.
- 화면 fixture: 영어 출발·설정·선택·확인 및 한국어 복귀, 모바일 연결·알림 설정·선택·확인에서 번역 누락과 JavaScript 오류를 검사했습니다. Fixture는 실제 주행이 아닙니다.
- 모바일 서버 단위 검사: 연결 권한, 영어 음성 경로 제한, 언어 저장과 영어 알림 구성·중복 방지를 확인했습니다. 이번 변경에서 실제 iPhone의 영어 잠금 화면 알림 수신을 재검증한 것은 아닙니다.

CARLA 기본 DX12, 비동기 물리, 시작 16GiB / 검증 2GiB 메모리 기준은 유지합니다. 영어화는 30fps 성능 보증이나 연구실 3면 화면 검증을 의미하지 않습니다.

## For English-speaking teammates

Choose **Language → English** in the original navigation interface; on narrow screens, open settings. The choice is saved in that browser. A language change reloads the interface without resetting the drive, so select it before a participant session.

Hongik AI uses pre-generated English Sohee recordings. Exterior dialogue uses pre-generated English Aiden recordings. There is no TTS inference during driving. Explanations are based on scripted scenario state, not live LLM perception. Source code is shared here; licensed models, generated audio and private connection material are not included.
