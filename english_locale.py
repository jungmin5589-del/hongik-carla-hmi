"""Reviewed display translations; simulation IDs and control payloads stay unchanged."""
from english_voice import catalog as voice_catalog

COPY={
 'congestion':('Slow traffic is blocking the road ahead','The car ahead and the large vehicles on our right are moving slowly. Fast traffic keeps passing on the left.','We are maintaining our gap and checking for a safe opening on the left.'),
 'fog':('Dense fog is limiting visibility','The fog is getting thicker and reducing visibility ahead.','We are slowing down and maintaining our distance from the car ahead.'),
 'night':('The car ahead is swaying between lane markings','The car ahead is moving from side to side near the lane boundaries.','We are staying in our lane and monitoring the car ahead.'),
 'yield':('The pedestrian is hesitating at the crossing','The pedestrian beside the crossing is gesturing and stepping back and forth.','We have stopped and are checking whether the pedestrian intends to cross.'),
 'carpool':('Someone outside is approaching the door','While waiting for your fellow passenger, someone has approached the car and is knocking on the window.','We are keeping the doors closed and checking the person and the space around the car.'),
 'rattle':('There is a recurring sound outside the vehicle','There is a scraping or rattling sound from outside the vehicle while driving.','We are checking the current driving conditions. The cause of the sound is not yet confirmed.'),
 'cargo':('An object has fallen onto the road ahead','An object has fallen from the truck ahead and remains on the road.','We are slowing down before the object and checking for space to pass.')}

OPTIONS={
 'congestion':[('Sound the horn','Sound one long horn blast toward the car ahead.'),('Move into the leftmost lane','Wait for a safe opening, then move to the left.'),('Get out nearby','Find a suitable stopping area before ending the ride.')],
 'fog':[('View the surroundings','Review the positions of surrounding traffic and lane markings.'),('Drive more slowly','Reduce speed further and maintain space ahead.'),('Pull over','Check for a suitable stopping area, then move over slowly.')],
 'night':[('Sound the horn','Sound one short horn and monitor the car ahead.'),('Increase the following distance','Create a larger gap to the car ahead.'),('Overtake when safe','Overtake on the left only when there is a safe opening.'),('Wait at the roadside','Check for a stopping area and wait for the other car to move away.')],
 'yield':[('Ask the pedestrian to cross first','Use the external speaker to offer the pedestrian priority.'),('Proceed slowly','Proceed only after the pedestrian has cleared the crossing.'),('Get out here','Check for a suitable stopping area nearby first.')],
 'carpool':[('Contact the control center','Request assistance and review the waiting status.'),('Leave now','Move to another waiting position after the person has moved away.'),('Move somewhere safe and get out','Check the surroundings, move to a suitable stopping area, and end the ride.')],
 'rattle':[('View vehicle status','Review the current speed, driving status, and any confirmed warnings.'),('Check while driving slowly','Continue at a reduced speed while checking the status.'),('Pull over and check','Check for a clear stopping area before moving over.')],
 'cargo':[('Inspect the object','Stop and zoom in on the forward view.'),('Request to pass the object','Pass slowly on the left when there is room.'),('Stop and wait','Wait at a distance before the object.'),('Let the vehicle decide','Stop and check the surroundings before proceeding.')]
}

# Whole sentences first. Small labels also cover the original Tesla-style UI.
PAIRS='''
참가자 이름 또는 ID	Participant name or ID
참가자 등록	Register participant
등록된 참가자:	Registered participant:
관리자 · 실험 기록	Admin · Research records
시나리오 선택으로	Back to scenario selection
주행이 끝났어요. 다른 상황을 선택할 수 있어요.	The drive has ended. You can select another scenario.
장면 소리 켜기	Enable scene sound
알림 설정	Notification settings
내 주행과 연결	Connect to your drive
휴대폰에서도	On your phone,
함께 살펴봐요.	stay connected to your drive.
PC의 ‘휴대폰 연결’ 화면에 있는 QR을 스캔하거나 연결 코드 6자리를 입력해 주세요.	Scan the QR code on the PC's phone connection page or enter the six-digit code.
연결 코드	Connection code
PC와 연결	Connect to PC
내 주행	My drive
연결 확인 중	Checking the connection
실제 영상이 아닌 차량 상태 일러스트	Vehicle status illustration, not live video
상향등	High beam
남은 구간	Distance remaining
새로운 주행 상황이 있어요	There is a new driving situation
홍익 AI에서 상황을 확인해 보세요	Open Hongik AI to review the situation
주행 준비 중	Preparing your drive
PC에서 시나리오를 시작하면 함께 연결됩니다.	Start a drive on the PC to connect here.
상황 살펴보기	Review the situation
앱 안의 알림 소리 준비	Enable in-app alert sounds
이 화면을 열어 두면 상황 알림을 바로 확인할 수 있어요. 잠금 화면 알림은 설정에서 따로 켭니다.	Keep this screen open for situation alerts. Enable lock-screen notifications separately in settings.
설정 닫기	Close settings
알림 연결 준비 상태	Notification readiness
지금 열린 주소:	Current address:
보안 주소를 Safari에서 열기	Open the secure address in Safari
아이폰 시스템 알림 켜기	Enable iPhone notifications
알림 받아보기	Send a test notification
시스템 알림 끄기	Disable system notifications
잠금 화면 알림 · 처음 한 번 설정	Lock-screen notifications · initial setup
같은 Wi-Fi에서 사용해요. 아래 설정은 아이폰에서 직접 진행해 주세요.	Use the same Wi-Fi network. Complete these steps on your iPhone.
1. 이 PC의 연구용 인증서 준비	1. Prepare this PC's research certificate
인증서를 신뢰하면 이 PC가 발급하는 인증서를 아이폰이 신뢰하게 됩니다. PC의 ‘휴대폰 연결’ 화면에 표시된 인증서 지문을 확인한 뒤 진행해 주세요.	Trusting this certificate allows your iPhone to trust certificates issued by this PC. First check the certificate fingerprint on the PC's phone connection page.
연구용 공개 인증서 다운로드	Download the public research certificate
설정 → 프로파일이 다운로드됨 → ‘Hongik AI local research CA’ 확인·설치. 이후 설정 → 일반 → 정보 → 인증서 신뢰 설정에서 같은 이름을 직접 확인·신뢰합니다. 프로파일 메뉴가 없으면 일반 → VPN 및 기기 관리에서 확인해 주세요.	In Settings, open Profile Downloaded and verify and install 'Hongik AI local research CA'. Then verify and trust that name in General → About → Certificate Trust Settings. If no profile menu appears, check General → VPN & Device Management.
이 앱은 아이폰의 신뢰 설정을 자동으로 바꾸지 않습니다. 인증서 경고가 계속되면 다음 단계로 진행하지 말고 PC 주소와 인증서를 다시 확인해 주세요.	This app does not change your iPhone's trust settings automatically. If certificate warnings continue, check the PC address and certificate before proceeding.
2. 보안 주소로 다시 연결	2. Reconnect using the secure address
PC의 ‘휴대폰 연결’ 화면을 새로고침해 새 코드를 확인한 뒤, 아래 보안 주소를 열고 연결 코드 6자리를 입력해 주세요. 기존 HTTP 연결은 해제됩니다.	Refresh the PC's phone connection page for a new code. Open the secure address below and enter its six-digit code. The previous HTTP connection will be disconnected.
보안 주소 열기	Open the secure address
3. 홈 화면에 추가하고 알림 허용	3. Add to Home Screen and allow notifications
보안 주소를 Safari에서 연 뒤 공유 버튼 → ‘홈 화면에 추가’. 홈 화면의 홍익 AI를 열고 설정 → ‘아이폰 시스템 알림 켜기’ → 허용을 누르세요.	Open the secure address in Safari, then choose Share → Add to Home Screen. Open Hongik AI from Home Screen and choose Settings → Enable iPhone notifications → Allow.
‘알림 받아보기’를 누르고 아이폰을 잠가 실제로 도착하는지 확인해 주세요. 알림을 눌러 앱을 연 다음 행동을 선택합니다. PC와 같은 Wi-Fi가 연결되어 있어야 행동 요청이 전달됩니다.	Send a test notification and lock your iPhone to check delivery. Tap the notification to open the app and choose an action. Your phone must be on the PC's Wi-Fi network to send requests.
일반 HTTP 연결에서는 앱을 열어둔 동안의 배너와 선택만 사용할 수 있어요.	On an HTTP connection, banners and choices are available while the app is open.
상황 닫기	Close the situation
현재 상황과 차량의 판단	Current situation and vehicle response
설명 다시 듣기	Replay the explanation
읽기 멈춤	Stop reading
연결을 확인해 주세요.	Please check the connection.
PC와 연결된 뒤 다시 선택해 주세요.	Connect to the PC before choosing again.
지금은 일반 HTTP 주소예요. 아래 보안 주소를 Safari로 열고, 그 주소로 홈 화면에 추가해 주세요.	This is an HTTP address. Open the secure address below in Safari and add it to Home Screen.
지금은 브라우저 탭으로 열려 있어요. Safari의 공유 → 홈 화면에 추가 후, 홈 화면의 홍익 AI 아이콘으로 다시 열어 주세요.	You are in a browser tab. In Safari, choose Share → Add to Home Screen, then open the Hongik AI icon.
이 화면에서 시스템 알림 기능을 사용할 수 없어요. 아이폰은 iOS 16.4 이상에서 보안 주소로 추가한 홈 화면 앱이 필요해요.	System notifications are unavailable here. iPhone requires iOS 16.4 or later and a Home Screen app added from the secure address.
이 홈 화면 앱에서는 PC 연결이 아직 확인되지 않았어요. 설정을 닫고 PC의 현재 QR 또는 연결 코드로 연결해 주세요. Safari 탭의 연결과 다를 수 있어요.	This Home Screen app is not connected to the PC yet. Close settings and use the PC's current QR or code. Its connection may differ from the Safari tab.
이 앱의 알림이 차단돼 있어요. 아이폰 설정 → 알림 → 홍익 AI에서 알림 허용을 켠 뒤 이 앱을 다시 열어 주세요.	Notifications are blocked. In iPhone Settings → Notifications → Hongik AI, allow notifications, then reopen this app.
준비됐어요. 아래 버튼을 누르고 아이폰의 알림 허용을 선택해 주세요.	Ready. Tap the button below and allow notifications on your iPhone.
알림 연결 중…	Connecting notifications…
시스템 알림 연결됨	System notifications connected
시스템 알림이 등록되어 있어요. ‘알림 받아보기’로 실제 수신을 확인해 주세요.	System notifications are registered. Send a test notification to check delivery.
HTTPS 보안 주소	Secure HTTPS address
아이폰 홈 화면 앱으로 실행	Running as an iPhone Home Screen app
브라우저 실행 환경	Browser environment
이 화면에서 PC 연결	PC connection in this app
알림 권한 허용	Notification permission
✓ 완료 ·	✓ Ready ·
○ 필요 ·	○ Needed ·
알림 연결 준비에 실패했어요. PC 연결을 확인한 뒤 앱을 다시 열거나 알림 켜기를 다시 눌러 주세요.	Could not prepare notifications. Check the PC connection, then reopen the app or try enabling notifications again.
알림 준비가 지연되고 있어요. PC 연결을 확인하고 앱을 다시 열어 주세요.	Notification setup is taking longer than expected. Check the PC connection and reopen the app.
PC와 연결됨	Connected to PC
PC 연결을 기다리는 중	Waiting for PC connection
선택한 행동의 결과 확인 중	Checking the outcome
상황이 생기면 홍익 AI가 알려드릴게요.	Hongik AI will notify you when a situation arises.
PC에서 주행을 시작해 주세요.	Start the drive on the PC.
행동 결과 보기	View the outcome
행동 결과 확인 중	Checking the outcome
새 상황 · 눌러서 확인	New situation · tap to review
현재 주행	Current drive
차량에 연결되면 상황을 확인할 수 있어요.	Connect to the vehicle to review the situation.
선택한 행동의 결과	Outcome of your choice
PC와 연결했어요. 주행을 시작하면 함께 알려드릴게요.	Connected to the PC. Updates will appear when the drive starts.
요청을 전달했어요. PC 주행 화면에서 결과를 확인해 주세요.	Request sent. Review the outcome on the PC driving screen.
실행 전 요청을 취소했어요.	The request was canceled before execution.
주변 정차 공간을 확인하고 감속해요.	Check for a stopping area and slow down.
지원 요청을 전달하고 현재 차량 상태를 확인해요.	Send an assistance request and review the vehicle status.
아이폰 알림을 허용한 뒤 다시 시도해 주세요.	Allow iPhone notifications and try again.
시스템 알림을 연결했어요. 알림 받아보기로 확인해 주세요.	System notifications connected. Send a test notification to check delivery.
알림 제공자에게 전송했어요. 실제 수신도 확인해 주세요.	Sent to the notification provider. Please also check delivery on your phone.
전송 상태를 확인하지 못했어요.	Could not confirm the delivery status.
시스템 알림을 껐어요.	System notifications disabled.
앱 안의 알림 소리 준비됨	In-app alert sounds ready
이 화면을 열어둔 동안 상황 알림 소리를 준비했어요.	Alert sounds are ready while this screen remains open.
주행·환경음\tDriving and ambient sound
주행·환경음 크기\tDriving and ambient volume
실제 주행 녹음 파일을 준비해 주세요\tThe recorded driving audio is not available.
출발하면 재생됩니다\tPlays after departure
주행 중 재생\tPlaying while driving
소리 준비 중\tPreparing audio
주행 소리 준비됨\tDriving audio ready
현재 주행에서 다시 요청해 주세요.\tPlease make the request again in the current drive.
요청을 진행 중이에요.\tA request is already in progress.
주행이 끝났어요. 출발 설정에서 다시 준비해 주세요.\tThe drive has ended. Prepare another drive in departure settings.
현재 상황을 먼저 확인해 주세요.\tReview the current situation first.
이 상황에서 제공하는 요청을 선택해 주세요.\tChoose one of the requests available for this situation.
선택한 요청을 진행하고 있어요. 취소하거나 결과를 확인해 주세요.\tThe selected request is in progress. Cancel it or review the outcome.
주행이 변경됐습니다. 현재 화면에서 다시 선택해 주세요.\tThe drive has changed. Make your selection again in the current screen.
대응 방법을 선택한 뒤 실행해 주세요.\tChoose a response before confirming it.
주행 정보를 먼저 열어 주세요.\tOpen the driving information first.
대응 방법을 먼저 열어 주세요.\tOpen the response choices first.
확인했습니다.\tAcknowledged.
지원하지 않는 요청입니다.\tThis request is not supported.
주행을 일시정지했습니다.\tThe drive has been paused.
휴대폰에서 사용할 수 없는 조작입니다.\tThis action is not available on the phone.
차량 일시정지 · 마지막 수신 위치\tVehicle paused · last received position
주행 제안을 선택하면 차량에 반영됩니다.\tConfirmed requests are applied to the vehicle.
목적지 랜드마크\tDestination landmark
주행 중 · 목적지 랜드마크\tDriving · destination landmark
주변 확인 중\tChecking the surroundings
왼쪽 차로 주행\tDriving in the left lane
한국어\t한국어
홍익 AI\tHongik AI
차량\tVehicle
실시간 연결\tLive connection
연결 대기\tWaiting for connection
차량에 연결하고 있습니다.\tConnecting to the vehicle.
주행을 기다리고 있어요\tWaiting to start
주행 중\tDriving
정차 중\tStopped
주차 구역\tParking area
출발 위치·방향 정렬을 확인하지 못했습니다. 다시 준비해 주세요.\tThe departure position and heading could not be verified. Prepare the scene again.
차량의 출발 위치·방향이 달라졌습니다. 출발 위치로 다시 준비해 주세요.\tThe vehicle has moved from its departure position. Reset the scene before starting.
이전 주행 화면에서 온 요청입니다. 현재 내비를 새로 열어 주세요.\tThis request came from an earlier drive. Reopen the current navigation screen.
출발 준비\tReady to depart
출발 대기\tReady to depart
주행 지도\tNavigation map
주행 화면\tDriving view
주변 상황\tSurroundings
목적지\tDestination
목적지는 아직 설정하지 않았어요.\tNo destination has been set yet.
주변 차량과 도로를 확인하세요.\tReview the surrounding traffic and road.
어디로 갈까요?\tWhere would you like to go?
목적지 검색\tSearch destination
목적지 선택\tChoose destination
목적지 변경\tChange destination
경로를 따라 주행합니다.\tFollowing the route.
경로를 따라 주행\tFollow the route
경로를 따라 계속 주행\tContinue along the route
경로를 따라 이동\tFollowing the route
경로 안내\tRoute guidance
도착 예정\tArrival time
예상 소요\tTravel time
남은 거리\tDistance remaining
남은 구간\tRemaining distance
종료\tEnd
주변 확인 · 정차 중\tChecked surroundings · stopped
시야 제한 구간 · 서서히 감속\tLimited visibility · slowing down
앞차와 간격을 유지하며 주행\tMaintaining the following distance
요청한 대응 진행 중\tCarrying out your request
서서히 정차 중\tSlowing to a stop
주변 차량과 도로를 살피며 이동하고 있어요.\tMonitoring traffic and the road while driving.
전방 시야를 확인하며 주행하고 있어요.\tMonitoring visibility ahead while driving.
주변 차량과 도로를 살피며 이동하고 있어요.\tMonitoring traffic and the road while driving.
차량이 정차했습니다\tThe vehicle has stopped
차량이 정차했습니다.\tThe vehicle has stopped.
차량이 정차했어요\tThe vehicle has stopped
차량 상태\tVehicle status
지금 상황\tCurrent situation
현재 상황\tCurrent situation
차가 하고 있는 일\tWhat the vehicle is doing
현재 상황과 차량의 판단\tCurrent situation and vehicle response
현재 주행\tCurrent drive
어떻게 할까요?\tWhat would you like to do?
설명 다시 듣기\tReplay explanation
설명 듣기\tListen to explanation
읽기 멈춤\tStop playback
설명 중\tSpeaking
음성 꺼짐\tVoice off
Sohee 음성을 준비하지 못했어요.\tThe Sohee recording is not available.
음성을 재생하지 못했어요. 다시 눌러 주세요.\tAudio could not play. Please try again.
다시 듣기를 눌러 주세요.\tSelect replay to listen.
음성을 재생하지 못했어요.\tAudio could not play.
상황 살펴보기\tReview the situation
새 상황 · 눌러서 확인\tNew situation · tap to review
주변 반응 확인 중\tMonitoring the response
주변 확인 완료\tSurroundings checked
주변 상황을 확인했어요\tThe response is complete
주변 상황을 확인했어요.\tThe response is complete.
요청한 대응을 진행하고 있어요\tCarrying out your request
주변의 반응을 확인하고 있어요\tMonitoring the response
서서히 정차하고 있어요\tSlowing to a stop
그냥 둘게요\tLeave it as it is
도움 요청\tRequest help
정차 요청\tRequest a stop
선택 취소\tCancel selection
요청 취소\tCancel request
실행\tConfirm
확인\tOK
한 번 더\tOnce more
현재 차량 주변 위치\tCurrent surrounding positions
실제 CARLA 주변 차량 위치\tCurrent CARLA vehicle positions
실제 주행 결과 화면\tLive driving result
요청을 확인하고 있어요.\tChecking your request.
요청을 전달하지 못했습니다.\tThe request could not be sent.
주행 연결을 확인해 주세요.\tPlease check the driving connection.
차량 응답을 확인하지 못했습니다. 현재 상태를 확인해 주세요.\tThe response could not be confirmed. Please check the current status.
요청이 실행되지 않았습니다.\tThe request was not executed.
동승자를 기다리고 있어요\tWaiting for your fellow passenger
경로를 따라 이동하고 있어요\tFollowing the route
주변 교통과 주행 상태를 확인하고 있어요.\tMonitoring surrounding traffic and the driving status.
차 밖에서 누군가 문을 두드리고 있어요\tSomeone outside is knocking on the door
요청을 준비했어요. 3초 안에 취소할 수 있어요.\tYour request is queued. You can cancel within three seconds.
요청을 취소했어요.\tThe request has been cancelled.
요청을 중단하고 차량을 정지하고 있어요.\tStopping the request and slowing the vehicle to a stop.
요청을 중단하고 차량이 정차했어요.\tThe request was cancelled and the vehicle has stopped.
경적을 한 번 울렸어요. 앞차의 반응을 확인하고 있어요.\tThe horn has sounded once. We are monitoring the car ahead.
서서히 감속해 앞차와의 간격을 넓히고 있어요.\tSlowing gradually to increase the following distance.
차로 안에서 옆 트럭과의 간격을 넓히고 있어요.\tMoving within our lane to create more space beside the truck.
왼쪽 차로의 안전한 틈을 기다리고 있어요.\tWaiting for a safe opening in the left lane.
왼쪽 차로를 확인하고 앞차를 지나갈 공간을 살피고 있어요.\tChecking the left lane for space to overtake.
속도를 더 낮추고 주행 상태를 확인하고 있어요.\tReducing speed further and monitoring the driving status.
주변과 차량 상태를 자세히 표시하고 있어요.\tShowing the surroundings and vehicle status in more detail.
외부 스피커로 먼저 건너시라고 알렸어요. 정지한 채 반응을 확인해요.\tThe external speaker has invited the pedestrian to cross. We remain stopped while monitoring their response.
보행자가 횡단 구간을 벗어났는지 확인하고 있어요.\tChecking whether the pedestrian has cleared the crossing.
지원 요청을 접수했어요. 차량 상태를 확인하며 안내를 기다려요.\tThe assistance request is registered. We are monitoring the vehicle while waiting for guidance.
주변 사람이 물러나면 대기 위치를 옮겨요.\tWe will move to another waiting position once the person is clear.
정차할 공간을 확인하고 감속하고 있어요.\tChecking for a stopping area and reducing speed.
안전하게 정차할 장소를 확인하고 있어요.\tChecking for a suitable stopping area.
현재 차량의 대응을 유지하고 있어요.\tMaintaining the current vehicle response.
옆 차로를 확인하고 낙하물을 피할 공간을 살피고 있어요.\tChecking the adjacent lane for room to pass the object.
낙하물 앞에서 간격을 두고 멈추고 있어요.\tStopping at a distance before the object.
정지 후 주변 공간이 확보되면 회피해요.\tAfter stopping, we will pass when there is sufficient space.
접촉이 감지되어 차량을 정지했어요. 주변 상황을 확인하고 있어요.\tContact was detected and the vehicle has stopped. We are checking the surroundings.
요청한 동작의 완료를 확인하지 못했어요. 차량을 정지하고 주변을 확인해요.\tWe could not confirm completion of the request. The vehicle is stopping to check the surroundings.
안전하게 옮겨 설 공간을 확인하지 못했어요. 현재 위치에서 정지 상태를 유지해요.\tA suitable stopping area could not be confirmed. We are remaining stopped at the current position.
확인한 정차 공간으로 이동해 멈췄어요.\tThe vehicle has moved into the verified stopping area and stopped.
 이용을 마칠 수 있어요.\t You may end the ride.
 주변 상황을 확인하고 있어요.\t We are checking the surroundings.
경적을 한 번 짧게 울렸어요. 앞차의 움직임을 살피며 주행했어요.\tThe horn sounded once. We continued monitoring the car ahead.
경적을 한 번 울렸어요. 앞차의 움직임을 살피며 주행했어요.\tThe horn sounded once. We continued monitoring the car ahead.
차로 안에서 옆 트럭과의 간격을 넓혔어요.\tWe moved within our lane to increase the space beside the truck.
왼쪽 차로의 공간을 확인하고 차로를 변경했어요.\tWe checked the available space and moved into the left lane.
왼쪽 차로로 이동해 앞차를 지나갔어요.\tWe moved into the left lane and passed the car ahead.
속도를 더 낮추고 주행 상태를 확인했어요.\tWe reduced speed further and checked the driving status.
주변 위치와 현재 차량 상태를 자세히 표시했어요. 확인되지 않은 원인은 계속 살피고 있어요.\tThe surroundings and current vehicle status are displayed in detail. Any unconfirmed cause still requires checking.
먼저 건너시라고 안내한 뒤 보행자가 횡단 구간을 벗어나는 것을 확인했어요.\tAfter inviting the pedestrian to cross, we confirmed that they cleared the crossing.
보행자가 횡단 구간을 벗어난 것을 확인한 뒤 서행으로 출발했어요.\tWe confirmed that the pedestrian cleared the crossing before proceeding slowly.
지원 요청을 접수했어요. 실제 상담원 연결은 아직 확인되지 않아 현재 차량 상태를 유지해요.\tThe assistance request is registered. A live operator connection is not confirmed, so we are maintaining the current vehicle status.
주변 사람이 물러난 뒤 다른 대기 위치로 이동해 정차했어요.\tAfter the person moved clear, we moved to another waiting position and stopped.
추가 요청 없이 현재 차량의 대응을 유지했어요.\tWe maintained the current vehicle response without an additional request.
옆 차로로 이동해 낙하물을 지나갔어요.\tWe moved into the adjacent lane and passed the object.
정지 후 주변을 확인하고 낙하물을 피해 지나갔어요.\tAfter stopping and checking the surroundings, we passed the object.
낙하물 앞에서 간격을 두고 기다렸어요.\tWe waited at a distance before the object.
차량의 대응 결과를 확인했어요.\tThe vehicle response has been checked.
내 음악\tMy music
음악을 선택하세요\tChoose music
음악 목록\tMusic library
음악 목록 열기\tOpen music library
음악 목록 닫기\tClose music library
이전 곡\tPrevious track
다음 곡\tNext track
재생\tPlay
음량\tVolume
음소거\tMute
재생 위치\tPlayback position
디스플레이\tDisplay
화면 설정\tDisplay settings
설정 닫기\tClose settings
전체 화면\tFull screen
열기\tOpen
주행 설정\tDrive settings
출발 설정\tDeparture settings
출발 위치로\tReset to departure
출발\tDepart
일시정지\tPause
차량 연결 중\tConnecting to vehicle
휴대폰 연결\tConnect phone
켜짐\tOn
꺼짐\tOff
켜기\tEnable
끄기\tDisable
설정 열기\tOpen settings
화면 미리보기\tDisplay preview
선명하게 · 720p\tSharp · 720p
가볍게 · 360p\tLight · 360p
균형 · 540p\tBalanced · 540p
고화질 · 1080p\tHigh resolution · 1080p
화면 선명도\tImage quality
목적지·AI 음성 안내\tNavigation and AI voice
내비 안내 목소리\tNavigation voice
홍익 AI 답변 목소리\tHongik AI voice
밝은 안내 · Supertonic F3\tBright guidance · Supertonic F3
한국어 음성 확인\tVoice preview
안내 듣기\tPlay sample
비상 정지\tEmergency stop
3D\t3D
위에서 보기\tTop view
주행 제안 보기\tView driving suggestion
차량 화면 설정\tVehicle display settings
표시 온도 낮추기\tDecrease displayed temperature
표시 온도 높이기\tIncrease displayed temperature
실내 온도 표시\tDisplayed cabin temperature
음성 안내\tVoice guidance
목적지·상황·내비 방식\tDestination, situation, and navigation mode
주행 목적지·상황·내비 방식\tDestination, situation, and navigation mode
YOLO 차량·보행자 감지\tYOLO vehicle and pedestrian detection
YOLO 감지 켜기\tEnable YOLO detection
앞차\tVehicle ahead
주변 차량\tSurrounding vehicle
보행자\tPedestrian
앞 트럭\tTruck ahead
낙하물\tFallen object
갓길\tRoadside
정차 구역\tStopping area
중심 간격\tCenter-to-center distance
왼쪽부터\tfrom the left
차로\tlane
분\tmin
초\tsec
곡\ttracks
4차로 정체\tFour-lane slow traffic
야간 졸음운전 차량\tSwaying vehicle at night
짙은 안개\tDense fog
보행자와 서로 양보\tHesitant pedestrian
카풀 대기 중 외부인 접근\tStranger approaching while waiting
주행 중 반복되는 이상음\tRecurring vehicle noise
도로 위 낙하물\tFallen object on the road
주행 환경을 선택하세요\tChoose a driving situation
인터페이스 조건\tInterface condition
B · 상태 안내와 대응 선택\tB · Status and response choices
A · 상태 안내와 고정 도움·정차\tA · Status and fixed help/stop requests
이 주행 선택\tChoose this drive
이 상황 선택\tChoose this situation
내비게이션 열기\tOpen navigation
큰 주행 화면 열기 ↗\tOpen large driving view ↗
주행 화면 열기 ↗\tOpen driving view ↗
시나리오를 선택하면 차량을 준비합니다.\tChoose a situation to prepare the vehicle.
CARLA 도로와 차량을 준비하고 있어요…\tPreparing the CARLA road and vehicles…
CARLA 차량과 카메라를 준비하고 있어요…\tPreparing the CARLA vehicles and camera…
CARLA의 도로·차량·보행자를 같은 엔진에서 표현합니다.\tRoads, vehicles, and pedestrians are rendered in the same CARLA engine.
기존 고속도로 세 주행과 보행자 양보·카풀 대기·이상음·낙하물 상황을 각각 선택할 수 있습니다.\tChoose the highway, pedestrian, waiting, noise, or fallen-object situations independently.
앞차와 오른쪽 대형차는 25~35km/h. 왼쪽에는 90km/h 차량이 계속 지나갑니다.\tThe car ahead and large vehicles on the right travel at 25–35 km/h. Traffic on the left keeps passing at 90 km/h.
우리 차는 차로를 유지합니다. 가까운 앞차는 차선 경계 주변에서 좌우로 흔들립니다.\tOur vehicle stays in its lane. The nearby car ahead sways around the lane boundary.
출발 10초 뒤 안개가 생겨 5초 동안 짙어집니다. 앞차를 따라 감속하며 주행합니다.\tFog begins 10 seconds after departure and thickens over five seconds. We slow down while following the car ahead.
상황 설명 후 양보 안내·안전 확인 후 출발·안전 정차 후 이용 종료 중 선택합니다.\tReview the situation, then offer priority, proceed after checking, or stop suitably before ending the ride.
주차 구역에서 동승자를 기다리는 중, 바깥에서 목소리와 발소리가 들리고 사람이 다가옵니다.\tWhile waiting in a parking area, voices and footsteps are heard outside as someone approaches.
차량 하부의 이상음을 듣고 상태 보기·저속 점검·정차 점검·주행 유지 중 선택합니다.\tAfter hearing a sound from underneath the vehicle, review its status, check at low speed, stop and check, or continue.
앞 트럭에서 물체가 떨어집니다. 감속 후 자세히 확인·회피·정지·차량 판단 위임 중 대응을 선택합니다.\tAn object falls from the truck ahead. After slowing down, choose to inspect, pass, stop, or let the vehicle respond.
홍익 AI 알림을 눌러 설명과 대응을 열고, 실행하면 결과를 확인한 후 종료합니다.\tOpen Hongik AI to review the situation and choices. After confirming, observe the response before the drive ends.
기본 1280×720 · 목표 30fps · 물리 차량 / 비동기 주행 ·\tDefault 1280×720 · Target 30 fps · Physical vehicles / asynchronous driving ·
준비 완료\tReady
준비 중 문제가 생겼어요:\tThere was a problem preparing the drive:
현재 출력\tCurrent output
횡단보도\tCrossing
주차 대기\tParked waiting
초 뒤 실행합니다\tseconds until execution
실행 후에도 3초 안에 취소할 수 있어요.\tYou can still cancel within three seconds after confirmation.
요청을 실행할까요?\tWould you like to confirm this request?
을 실행할까요?\t— confirm this request?
요청을 전달했어요. PC 주행 화면에서 결과를 확인해 주세요.\tYour request was sent. Observe the response in the PC driving view.
PC와 연결됨\tConnected to PC
PC 연결을 기다리는 중\tWaiting for PC connection
내 주행\tMy drive
새로운 주행 상황이 있어요\tThere is a new driving situation
홍익 AI에서 상황을 확인해 보세요\tReview it in Hongik AI
행동 결과 보기\tView response outcome
행동 결과 확인 중\tMonitoring response outcome
선택한 행동의 결과\tOutcome of your choice
선택한 행동의 결과 확인 중\tMonitoring the outcome of your choice
상황이 생기면 홍익 AI가 알려드릴게요.\tHongik AI will indicate when a situation occurs.
PC에서 주행을 시작해 주세요.\tStart the drive on the PC.
음성 안내가 꺼져 있어요.\tVoice guidance is off.
대응 방법 보기\tView response choices
대응 완료\tResponse complete
대화 완료\tConversation complete
차량 연결이 끊겼어요.\tThe vehicle connection was lost.
PC와 연결된 뒤 다시 선택해 주세요.\tConnect to the PC before choosing again.
실행 전 요청을 취소했어요.\tThe request was cancelled before execution.
'''

def catalog():
    from midterm_study import COPY as KO_COPY,OPTIONS as KO_OPTIONS
    from voice_bank import TEXTS as KO_VOICE
    from city_voice import TEXTS as KO_CITY_VOICE
    from pedestrian_voice import TEXTS as KO_PEDESTRIAN_VOICE
    from english_voice import TEXTS as EN_VOICE,canonical
    strings={line.split('\t',1)[0]:line.split('\t',1)[1] for line in PAIRS.splitlines() if '\t' in line}
    strings.update({'차량 연결을 확인하고 있어요.':'Checking the vehicle connection.','차량 연결이 끊겼어요. 다시 연결된 뒤 선택해 주세요.':'The vehicle connection was lost. Please choose after reconnection.'})
    for profile,triplet in COPY.items():
        strings.update(zip(KO_COPY[profile],triplet))
    for profile,options in OPTIONS.items():
        for ko,(label,detail) in zip(KO_OPTIONS[profile],options):
            strings[ko['label']]=label;strings[ko['detail']]=detail
    for source in (KO_VOICE,KO_CITY_VOICE,KO_PEDESTRIAN_VOICE):
        for key,value in source.items():
            key=canonical(key)
            if key in EN_VOICE:strings[value[0] if isinstance(value,tuple) else value]=EN_VOICE[key][0]
    strings.update({'상황 확인 · 대응 선택': 'Situation & response', '눌러서 상황·대응 보기': 'Tap to review situation and choices', '새 상황 · 눌러서 대응 선택': 'New situation · tap for choices', '요청을 받았어요.': 'Request received.', '요청을 반영하고 있어요.': 'Applying your request.', '지원 요청을 기록하며, 실제 상담원 연결은 보장되지 않아요.': 'The assistance request is recorded; connection to a live agent is not guaranteed.', '정차할 공간을 확인한 뒤 서서히 이동해요.': 'We will check for a stopping area and move over gradually.'})
    return dict(language='en',strings=strings,voices=voice_catalog())
